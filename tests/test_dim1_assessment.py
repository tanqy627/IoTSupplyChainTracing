import pandas as pd

from src.dim1_assessment import run_dim1_assessment


def test_dim1_assessment_builds_candidates_and_uses_cache(tmp_path):
    pd.DataFrame([
        {"Device_Name": "A_YT", "Vendor": "Vendor A"},
        {"Device_Name": "B_YT", "Vendor": "Vendor B"},
    ]).to_csv(tmp_path / "devices.csv", index=False)
    pd.DataFrame([
        {"Device_Name": "A_YT", "Type": "Speaker"},
        {"Device_Name": "B_YT", "Type": "Speaker"},
    ]).to_csv(tmp_path / "types.csv", index=False)

    calls = []

    def fake_llm(prompt, schema):
        calls.append(prompt)
        if "Vendor 1" in prompt:
            parsed = {
                "is_related": True,
                "connection_type": "Technical Integration",
                "technical_link": "Amazon Alexa",
                "reason": "documented",
            }
        else:
            parsed = {"is_related": True, "reason": "documented"}
        return {"parsed": parsed, "raw_text": "{}", "model": "test"}

    result = run_dim1_assessment(
        str(tmp_path / "devices.csv"), str(tmp_path / "types.csv"),
        str(tmp_path / "out"), fake_llm, str(tmp_path / "cache"),
    )
    assert len(result) == 1
    assert result.loc[0, "Connection_Type"] == "Technical Integration"
    assert result.loc[0, "Devices"] == "A_YT|B_YT"
    assert len(calls) == 3  # one vendor pair and two vendor/type checks

    run_dim1_assessment(
        str(tmp_path / "devices.csv"), str(tmp_path / "types.csv"),
        str(tmp_path / "out2"), fake_llm, str(tmp_path / "cache"),
    )
    assert len(calls) == 3
