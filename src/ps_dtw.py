#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ps_dtw.py
=========

Packet-Semantic Weighted Dynamic Time Warping (PS-DTW).

This module contains the reusable similarity functions shared by the
in-device and global behavioral clustering stages.

Signed packet-length sequence convention:
  positive values: device -> remote endpoint
  negative values: remote endpoint -> device
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np

try:
    from numba import jit, prange
except ImportError:
    def jit(nopython=True, parallel=False):  # type: ignore
        def decorator(func):
            return func
        return decorator

    def prange(n):  # type: ignore
        return range(n)


@dataclass(frozen=True)
class PSDTWConfig:
    sigma: float = 35.0
    max_seq_len: int = 100
    small_thresh: float = 100.0
    small_weight: float = 10.0
    mtu_thresh: float = 1400.0
    mtu_weight: float = 1.0
    big_thresh: float = 350.0
    big_weight: float = 8.0
    cross_weight: float = 3.0


def split_signed_sequence(
    signed_seq: Sequence[int | float],
    max_seq_len: int | None = 100,
) -> Tuple[np.ndarray, np.ndarray]:
    """Split a signed packet-length sequence into upload/downlink arrays."""
    up: List[float] = []
    down: List[float] = []

    for x in signed_seq or []:
        if x > 0:
            if max_seq_len is None or len(up) < max_seq_len:
                up.append(abs(float(x)))
        elif x < 0:
            if max_seq_len is None or len(down) < max_seq_len:
                down.append(abs(float(x)))

        if max_seq_len is not None and len(up) >= max_seq_len and len(down) >= max_seq_len:
            break

    return np.asarray(up, dtype=np.float64), np.asarray(down, dtype=np.float64)


