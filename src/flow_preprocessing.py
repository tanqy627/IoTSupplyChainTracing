#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow_preprocessing.py
=====================

PCAP flow extraction and filtering.

This module consolidates the original Flow_extract and Flow_filter scripts into
a path-configurable public-release version.

Key behavior preserved from the experimental scripts:
  - flow key: (Protocol, Remote_IP, Device_Port, Server_Port)
  - signed packet-length sequence: upload positive, download negative
  - DNS A/AAAA/CNAME extraction with timestamped IP->domain events
  - domain matching by flow start timestamp
  - flow split by TCP FIN/RST or inactivity timeout
  - filtering: non-routable IP -> standardized protocol ports -> min packets
"""

from __future__ import annotations

import argparse
import glob
import ipaddress
import os
import pickle
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd
from tqdm import tqdm

try:
    from scapy.all import DNS, DNSRR, IP, IPv6, PcapReader, TCP, UDP
except ImportError:
    DNS = DNSRR = IP = IPv6 = PcapReader = TCP = UDP = None  # type: ignore


NON_IOT_TYPES = {"Hub", "Phone", "Computer", "Gateway", "Tablet", "Router", "Game Console", "Unknown"}
PROTOCOL_PORT_BLOCKLIST = {37, 53, 123}
EXTRA_NON_ROUTABLE = (
    "224.0.0.0/4",
    "240.0.0.0/4",
    "255.255.255.255/32",
    "100.64.0.0/10",
    "0.0.0.0/8",
)


def load_pickle(path: str) -> Any:
    with open(path, "rb") as f:
        return pickle.load(f)


def save_pickle(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f)
    os.replace(tmp, path)


def load_device_types(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    df = pd.read_csv(path, dtype=str)
    return dict(zip(df["Device_Name"], df["Type"]))


def load_vendor_map(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    df = pd.read_csv(path, dtype=str)
    return dict(zip(df["Device_Name"].astype(str), df["Vendor"].fillna("unknown").astype(str).str.lower()))


def load_manual_ip_map(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}
    df = pd.read_csv(path, dtype=str)
    return {os.path.normpath(r["Full_Path"]): str(r["Manual_IP"]) for _, r in df.iterrows()}


def parse_ip_from_filename(filename: str) -> Optional[str]:
    for candidate in re.findall(r"(?<!\d)(\d{1,3}_\d{1,3}_\d{1,3}_\d{1,3})(?!\d)", filename):
        parts = candidate.split("_")
        if all(0 <= int(p) <= 255 for p in parts):
            return candidate.replace("_", ".")
    return None


def get_dataset(device_name: str, filename: str) -> str:
    if "_Mon(us)" in device_name:
        return "Mon(IoT)r_us"
    if "_Mon(uk)" in device_name:
        return "Mon(IoT)r_uk"
    if "_IoT-Sentinel" in device_name:
        return "IoT_Sentinel"
    if "_IoTLS" in device_name or "_IoTLS" in filename:
        return "IoTLS"
    if "_YT" in filename:
        return "YourThings"
    if "_Our2" in filename:
        return "NCSU_2022"
    if "_Our" in filename:
        return "NCSU_2021"
    if "_UNSW" in filename:
        return "UNSW"
    return "IoT_LifeCycle"


def build_pcap_tasks(
    root_dirs: Sequence[str],
    manual_ip_csv: Optional[str] = None,
    device_type_csv: Optional[str] = None,
    non_iot_types: Set[str] = NON_IOT_TYPES,
) -> List[Dict[str, str]]:
    manual_ip_map = load_manual_ip_map(manual_ip_csv)
    device_type_map = load_device_types(device_type_csv)
    tasks: List[Dict[str, str]] = []
    skipped_no_ip = 0

    for root_dir in root_dirs:
        for root, _, files in os.walk(root_dir):
            rel = os.path.relpath(root, root_dir)
            if rel == ".":
                continue
            device_name = rel.split(os.sep)[0]
            if device_type_map.get(device_name) in non_iot_types:
                continue

            for filename in files:
                if not filename.endswith(".pcap"):
                    continue
                parts = filename.split("_")
                if len(parts) >= 2 and parts[-2] == "app":
                    continue

                full_path = os.path.join(root, filename)
                device_ip = parse_ip_from_filename(filename)
                if not device_ip:
                    manual_ip = manual_ip_map.get(os.path.normpath(full_path))
                    if not manual_ip or manual_ip == "0":
                        skipped_no_ip += 1
                        continue
                    device_ip = manual_ip

                tasks.append(
                    {
                        "full_path": full_path,
                        "filename": filename,
                        "device_name": device_name,
                        "device_ip": device_ip,
                        "dataset": get_dataset(device_name, filename),
                    }
                )

    print(f"[*] PCAP tasks: {len(tasks):,}; skipped without IP: {skipped_no_ip:,}")
    return tasks


def _decode_dns(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").rstrip(".")
    return str(value).rstrip(".")


def _extract_dns_records(pkt: Any) -> List[Tuple[str, str]]:
    if not (pkt.haslayer(DNS) and pkt.haslayer(DNSRR)):
        return []
    try:
        dns_layer = pkt[DNS]
        cname_map: Dict[str, str] = {}
        a_records: List[Tuple[str, str]] = []
        for i in range(dns_layer.ancount):
            ans = dns_layer.an[i]
            if ans.type == 5:
                cname_map[_decode_dns(ans.rrname)] = _decode_dns(ans.rdata)
            elif ans.type in (1, 28):
                a_records.append((_decode_dns(ans.rdata), _decode_dns(ans.rrname)))

        reverse_cname = {target: alias for alias, target in cname_map.items()}
        out: List[Tuple[str, str]] = []
        for ip_str, name in a_records:
            depth = 0
            while name in reverse_cname and depth <= 10:
                name = reverse_cname[name]
                depth += 1
            out.append((ip_str, name))
        return out
    except Exception:
        return []


def find_domain_at_time(dns_events: Dict[str, List[Tuple[float, str]]], ip: str, flow_start_ts: float) -> Optional[str]:
    events = dns_events.get(ip, [])
    if not events:
        return None
    before = [(ts, d) for ts, d in events if ts <= flow_start_ts]
    if before:
        return max(before, key=lambda x: x[0])[1]
    return min(events, key=lambda x: x[0])[1]


def process_single_pcap(task: Dict[str, str], flow_timeout: float = 120.0) -> Dict[str, Any]:
    if PcapReader is None:
        raise ImportError("scapy is required for PCAP extraction")

    dns_events: DefaultDict[str, List[Tuple[float, str]]] = defaultdict(list)
    flow_buffer: Dict[Tuple[str, str, int, int], Dict[str, Any]] = {}
    completed: List[Dict[str, Any]] = []
    device_ip = task["device_ip"]

    def flush(key: Tuple[str, str, int, int], pkts: List[Dict[str, Any]]) -> None:
        if not pkts:
            return
        proto, remote_ip, device_port, server_port = key
        completed.append(
            {
                "flow_key": key,
                "proto": proto,
                "remote_ip": remote_ip,
                "device_port": device_port,
                "server_port": server_port,
                "flow_start_ts": pkts[0]["ts"],
                "payload_sequence": [p["signed_size"] for p in pkts],
            }
        )

    try:
        with PcapReader(task["full_path"]) as reader:
            for pkt in reader:
                ts = float(pkt.time)
                for ip_str, domain in _extract_dns_records(pkt):
                    dns_events[ip_str].append((ts, domain))

                if IP in pkt:
                    ip_layer = pkt[IP]
                elif IPv6 in pkt:
                    ip_layer = pkt[IPv6]
                else:
                    continue
                if TCP not in pkt and UDP not in pkt:
                    continue

                src, dst = ip_layer.src, ip_layer.dst
                if src != device_ip and dst != device_ip:
                    continue

                is_upload = src == device_ip
                remote_ip = dst if is_upload else src
                proto_obj = TCP if TCP in pkt else UDP
                proto_name = "TCP" if TCP in pkt else "UDP"
                sport, dport = int(pkt[proto_obj].sport), int(pkt[proto_obj].dport)
                device_port, server_port = (sport, dport) if is_upload else (dport, sport)

                key = (proto_name, remote_ip, device_port, server_port)
                signed_size = len(pkt) if is_upload else -len(pkt)
                tcp_flags = int(pkt[TCP].flags) if TCP in pkt else 0

                if key not in flow_buffer:
                    flow_buffer[key] = {"pkts": [], "last_ts": -1.0, "force_new": False}
                buf = flow_buffer[key]

                if buf["force_new"] or (buf["last_ts"] != -1.0 and ts - buf["last_ts"] > flow_timeout):
                    flush(key, buf["pkts"])
                    buf["pkts"] = []
                    buf["force_new"] = False

                buf["pkts"].append({"ts": ts, "signed_size": signed_size})
                buf["last_ts"] = ts

                if proto_name == "TCP" and ((tcp_flags & 0x01) or (tcp_flags & 0x04)):
                    buf["force_new"] = True
    except Exception as exc:
        return {"status": "error", "msg": str(exc), "path": task["full_path"]}

    for key, buf in flow_buffer.items():
        flush(key, buf["pkts"])

    rows = []
    for flow in completed:
        proto, remote_ip, device_port, server_port = flow["flow_key"]
        rows.append(
            {
                "Device": task["device_name"],
                "Device_IP": device_ip,
                "Remote_IP": remote_ip,
                "Protocol": proto,
                "Device_Port": device_port,
                "Server_Port": server_port,
                "Flow_Start_TS": flow["flow_start_ts"],
                "Domain": find_domain_at_time(dns_events, remote_ip, flow["flow_start_ts"]),
                "Payload_Sequence": flow["payload_sequence"],
                "Pcap_Filename": task["filename"],
                "Source_Full_Path": task["full_path"],
            }
        )
    return {"status": "success", "data": rows, "path": task["full_path"]}


def _worker(args: Tuple[Dict[str, str], float]) -> Dict[str, Any]:
    return process_single_pcap(args[0], args[1])


def extract_pcaps(
    root_dirs: Sequence[str],
    output_pickle: str,
    manual_ip_csv: Optional[str] = None,
    device_type_csv: Optional[str] = None,
    checkpoint_log: Optional[str] = None,
    workers: int = 1,
    flow_timeout: float = 120.0,
    save_interval: int = 200,
) -> None:
    tasks = build_pcap_tasks(root_dirs, manual_ip_csv, device_type_csv)
    processed = set()
    if checkpoint_log and os.path.exists(checkpoint_log):
        with open(checkpoint_log, "r", encoding="utf-8") as f:
            processed = {line.strip() for line in f if line.strip()}
    tasks = [t for t in tasks if t["full_path"] not in processed]

    batch: List[Dict[str, Any]] = []
    batch_id = len(glob.glob(f"{output_pickle}.batch_*"))
    ok = err = total = 0

    def handle(result: Dict[str, Any]) -> None:
        nonlocal batch, batch_id, ok, err, total
        if result["status"] == "success":
            batch.extend(result.get("data", []))
            total += len(result.get("data", []))
            ok += 1
            if checkpoint_log:
                with open(checkpoint_log, "a", encoding="utf-8") as f:
                    f.write(result["path"] + "\n")
        else:
            err += 1
            print(f"[ERR] {result.get('msg')} -> {result['path']}")

        if ok and ok % save_interval == 0:
            save_pickle(batch, f"{output_pickle}.batch_{batch_id:04d}")
            batch = []
            batch_id += 1

    if workers <= 1:
        for task in tqdm(tasks, desc="Extracting"):
            handle(process_single_pcap(task, flow_timeout))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_worker, (t, flow_timeout)) for t in tasks]
            for fut in tqdm(as_completed(futures), total=len(futures), desc="Extracting"):
                handle(fut.result())

    if batch:
        save_pickle(batch, f"{output_pickle}.batch_{batch_id:04d}")
    print(f"[+] PCAP ok={ok:,}, err={err:,}, flows={total:,}")


def merge_batches(batch_prefix: str, output_pickle: str) -> None:
    merged: List[Dict[str, Any]] = []
    for path in tqdm(sorted(glob.glob(f"{batch_prefix}.batch_*")), desc="Merging"):
        obj = load_pickle(path)
        merged.extend(obj if isinstance(obj, list) else list(obj))
    save_pickle(merged, output_pickle)
    print(f"[+] merged {len(merged):,} flows -> {output_pickle}")


def is_non_routable_ip(ip_str: str, extra_ranges: Sequence[str] = EXTRA_NON_ROUTABLE) -> bool:
    if not ip_str:
        return True
    try:
        ip_obj = ipaddress.ip_address(str(ip_str))
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return True
        if ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
            return True
        if isinstance(ip_obj, ipaddress.IPv4Address):
            return any(ip_obj in ipaddress.ip_network(net) for net in extra_ranges)
        return False
    except ValueError:
        return True


def is_standardized_protocol(server_port: Any, blocklist: Set[int] = PROTOCOL_PORT_BLOCKLIST) -> bool:
    try:
        return int(server_port) in blocklist
    except (TypeError, ValueError):
        return False


def has_min_bidirectional_packets(seq: Sequence[int], min_packet_count: int) -> bool:
    return sum(1 for x in seq if x > 0) >= min_packet_count and sum(1 for x in seq if x < 0) >= min_packet_count


def filter_flows(
    input_pickle: str,
    output_pickle: str,
    device_list_csv: Optional[str] = None,
    min_packet_count: int = 5,
    block_ports: Set[int] = PROTOCOL_PORT_BLOCKLIST,
    extra_non_routable: Sequence[str] = EXTRA_NON_ROUTABLE,
) -> None:
    obj = load_pickle(input_pickle)
    flows = obj if isinstance(obj, list) else obj.to_dict(orient="records")
    vendor_map = load_vendor_map(device_list_csv)

    stats = defaultdict(int)
    cleaned: List[Dict[str, Any]] = []
    for flow in tqdm(flows, desc="Filtering"):
        stats["input"] += 1
        if is_non_routable_ip(flow.get("Remote_IP", ""), extra_non_routable):
            stats["drop_non_routable"] += 1
            continue
        if is_standardized_protocol(flow.get("Server_Port", ""), block_ports):
            stats["drop_standardized_protocol"] += 1
            continue
        if not has_min_bidirectional_packets(flow.get("Payload_Sequence", []), min_packet_count):
            stats["drop_short_flow"] += 1
            continue
        if vendor_map:
            flow = dict(flow)
            flow["Vendor"] = vendor_map.get(flow.get("Device", ""), "unknown")
        cleaned.append(flow)

    stats["kept"] = len(cleaned)
    save_pickle(cleaned, output_pickle)
    print(dict(stats))
    print(f"[+] saved {len(cleaned):,} flows -> {output_pickle}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCAP extraction and flow filtering.")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("extract")
    p1.add_argument("--root-dirs", nargs="+", required=True)
    p1.add_argument("--output-pickle", required=True)
    p1.add_argument("--manual-ip-csv", default=None)
    p1.add_argument("--device-type-csv", default=None)
    p1.add_argument("--checkpoint-log", default=None)
    p1.add_argument("--workers", type=int, default=1)
    p1.add_argument("--flow-timeout", type=float, default=120.0)
    p1.add_argument("--save-interval", type=int, default=200)

    p2 = sub.add_parser("merge")
    p2.add_argument("--batch-prefix", required=True)
    p2.add_argument("--output-pickle", required=True)

    p3 = sub.add_parser("filter")
    p3.add_argument("--input-pickle", required=True)
    p3.add_argument("--output-pickle", required=True)
    p3.add_argument("--device-list-csv", default=None)
    p3.add_argument("--min-packet-count", type=int, default=5)
    p3.add_argument("--block-ports", nargs="*", type=int, default=sorted(PROTOCOL_PORT_BLOCKLIST))
    p3.add_argument("--extra-non-routable", nargs="*", default=list(EXTRA_NON_ROUTABLE))

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "extract":
        extract_pcaps(
            args.root_dirs, args.output_pickle, args.manual_ip_csv, args.device_type_csv,
            args.checkpoint_log, args.workers, args.flow_timeout, args.save_interval,
        )
    elif args.command == "merge":
        merge_batches(args.batch_prefix, args.output_pickle)
    elif args.command == "filter":
        filter_flows(
            args.input_pickle, args.output_pickle, args.device_list_csv,
            args.min_packet_count, set(args.block_ports), tuple(args.extra_non_routable),
        )


if __name__ == "__main__":
    main()
