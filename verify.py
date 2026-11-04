"""Audit immutable inputs and independently revalidate all 624 raw responses."""

import csv, hashlib, json
from pathlib import Path
from records import ROOT, records, validate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for item in manifest["files"]:
        assert digest(ROOT / item["path"]) == item["sha256"], item["path"]
    count = items = 0
    for phase, path, record, questions in records():
        assert (
            hashlib.sha256(canonical(record["request"])).hexdigest()
            == record["request_sha256"]
        ), path
        errors, answers = validate(phase, record, questions)
        assert bool(errors) == bool(record["errors"]), (
            phase,
            path,
            errors,
            record["errors"],
        )
        for q in questions:
            new = answers.get(q["id"])
            old = record.get("validated", {}).get("answers", {}).get(q["id"])
            newvalid = bool(not errors and new and not new["errors"])
            oldvalid = bool(not record["errors"] and old and not old["errors"])
            assert newvalid == oldvalid, (path, q["id"])
            assert (new["label"] if newvalid else "uncertain") == (
                old["label"] if oldvalid else "uncertain"
            ), path
            items += 1
        count += 1
    assert (count, items) == (624, 6288)
    expected = {f.name: digest(f) for f in (ROOT / "expected").glob("*.csv")}
    actual = {f.name: digest(f) for f in (ROOT / "output").glob("*.csv")}
    assert expected == actual, "Regenerated CSVs differ from the preserved analysis"
    result = {
        "status": "PASS",
        "raw_calls_revalidated": count,
        "item_decisions_revalidated": items,
        "matching_csv_files": len(expected),
        "manifest_files_verified": len(manifest["files"]),
    }
    (ROOT / "output/verification.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
