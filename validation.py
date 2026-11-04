"""Historical validation semantics, isolated from local execution code."""

import json

ANSWER = {"required": ["id", "label", "confidence", "evidence_ids"]}


def validate_anchor(parsed, shown, condition):
    issues = []
    answers = {}
    expected = {t["id"]: t for t in shown}
    if (
        not isinstance(parsed, dict)
        or set(parsed) != {"answers"}
        or not isinstance(parsed["answers"], list)
    ):
        return {"batch": ["schema"]}, {}
    for a in parsed["answers"]:
        if not isinstance(a, dict) or set(a) != set(ANSWER["required"]):
            issues.append("answer_schema")
            continue
        ident = a["id"]
        if ident not in expected:
            issues.append("unknown_id")
            continue
        if ident in answers:
            issues.append("duplicate_id")
            continue
        err = []
        t = expected[ident]
        if a["label"] not in ["link", "nonlink", "uncertain"]:
            err.append("label")
        if type(a["confidence"]) is not int or not 0 <= a["confidence"] <= 100:
            err.append("confidence")
        visible = (
            {t["target_sentence_id"]}
            if condition == "target_only"
            else {x["sentence_id"] for x in t["context"]}
        )
        if (
            not isinstance(a["evidence_ids"], list)
            or len(a["evidence_ids"]) > 3
            or any(type(s) is not int or s not in visible for s in a["evidence_ids"])
        ):
            err.append("citation")
        if a["label"] == "link" and not a["evidence_ids"]:
            err.append("link_without_evidence")
        answers[ident] = {
            "parsed": a,
            "errors": err,
            "label": a["label"] if not err else "uncertain",
        }
    if set(answers) != set(expected):
        issues.append("missing_ids")
    return {"batch": issues}, answers


def validate_shape(value, schema, path="$"):
    """Independent validator for exactly the JSON Schema vocabulary used here."""
    expected = {"object": dict, "array": list, "string": str, "integer": int}[
        schema["type"]
    ]
    if type(value) is not expected:
        raise ValueError("schema_type:" + path)
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("schema_enum:" + path)
    if type(value) is dict:
        if not set(schema.get("required", [])) <= set(value):
            raise ValueError("schema_required:" + path)
        if schema.get("additionalProperties") is False and not set(value) <= set(
            schema["properties"]
        ):
            raise ValueError("schema_extra:" + path)
        for k, v in value.items():
            validate_shape(v, schema["properties"][k], path + "." + k)
    if type(value) is list:
        if len(value) > schema.get("maxItems", float("inf")):
            raise ValueError("schema_maxItems:" + path)
        for i, v in enumerate(value):
            validate_shape(v, schema["items"], path + "[" + str(i) + "]")
    if type(value) is int:
        if value < schema.get("minimum", float("-inf")) or value > schema.get(
            "maximum", float("inf")
        ):
            raise ValueError("schema_range:" + path)


def unique_json_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate_json_object_key:" + k)
        result[k] = v
    return result
