"""Read the seven experimental phases and preserve their original validation rules."""

import json
from pathlib import Path
from validation import validate_anchor, validate_shape, unique_json_object

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def records():
    for phase, folder, question_file in [
        (
            "discovery_array",
            "D/results/calls/evidence_decision",
            "D/data/anchor_inputs.json",
        ),
        (
            "discovery_keyed",
            "D/results/keyed/calls/evidence_decision",
            "D/data/anchor_inputs.json",
        ),
        ("exploratory", "E/results/calls/P10_factorial", "E/data/trace_inputs.json"),
        (
            "order_control",
            "E/results/calls/P10_order_control",
            "E/data/trace_inputs.json",
        ),
        (None, "H/calls", "H/data/questions.json"),
        ("identity_control", "R/calls", "R/data/questions.json"),
    ]:
        questions = {q["id"]: q for q in read(ROOT / "data" / question_file)}
        for path in sorted((ROOT / "data" / folder).glob("*.json")):
            record = read(path)
            actual_phase = phase or record["job"]["study"]
            shown = json.loads(record["request"]["messages"][1]["content"])["questions"]
            yield actual_phase, path, record, [questions[q["id"]] for q in shown]


def validate(phase, record, questions):
    errors = []
    answers = {}
    parsed = None
    try:
        response = record["response"]
        if response is None:
            return ["transport"], answers
        if response.get("done_reason") == "length":
            errors.append("truncated")
        kwargs = (
            {}
            if phase == "discovery_array"
            else {"object_pairs_hook": unique_json_object}
        )
        parsed = json.loads(response["message"]["content"], **kwargs)
        if phase == "discovery_array":
            normalized = parsed
        else:
            if phase == "discovery_keyed":
                if (
                    set(parsed) != {"answers"}
                    or not isinstance(parsed["answers"], dict)
                    or set(parsed["answers"]) != {q["id"] for q in questions}
                ):
                    errors.append("keyed_schema")
            else:
                validate_shape(parsed, record["request"]["format"])
            normalized = {
                "answers": [dict(id=q, **a) for q, a in parsed["answers"].items()]
            }
        condition = record["job"].get("condition", "structured")
        flags, answers = validate_anchor(normalized, questions, condition)
        errors.extend(flags["batch"])
    except Exception as exc:
        errors.append(type(exc).__name__ + ":" + str(exc))
    return errors, answers