def pack_variable_length_sequences(arrays: Sequence[np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pack variable-length arrays into flat storage plus offsets/lengths."""
    n = len(arrays)
    offsets = np.empty(n, dtype=np.int64)
    lengths = np.empty(n, dtype=np.int32)

    total = 0
    for i, arr in enumerate(arrays):
        offsets[i] = total
        lengths[i] = int(arr.size)
        total += int(arr.size)

    flat = np.empty(total, dtype=np.float64)
    pos = 0
    for arr in arrays:
        length = int(arr.size)
        if length:
            flat[pos:pos + length] = arr
        pos += length

    return flat, offsets, lengths


@jit(nopython=True)
def weighted_dtw_distance(
    seq_a,
    seq_b,
    small_thresh,
    small_weight,
    mtu_thresh,
    mtu_weight,
    big_thresh,
    big_weight,
    cross_weight,
):
    n, m = len(seq_a), len(seq_b)
    if n == 0 and m == 0:
        return 0.0
    if n == 0 or m == 0:
        return 1e15

    prev_row = np.full(m + 1, 1e15, dtype=np.float64)
    curr_row = np.empty(m + 1, dtype=np.float64)
    prev_row[0] = 0.0

    for i in range(1, n + 1):
        curr_row[:] = 1e15
        val_a = seq_a[i - 1]
        is_small_a = val_a < small_thresh
        is_big_a = val_a > big_thresh
        is_mtu_a = val_a > mtu_thresh

        for j in range(1, m + 1):
            val_b = seq_b[j - 1]
            base_diff = abs(val_a - val_b)
            is_small_b = val_b < small_thresh
            is_big_b = val_b > big_thresh
            is_mtu_b = val_b > mtu_thresh

            if is_small_a and is_small_b:
                cost = base_diff * small_weight
            elif is_mtu_a and is_mtu_b:
                cost = base_diff / mtu_weight
            elif is_big_a and is_big_b:
                cost = base_diff / big_weight
            elif is_small_a != is_small_b:
                cost = base_diff * cross_weight
            else:
                cost = base_diff

            min_val = prev_row[j - 1]
            if prev_row[j] < min_val:
                min_val = prev_row[j]
            if curr_row[j - 1] < min_val:
                min_val = curr_row[j - 1]
            curr_row[j] = cost + min_val

        prev_row[:] = curr_row

    return prev_row[m]


def ps_dtw_similarity(
    signed_seq_a: Sequence[int | float],
    signed_seq_b: Sequence[int | float],
    config: PSDTWConfig = PSDTWConfig(),
) -> float:
    """Return PS-DTW similarity in [0, 1] for two signed packet sequences."""
    up_a, down_a = split_signed_sequence(signed_seq_a, config.max_seq_len)
    up_b, down_b = split_signed_sequence(signed_seq_b, config.max_seq_len)

    dist_up = weighted_dtw_distance(
        up_a, up_b,
        config.small_thresh, config.small_weight,
        config.mtu_thresh, config.mtu_weight,
        config.big_thresh, config.big_weight,
        config.cross_weight,
    )
    dist_down = weighted_dtw_distance(
        down_a, down_b,
        config.small_thresh, config.small_weight,
        config.mtu_thresh, config.mtu_weight,
        config.big_thresh, config.big_weight,
        config.cross_weight,
    )

    mean_len_up = (len(up_a) + len(up_b)) / 2.0
    mean_len_down = (len(down_a) + len(down_b)) / 2.0

    norm_up = dist_up / mean_len_up if mean_len_up > 0 else 1e9
    norm_down = dist_down / mean_len_down if mean_len_down > 0 else 1e9

    sim_up = float(np.exp(-norm_up / config.sigma)) if mean_len_up > 0 else 0.0
    sim_down = float(np.exp(-norm_down / config.sigma)) if mean_len_down > 0 else 0.0
    return float(np.sqrt(sim_up * sim_down))


@jit(nopython=True, parallel=True)
def compute_condensed_distance_matrix(
    flat_up,
    offsets_up,
    lengths_up,
    flat_down,
    offsets_down,
    lengths_down,
    n,
    small_thresh,
    small_weight,
    mtu_thresh,
    mtu_weight,
    big_thresh,
    big_weight,
    cross_weight,
    sigma,
):
    """Compute condensed pairwise distance matrix where distance = 1 - PS-DTW similarity."""
    dist_len = n * (n - 1) // 2
    dist_array = np.empty(dist_len, dtype=np.float64)

    for i in prange(n):
        len_u_a = lengths_up[i]
        off_u_a = offsets_up[i]
        len_d_a = lengths_down[i]
        off_d_a = offsets_down[i]
        up_a = flat_up[off_u_a:off_u_a + len_u_a]
        down_a = flat_down[off_d_a:off_d_a + len_d_a]

        row_offset = i * n - (i * (i + 1)) // 2

        for j in range(i + 1, n):
            len_u_b = lengths_up[j]
            off_u_b = offsets_up[j]
            len_d_b = lengths_down[j]
            off_d_b = offsets_down[j]
            up_b = flat_up[off_u_b:off_u_b + len_u_b]
            down_b = flat_down[off_d_b:off_d_b + len_d_b]

            dist_up = weighted_dtw_distance(
                up_a, up_b, small_thresh, small_weight,
                mtu_thresh, mtu_weight, big_thresh, big_weight, cross_weight,
            )
            dist_down = weighted_dtw_distance(
                down_a, down_b, small_thresh, small_weight,
                mtu_thresh, mtu_weight, big_thresh, big_weight, cross_weight,
            )

            mean_len_up = (len_u_a + len_u_b) / 2.0
            mean_len_down = (len_d_a + len_d_b) / 2.0

            norm_up = dist_up / mean_len_up if mean_len_up > 0 else 1e9
            norm_down = dist_down / mean_len_down if mean_len_down > 0 else 1e9

            sim_up = np.exp(-norm_up / sigma) if mean_len_up > 0 else 0.0
            sim_down = np.exp(-norm_down / sigma) if mean_len_down > 0 else 0.0
            final_sim = np.sqrt(sim_up * sim_down)

            dist_array[row_offset + (j - i - 1)] = max(0.0, 1.0 - final_sim)

    return dist_array


def pairwise_distance_matrix_from_signed_sequences(
    sequences: Sequence[Sequence[int | float]],
    config: PSDTWConfig = PSDTWConfig(),
) -> np.ndarray:
    """Compute a condensed pairwise distance matrix from signed sequences."""
    up_list, down_list = [], []
    for seq in sequences:
        up, down = split_signed_sequence(seq, config.max_seq_len)
        up_list.append(up)
        down_list.append(down)

    flat_up, offsets_up, lengths_up = pack_variable_length_sequences(up_list)
    flat_down, offsets_down, lengths_down = pack_variable_length_sequences(down_list)

    return compute_condensed_distance_matrix(
        flat_up, offsets_up, lengths_up,
        flat_down, offsets_down, lengths_down,
        len(sequences),
        config.small_thresh, config.small_weight,
        config.mtu_thresh, config.mtu_weight,
        config.big_thresh, config.big_weight,
        config.cross_weight, config.sigma,
    )
