import pandas as pd

from src.overlap_analysis import CATEGORY_ORDER, run_overlap_analysis, summarize_overlap


def test_released_overlap_outputs_match_table_vi():
    details = run_overlap_analysis(
        "outputs/documentary_groups.csv",
        "outputs/endpoint_groups.csv",
        "outputs/behavior_groups.csv",
    )
    summary = summarize_overlap(details)

    assert len(details) == 36 + 69 + 81
    assert details["Source"].value_counts().to_dict() == {
        "D1": 36,
        "D2": 69,
        "D3": 81,
    }
    assert summary["Category"].tolist() == CATEGORY_ORDER
    assert dict(zip(summary["Category"], summary["Groups"])) == {
        "D1&D2&D3": 17,
        "D1&D2\\D3": 35,
        "D1&D3\\D2": 26,
        "D2&D3\\D1": 18,
        "D1_only": 36,
        "D2_only": 26,
        "D3_only": 28,
    }

    released_details = pd.read_csv("outputs/overlap_details.csv")
    released_summary = pd.read_csv("outputs/overlap_summary.csv")
    pd.testing.assert_frame_equal(released_details, details)
    pd.testing.assert_frame_equal(released_summary, summary)
