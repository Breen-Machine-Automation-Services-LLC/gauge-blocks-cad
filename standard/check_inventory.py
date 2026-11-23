"""Verify item identity, source URLs, intent links, evidence and rebuild equality."""

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re

from build_inventory import DEFAULT_REPO, HERE, build, read_intents
from reference_catalog import catalog


def validate(records, intents):
    keys = [(record["kind"], record["name"]) for record in records]
    assert len(keys) == len(set(keys)), "Duplicate (kind, name)"
    expected = {(record["kind"], record["name"]) for record in catalog()}
    assert set(keys) == expected, f"Catalog mismatch: missing={expected - set(keys)}, extra={set(keys) - expected}"
    urls = {(record["kind"], record["name"]): record["reference_url"] for record in catalog()}
    for record in records:
        key = record["kind"], record["name"]
        assert record.get("reference_url"), f"Missing URL: {key}"
        assert record["reference_url"] == urls[key], f"Wrong owning item URL: {key}"
        assert re.fullmatch(r"https://help\.autodesk\.com/cloudhelp/\d{4}/ENU/AutoCAD-DXF/files/GUID-[A-F0-9-]+\.htm", record["reference_url"]), key
        dataset = record["dataset"]
        assert dataset["status"] in ("included", "partial", "present", "future", "omitted"), key
        assert dataset["intents"] == sorted(set(dataset["intents"])), key
        assert set(dataset["intents"]) <= set(intents), f"Unknown intent: {key}"
        assert dataset["note"] and "\n" not in dataset["note"], key
        assert not any(0xE000 <= ord(character) <= 0xF8FF for character in json.dumps(record, ensure_ascii=False)), key
        if dataset["status"] == "omitted":
            assert not dataset["intents"], key
        else:
            assert dataset["intents"], key


def self_test(records, intents):
    mutations = []
    duplicate = copy.deepcopy(records)
    duplicate.append(copy.deepcopy(duplicate[0]))
    mutations.append(duplicate)
    for mutate in (lambda rows: rows.pop(), lambda rows: rows[0].pop("reference_url"),
                   lambda rows: rows[0]["dataset"].update(intents=["nonexistent_intent"]),
                   lambda rows: rows[0].update(reference_url="https://example.com/not-autodesk")):
        bad = copy.deepcopy(records)
        mutate(bad)
        mutations.append(bad)
    for mutation in mutations:
        try:
            validate(mutation, intents)
        except (AssertionError, KeyError):
            continue
        raise AssertionError("Checker accepted an intentionally invalid inventory")
    return len(mutations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    args = parser.parse_args()
    records = json.loads((HERE / "dxf-inventory.json").read_text())
    intents = read_intents(args.repo)
    validate(records, intents)
    rebuilt, _ = build(args.repo)
    assert records == rebuilt, "Inventory differs from current repository analysis"
    print(dict(result="PASS", records=len(records), invalid_mutations_rejected=self_test(records, intents)))


if __name__ == "__main__":
    main()
