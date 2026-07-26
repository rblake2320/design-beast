import json
from pathlib import Path


def test_fixed_multimodal_suite_counts_and_sources():
    bench = Path(__file__).resolve().parents[1]
    briefs = json.loads((bench / "briefs.json").read_text())["image_briefs"]
    source_ids = {row["id"] for row in briefs}
    suite = json.loads((bench / "multimodal_tasks.json").read_text())
    expected = {"edit_tasks": 20, "i2v_tasks": 15, "i23d_tasks": 15}
    all_ids = []
    for group, count in expected.items():
        rows = suite[group]
        assert len(rows) == count
        assert all(row["source_brief"] in source_ids for row in rows)
        assert all(row.get("criterion", "").strip() for row in rows)
        all_ids.extend(row["id"] for row in rows)
    assert len(all_ids) == len(set(all_ids)) == 50
