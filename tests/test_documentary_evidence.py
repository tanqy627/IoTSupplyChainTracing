import pandas as pd

from src.documentary_evidence import (
    DOCUMENTARY_GROUP_COLUMNS,
    PROMPT_STAGE1,
    PROMPT_STAGE2,
    load_documentary_groups,
    normalize_documentary_groups,
)


def test_released_documentary_groups_match_reported_results():
    groups = load_documentary_groups("outputs/documentary_groups.csv")

    assert list(groups.columns) == DOCUMENTARY_GROUP_COLUMNS
    assert len(groups) == 36
    assert groups["Connection_Type"].value_counts().to_dict() == {
        "Technical Integration": 28,
        "Corporate Affiliation": 8,
    }


def test_normalization_accepts_legacy_schema_and_preserves_provider_fields(tmp_path):
    source = pd.DataFrame(
        [{
            "Group_ID": "legacy-1",
            "Platform": "Works with Alexa",
            "Relationship_Type": "Ecosystem",
            "Num_Vendors": 2,
            "Num_Devices": 2,
            "Vendors": "A|B",
            "Devices": "device-a|device-b",
            "provider": "Amazon",
            "provider_role": "IoT Platform Provider",
            "provider_subrole": "",
        }]
    )
    input_csv = tmp_path / "legacy.csv"
    output_csv = tmp_path / "normalized.csv"
    source.to_csv(input_csv, index=False)

    result = normalize_documentary_groups(str(input_csv), str(output_csv))

    assert list(result.columns) == DOCUMENTARY_GROUP_COLUMNS
    assert result.loc[0, "Cluster_ID"] == "legacy-1"
    assert result.loc[0, "Tech_Link"] == "Amazon Alexa"
    assert result.loc[0, "Connection_Type"] == "Technical Integration"
    assert result.loc[0, "Provider"] == "Amazon"
    assert result.loc[0, "Provider_Role"] == "IoT Platform Provider"


def test_prompts_match_appendix_terminology():
    stage2_single_line = " ".join(PROMPT_STAGE2.split())
    assert "Corporate Affiliation" in PROMPT_STAGE1
    assert "Technical Integration" in PROMPT_STAGE1
    assert '"connection_type"' in PROMPT_STAGE1
    assert '"technical_link"' in PROMPT_STAGE1
    assert "Ecosystem" not in PROMPT_STAGE1
    assert "Parent/Subsidiary" not in PROMPT_STAGE1
    assert 'Tech-link: "{technical_link}"' in PROMPT_STAGE2
    assert "depend on, or interoperate through" in stage2_single_line
