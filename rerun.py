"""Replay preserved requests into a new directory; never overwrite the study records."""

import argparse, datetime, hashlib, json, time, urllib.request
from pathlib import Path
from records import ROOT, records, validate


def api(base, endpoint, payload=None):
    request = urllib.request.Request(
        base.rstrip("/") + "/api/" + endpoint,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=1800) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://localhost:11434")
    parser.add_argument(
        "--phase",
        choices=[
            "discovery_array",
            "discovery_keyed",
            "exploratory",
            "order_control",
            "replication",
            "singleton",
            "identity_control",
        ],
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("Use an output directory outside the immutable artifact.")
    selected = [x for x in records() if x[0] == args.phase]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        selected = selected[: args.limit]
    models = json.loads((ROOT / "model_artifacts.json").read_text())
    tags = {
        m["name"]: m["digest"].removeprefix("sha256:")
        for m in api(args.endpoint, "tags")["models"]
    }
    for name in {r["job"]["model"] for _, _, r, _ in selected}:
        if tags.get(name) != models[name]["digest"].removeprefix("sha256:"):
            raise RuntimeError("Recorded model digest unavailable for " + name)
    if api(args.endpoint, "version")["version"] != "0.34.4":
        raise RuntimeError("Exact replay requires recorded Ollama version 0.34.4")
    output.mkdir(parents=True, exist_ok=True)
    for phase, path, original, questions in selected:
        target = output / (phase + "_" + path.name)
        if target.exists():
            previous = json.loads(target.read_text())
            if previous["request_sha256"] != original["request_sha256"]:
                raise RuntimeError("Resume hash mismatch")
            continue
        started = time.perf_counter()
        record = {k: original[k] for k in ["job", "request", "request_sha256"]}
        record["response"] = None
        transport = None
        try:
            record["response"] = api(args.endpoint, "chat", record["request"])
        except Exception as exc:
            transport = str(exc)
        errors, answers = validate(phase, record, questions)
        record.update(
            errors=errors,
            validated={"answers": answers},
            wall_seconds=time.perf_counter() - started,
            completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            replay_of_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            transport_detail=transport,
        )
        with target.open("x") as handle:
            json.dump(record, handle, indent=2, ensure_ascii=False)
        print(
            phase, record["job"]["id"], "batch_failed=" + str(bool(errors)), flush=True
        )


if __name__ == "__main__":
    main()
