from __future__ import annotations

from pathlib import Path

from app.services.levels_fyi import parse_levels_md

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_levels_russia_md() -> None:
    text = (FIXTURES / "levels_fyi_russia.md").read_text(encoding="utf-8")
    row = parse_levels_md(
        text,
        key="swe_russia",
        label="Software Engineer · Russia",
        html_path="/t/software-engineer/locations/russia",
        md_path="/t/software-engineer/locations/russia.md",
    )
    assert row is not None
    assert row.median == 3_877_113
    assert row.p25 == 2_762_962
    assert row.p75 == 5_086_353
    monthly = row.as_monthly()
    assert monthly["median"] == round(3_877_113 / 12)
    assert monthly["p25"] == round(2_762_962 / 12)
    payload = row.to_dict()
    assert payload["source"] == "levels.fyi"
    assert "Levels.fyi" in payload["attribution"]
