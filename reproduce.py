"""Generate manuscript tables and vector figures from actual preserved records."""

import csv, html, json, os, re, shutil, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})
ROOT = Path(__file__).resolve().parent
TEX = ROOT / "output"
DISC = ROOT / "data/D"
EXPL = ROOT / "data/E"
REPL = ROOT / "data/H"
IDENTITY = ROOT / "data/R"
PHASE_LABEL = {"exploratory": "$E$", "replication": "$H$", "identity_control": "$R$"}
NAMES = {
    "gpt-oss:20b": "GPT-OSS",
    "mistral-small:24b": "Mistral",
    "gemma4:26b": "Gemma",
}
FAMS = ["bigbluebutton", "jabref", "teammates", "mediastore", "teastore"]
SHORT = {
    "bigbluebutton": "BBB",
    "jabref": "JR",
    "teammates": "TM",
    "mediastore": "MS",
    "teastore": "TS",
}
CELLS = [("prose", False), ("prose", True), ("structured", False), ("structured", True)]
read = lambda p: json.loads(Path(p).read_text())


def esc(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def pp(v):
    return f"{100*(0.0 if abs(v)<1e-9 else v):+.1f}"


def dump(name, rows):
    p = ROOT / "output" / name
    p.parent.mkdir(exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(
            sorted(
                rows, key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False)
            )
        )


def table(name, columns, header, rows):
    text = (
        r"\begin{tabular}{"
        + columns
        + r"}\toprule"
        + "\n"
        + header
        + r"\\\midrule"
        + "\n"
        + "\n".join(" & ".join(str(v) for v in r) + r"\\" for r in rows)
        + "\n"
        + r"\bottomrule\end{tabular}"
        + "\n"
    )
    (TEX / "tables" / name).write_text(text)


def newobs(record, ids, gold, phase, **fields):
    out = []
    for qid in ids:
        a = record.get("validated", {}).get("answers", {}).get(qid)
        valid = bool(not record["errors"] and a and not a["errors"])
        pred = a["label"] if valid else "uncertain"
        state = (
            "batch_failure"
            if record["errors"]
            else (
                "item_invalid"
                if not valid
                else "explicit_uncertain" if pred == "uncertain" else "definitive"
            )
        )
        out.append(
            dict(
                phase=phase,
                model=record["job"]["model"],
                seed=record["job"]["seed"],
                id=qid,
                reference=gold[qid],
                prediction=pred,
                valid=valid,
                definitive=valid and pred != "uncertain",
                correct=int(pred == gold[qid]),
                state=state,
                job_id=record["job"]["id"],
                **fields,
            )
        )
    return out


def load():
    observations = []
    callrows = []
    ditems = read(DISC / "data/anchor_inputs.json")
    dgold = read(DISC / "private/anchor_labels.json")
    for contract, folder in [
        ("array", DISC / "results/calls/evidence_decision"),
        ("keyed", DISC / "results/keyed/calls/evidence_decision"),
    ]:
        records = [read(p) for p in folder.glob("*.json")]
        assert len(records) == 72
        for r in records:
            j = r["job"]
            ids = [x["id"] for x in ditems if x["cohort"] == j["cohort"]]
            observations += newobs(
                r,
                ids,
                dgold,
                "discovery_" + contract,
                family=j["cohort"].rsplit("_", 1)[0],
                condition=j["condition"],
                layout="NA",
                linked="NA",
                trial="primary",
            )
            callrows.append(
                dict(
                    phase="discovery_" + contract,
                    model=j["model"],
                    seed=j["seed"],
                    family=j["cohort"].rsplit("_", 1)[0],
                    condition=j["condition"],
                    layout="NA",
                    linked="NA",
                    failure=bool(r["errors"]),
                    id=j["id"],
                    wall_seconds=r["wall_seconds"],
                )
            )
    eitems = {x["id"]: x for x in read(EXPL / "data/trace_inputs.json")}
    egold = read(EXPL / "private/trace_gold.json")
    batches = read(EXPL / "data/batches.json")
    for study, phase in [
        ("P10_factorial", "exploratory"),
        ("P10_order_control", "order_control"),
    ]:
        records = [read(p) for p in (EXPL / "results/calls" / study).glob("*.json")]
        assert len(records) == (128 if phase == "exploratory" else 32)
        for r in records:
            j = r["job"]
            ids = batches[j["batch"]]
            observations += newobs(
                r,
                ids,
                egold,
                phase,
                family=eitems[ids[0]]["family"],
                condition="NA",
                layout=j["layout"],
                linked=j["linked"],
                trial=j["trial"],
            )
            callrows.append(
                dict(
                    phase=phase,
                    model=j["model"],
                    seed=j["seed"],
                    family=eitems[ids[0]]["family"],
                    condition="NA",
                    layout=j["layout"],
                    linked=j["linked"],
                    failure=bool(r["errors"]),
                    id=j["id"],
                    wall_seconds=r["wall_seconds"],
                )
            )
    primary_done = (REPL / "status.json").exists() and read(REPL / "status.json")[
        "status"
    ] == "completed"
    identity_done = (IDENTITY / "status.json").exists() and read(
        IDENTITY / "status.json"
    )["status"] == "completed"
    if primary_done:
        gold = read(REPL / "private/gold.json")
        records = [read(p) for p in (REPL / "calls").glob("*.json")]
        assert len(records) == 200
        for r in records:
            j = r["job"]
            observations += newobs(
                r,
                j["ids"],
                gold,
                j["study"],
                family=j["family"],
                condition="NA",
                layout=j["layout"],
                linked=j["linked"],
                trial="primary",
            )
            callrows.append(
                dict(
                    phase=j["study"],
                    model=j["model"],
                    seed=j["seed"],
                    family=j["family"],
                    condition="NA",
                    layout=j["layout"],
                    linked=j["linked"],
                    failure=bool(r["errors"]),
                    id=j["id"],
                    wall_seconds=r["wall_seconds"],
                )
            )
    if identity_done:
        gold = read(IDENTITY / "private/gold.json")
        records = [read(p) for p in (IDENTITY / "calls").glob("*.json")]
        assert len(records) == 120
        for r in records:
            j = r["job"]
            observations += newobs(
                r,
                j["ids"],
                gold,
                "identity_control",
                family=j["family"],
                condition="NA",
                layout=j["layout"],
                linked=j["linked"],
                trial="primary",
            )
            callrows.append(
                dict(
                    phase="identity_control",
                    model=j["model"],
                    seed=j["seed"],
                    family=j["family"],
                    condition="NA",
                    layout=j["layout"],
                    linked=j["linked"],
                    failure=bool(r["errors"]),
                    id=j["id"],
                    wall_seconds=r["wall_seconds"],
                )
            )
    return observations, callrows, primary_done and identity_done


def design_figure():
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(4.724, 2.95))
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    ax.axis("off")
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 2)
    boxes = [
        (0.02, 1.15, "Fixed pair\nand context"),
        (1.04, 1.15, "Four input cells\nPU / PL / SU / SL"),
        (2.06, 1.15, "Local model\nFixed schema"),
        (2.06, 0.1, "Batch and item\nvalidation"),
        (1.04, 0.1, "All-attempted\nscore / coverage"),
        (0.02, 0.1, "Paired contrasts\nValidity partition"),
    ]
    for x, y, label in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                0.9,
                0.68,
                boxstyle="round,pad=0.015",
                facecolor="#f4f4f4",
                edgecolor="#444444",
            )
        )
        ax.text(x + 0.45, y + 0.34, label, ha="center", va="center", fontsize=10)
    for start, end in [
        ((0.94, 1.49), (1.02, 1.49)),
        ((1.96, 1.49), (2.04, 1.49)),
        ((2.51, 1.13), (2.51, 0.80)),
        ((2.04, 0.44), (1.96, 0.44)),
        ((1.02, 0.44), (0.94, 0.44)),
    ]:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={"arrowstyle": "->", "color": "#333333"},
        )
    fig.savefig(TEX / "figures/design.pdf")
    plt.close(fig)


def build():
    (ROOT / "output").mkdir(exist_ok=True)
    for f in ["tables", "figures"]:
        (TEX / f).mkdir(exist_ok=True)
    obs, calls, complete = load()
    dump("all_observations.csv", obs)
    dump("all_call_accounting.csv", calls)
    metric_groups = defaultdict(list)
    for r in obs:
        if r["phase"] in ["exploratory", "replication", "identity_control"]:
            metric_groups[
                (
                    r["phase"],
                    r["model"],
                    r["seed"],
                    r["family"],
                    r["layout"],
                    r["linked"],
                )
            ].append(r)
    metrics = []
    for key, rr in sorted(metric_groups.items()):
        n = len(rr)
        correct = sum(r["correct"] for r in rr)
        definitive = sum(r["definitive"] for r in rr)
        row = dict(zip(["phase", "model", "seed", "family", "layout", "linked"], key))
        row.update(
            n=n,
            correct=correct,
            correct_fraction_all=correct / n,
            definitive=definitive,
            coverage=definitive / n,
            correct_fraction_definitive=correct / definitive if definitive else "",
            batch_failure_items=sum(r["state"] == "batch_failure" for r in rr),
            item_invalid=sum(r["state"] == "item_invalid" for r in rr),
            explicit_uncertain=sum(r["state"] == "explicit_uncertain" for r in rr),
        )
        for label in ["link", "nonlink"]:
            selected = [r for r in rr if r["reference"] == label]
            row[label + "_reference_n"] = len(selected)
            row[label + "_correct"] = sum(r["correct"] for r in selected)
            row[label + "_recall"] = (
                sum(r["correct"] for r in selected) / len(selected) if selected else ""
            )
        metrics.append(row)
    dump("all_factorial_metrics.csv", metrics)
    cohorts = read(REPL / "data/cohorts.json")
    table(
        "cohort.tex",
        "lrrrr",
        "Project & Year & Sent. & Comp. & Links",
        [
            [
                {
                    "bigbluebutton": "BigBlueButton",
                    "jabref": "JabRef",
                    "teammates": "TEAMMATES",
                    "mediastore": "MediaStore",
                    "teastore": "TeaStore",
                }[r["family"]],
                r["year"],
                r["sentences"],
                r["components"],
                r["published_positive_links"],
            ]
            for r in cohorts
        ],
    )
    dr = []
    for model in ["gpt-oss:20b", "mistral-small:24b"]:
        for seed in [17, 43]:
            for condition in ["target_only", "unstructured", "structured"]:
                rows = []
                for phase in ["discovery_array", "discovery_keyed"]:
                    oo = [
                        r
                        for r in obs
                        if r["phase"] == phase
                        and r["model"] == model
                        and r["seed"] == seed
                        and r["condition"] == condition
                    ]
                    cc = [
                        r
                        for r in calls
                        if r["phase"] == phase
                        and r["model"] == model
                        and r["seed"] == seed
                        and r["condition"] == condition
                    ]
                    assert len(oo) == 72 and len(cc) == 6
                    rows.append(
                        (sum(r["correct"] for r in oo), sum(r["failure"] for r in cc))
                    )
                dr.append(
                    [
                        NAMES[model],
                        seed,
                        {"target_only": "T", "unstructured": "P", "structured": "S"}[
                            condition
                        ],
                        rows[0][0],
                        rows[1][0],
                        rows[0][1],
                    ]
                )
    table(
        "discovery.tex",
        "llcrrr",
        "Model & Seed & Input & Array & Keyed & Array fail",
        dr,
    )
    armrows = []
    for phase, label, q, f, m, s, b, n in [
        ("discovery_array", "$D$: array", 72, 3, 2, 2, 12, 72),
        ("discovery_keyed", "$D$: keyed", 72, 3, 2, 2, 12, 72),
        ("exploratory", "$E$: factorial", 80, 2, 2, 2, 10, 128),
        ("order_control", "$E$: order/repeat", 20, 2, 2, 1, 10, 32),
        ("replication", "$H$: factorial", 60, 5, 3, 2, 12, 120),
        ("singleton", "$H$: singleton", 10, 5, 2, 1, 1, 80),
        ("identity_control", "$R$: remapped", 60, 5, 3, 2, 12, 120),
    ]:
        selected = [r for r in calls if r["phase"] == phase]
        bad = sum(r["failure"] for r in selected) if selected else "pending"
        armrows.append([label, q, f, m, s, b, n, bad])
    table(
        "arms.tex",
        "lrrrrrrr",
        "Arm & Pairs & Proj. & Models & Seeds & Batch & Calls & Failed",
        armrows,
    )
    outcomes = []
    for phase in ["exploratory", "identity_control"]:
        for model in ["gpt-oss:20b", "mistral-small:24b"] + (
            ["gemma4:26b"] if phase == "identity_control" else []
        ):
            for layout, linked in CELLS:
                rr = [
                    r
                    for r in obs
                    if r["phase"] == phase
                    and r["model"] == model
                    and r["layout"] == layout
                    and r["linked"] == linked
                ]
                cc = [
                    r
                    for r in calls
                    if r["phase"] == phase
                    and r["model"] == model
                    and r["layout"] == layout
                    and r["linked"] == linked
                ]
                if not rr:
                    continue
                outcomes.append(
                    dict(
                        phase=phase,
                        model=model,
                        layout=layout,
                        linked=linked,
                        n=len(rr),
                        correct=sum(r["correct"] for r in rr),
                        definitive=sum(r["definitive"] for r in rr),
                        valid=sum(r["valid"] for r in rr),
                        calls=len(cc),
                        failed_calls=sum(r["failure"] for r in cc),
                        states=dict(Counter(r["state"] for r in rr)),
                    )
                )
    table(
        "main.tex",
        "llrr",
        r"Arm / model & Cell & Correct & Definitive",
        [
            [
                PHASE_LABEL[r["phase"]] + " / " + NAMES[r["model"]],
                ("P" if r["layout"] == "prose" else "S")
                + ("L" if r["linked"] else "U"),
                r["correct"],
                r["definitive"],
            ]
            for r in outcomes
        ],
    )
    # Recompute every factorial and contribution directly from response records.
    index = {
        (r["phase"], r["model"], r["seed"], r["layout"], r["linked"], r["id"]): r
        for r in obs
        if r["phase"] in ["exploratory", "replication", "identity_control"]
    }
    effects = []
    parts = []
    for phase in ["exploratory", "replication", "identity_control"]:
        phases = [r for r in obs if r["phase"] == phase]
        for model in sorted({r["model"] for r in phases}):
            for seed in [17, 43]:
                for family in sorted({r["family"] for r in phases}):
                    ids = sorted({r["id"] for r in phases if r["family"] == family})
                    n = len(ids)
                    values = {
                        (l, k): sum(
                            index[phase, model, seed, l, k, i]["correct"] for i in ids
                        )
                        / n
                        for l, k in CELLS
                    }
                    effects.append(
                        dict(
                            phase=phase,
                            model=model,
                            seed=seed,
                            family=family,
                            n=n,
                            layout_unlinked=values["structured", False]
                            - values["prose", False],
                            layout_linked=values["structured", True]
                            - values["prose", True],
                            locator_prose=values["prose", True]
                            - values["prose", False],
                            locator_structured=values["structured", True]
                            - values["structured", False],
                            interaction=(
                                values["structured", True] - values["prose", True]
                            )
                            - (values["structured", False] - values["prose", False]),
                        )
                    )
                    for linked in [False, True]:
                        c = Counter()
                        counts = Counter()
                        for i in ids:
                            a = index[phase, model, seed, "prose", linked, i]
                            b = index[phase, model, seed, "structured", linked, i]
                            category = (
                                "both_valid"
                                if a["valid"] and b["valid"]
                                else (
                                    "structured_only"
                                    if b["valid"]
                                    else "prose_only" if a["valid"] else "both_invalid"
                                )
                            )
                            c[category] += b["correct"] - a["correct"]
                            counts[category] += 1
                        assert sum(c.values()) == round(
                            (values["structured", linked] - values["prose", linked]) * n
                        )
                        parts.append(
                            dict(
                                phase=phase,
                                model=model,
                                seed=seed,
                                family=family,
                                linked=linked,
                                n=n,
                                total=sum(c.values()),
                                both_valid=c["both_valid"],
                                structured_only=c["structured_only"],
                                prose_only=c["prose_only"],
                                both_invalid=c["both_invalid"],
                                both_valid_n=counts["both_valid"],
                                structured_only_n=counts["structured_only"],
                                prose_only_n=counts["prose_only"],
                                both_invalid_n=counts["both_invalid"],
                            )
                        )
    dump("all_factorial_effects.csv", effects)
    dump("all_failure_contributions.csv", parts)
    aggregated = []
    for phase in ["exploratory", "identity_control"]:
        for model in sorted({r["model"] for r in parts if r["phase"] == phase}):
            for linked in [False, True]:
                rr = [
                    r
                    for r in parts
                    if r["phase"] == phase
                    and r["model"] == model
                    and r["linked"] == linked
                ]
                d = {
                    k: sum(r[k] for r in rr)
                    for k in [
                        "n",
                        "total",
                        "both_valid",
                        "structured_only",
                        "prose_only",
                        "both_invalid",
                    ]
                }
                assert d["total"] == sum(
                    d[k]
                    for k in [
                        "both_valid",
                        "structured_only",
                        "prose_only",
                        "both_invalid",
                    ]
                )
                aggregated.append(
                    [
                        PHASE_LABEL[phase] + " / " + NAMES[model],
                        "L" if linked else "U",
                        d["n"],
                        d["total"],
                        d["both_valid"],
                        d["structured_only"],
                        d["prose_only"],
                    ]
                )
    table(
        "failure.tex",
        "lcrrrrr",
        r"Arm / model & Loc. & $N$ & $\Delta n$ & Both valid & $S$ only & $P$ only",
        aggregated,
    )
    erows = []
    for phase in ["exploratory", "identity_control"]:
        for model in sorted({r["model"] for r in effects if r["phase"] == phase}):
            for seed in [17, 43]:
                rr = [
                    r
                    for r in effects
                    if r["phase"] == phase and r["model"] == model and r["seed"] == seed
                ]
                erows.append(
                    [PHASE_LABEL[phase] + " / " + NAMES[model], seed]
                    + [
                        pp(sum(r[k] for r in rr) / len(rr))
                        for k in [
                            "layout_unlinked",
                            "layout_linked",
                            "locator_prose",
                            "locator_structured",
                            "interaction",
                        ]
                    ]
                )
    table(
        "effects.tex",
        "llrrrrr",
        r"Arm / model & Seed & $\Delta_{L,U}$ & $\Delta_{L,L}$ & $\Delta_{A,P}$ & $\Delta_{A,S}$ & $I$",
        erows,
    )
    controls = []
    if complete:
        rr = read(REPL / "results/singleton_pairs.json")
        for model in ["gpt-oss:20b", "mistral-small:24b"]:
            for layout, linked in CELLS:
                selected = [
                    r
                    for r in rr
                    if r["model"] == model
                    and r["layout"] == layout
                    and r["linked"] == linked
                ]
                assert len(selected) == 10
                controls.append(
                    dict(
                        model=model,
                        layout=layout,
                        linked=linked,
                        n=10,
                        batch_correct=sum(r["batch_correct"] for r in selected),
                        single_correct=sum(r["singleton_correct"] for r in selected),
                        both_valid=sum(r["both_valid"] for r in selected),
                        both_definitive=sum(r["both_definitive"] for r in selected),
                        label_changes=sum(
                            r["batch_prediction"] != r["singleton_prediction"]
                            for r in selected
                        ),
                        definitive_changes=sum(
                            r["both_definitive"]
                            and r["batch_prediction"] != r["singleton_prediction"]
                            for r in selected
                        ),
                    )
                )
        table(
            "singletons.tex",
            "lcrrrr",
            "Model & Cell & Batch & Single & Changes & Def. changes",
            [
                [
                    NAMES[r["model"]],
                    ("P" if r["layout"] == "prose" else "S")
                    + ("L" if r["linked"] else "U"),
                    r["batch_correct"],
                    r["single_correct"],
                    r["label_changes"],
                    r["definitive_changes"],
                ]
                for r in controls
            ],
        )
        dump("singleton_summary.csv", controls)
    else:
        (TEX / "tables/singletons.tex").write_text(
            "Replication is running; no singleton results have been imputed.\n"
        )
    from table_layout import compact_tables

    compact_tables(TEX)
    # Macros are derived counts, never hand-filled outcomes.
    macros = []

    def macro(k, v):
        macros.append(chr(92) + "newcommand{" + chr(92) + k + "}{" + str(v) + "}")

    macro(
        "DiscoveryArrayFailures",
        sum(r["failure"] for r in calls if r["phase"] == "discovery_array"),
    )
    macro(
        "DiscoveryKeyedFailures",
        sum(r["failure"] for r in calls if r["phase"] == "discovery_keyed"),
    )
    macro("ActualPaperCalls", len(calls))
    macro("ReplicationCompleted", "1" if complete else "0")
    order = []
    for b in (r for r in obs if r["phase"] == "order_control"):
        a = index["exploratory", b["model"], 17, b["layout"], b["linked"], b["id"]]
        order.append(
            dict(
                model=b["model"],
                layout=b["layout"],
                linked=b["linked"],
                trial=b["trial"],
                id=b["id"],
                both_valid=a["valid"] and b["valid"],
                both_definitive=a["definitive"] and b["definitive"],
                changed_definitive=bool(
                    a["definitive"]
                    and b["definitive"]
                    and a["prediction"] != b["prediction"]
                ),
            )
        )
    dump("order_repeat_pairs.csv", order)
    same = [r for r in order if r["trial"] == "same_order_repeat"]
    rev = [r for r in order if r["trial"] == "reversed_order"]
    macro("SameOrderChanges", sum(r["changed_definitive"] for r in same))
    macro("ReverseOrderChanges", sum(r["changed_definitive"] for r in rev))
    macro("SameOrderBothDef", sum(r["both_definitive"] for r in same))
    macro("ReverseOrderBothDef", sum(r["both_definitive"] for r in rev))
    if complete:
        macro("ReplicationReady", "")
        reffects = [r for r in effects if r["phase"] == "identity_control"]
        layout = [r[k] for r in reffects for k in ["layout_unlinked", "layout_linked"]]
        locator = [
            r[k] for r in reffects for k in ["locator_prose", "locator_structured"]
        ]
        for name, values in [("Layout", layout), ("Locator", locator)]:
            macro("R" + name + "Min", f"{100*min(values):+.1f}")
            macro("R" + name + "Max", f"{100*max(values):+.1f}")
            macro("R" + name + "Positive", sum(v > 1e-9 for v in values))
            macro("R" + name + "Zero", sum(abs(v) < 1e-9 for v in values))
            macro("R" + name + "Negative", sum(v < -1e-9 for v in values))
        macro(
            "ReplicationBatchFailures",
            sum(r["failure"] for r in calls if r["phase"] == "identity_control"),
        )
        macro(
            "SingletonBatchFailures",
            sum(r["failure"] for r in calls if r["phase"] == "singleton"),
        )
        diagnostic = next(
            r
            for r in parts
            if r["phase"] == "identity_control"
            and r["model"] == "gpt-oss:20b"
            and r["seed"] == 43
            and r["family"] == "mediastore"
            and r["linked"]
        )
        macro("RDiagnosticTotal", diagnostic["total"])
        macro("RDiagnosticBoth", f"{diagnostic['both_valid']:+d}")
        macro("RDiagnosticProseOnly", diagnostic["prose_only"])
        macro(
            "RDiagnosticCitationFailures",
            sum(
                r["state"] == "item_invalid"
                for r in obs
                if r["phase"] == "identity_control"
                and r["model"] == "gpt-oss:20b"
                and r["seed"] == 43
                and r["family"] == "mediastore"
                and r["layout"] == "structured"
                and r["linked"]
            ),
        )
        mapping = read(IDENTITY / "data/id_map.json")
        joint = []
        for model in ["gpt-oss:20b", "mistral-small:24b", "gemma4:26b"]:
            for seed in [17, 43]:
                rr = []
                for qid, newid in mapping.items():
                    for layout, linked in CELLS:
                        a = index["replication", model, seed, layout, linked, qid]
                        b = index[
                            "identity_control", model, seed, layout, linked, newid
                        ]
                        rr.append(
                            dict(
                                model=model,
                                seed=seed,
                                id=qid,
                                display_id=newid,
                                family=a["family"],
                                layout=layout,
                                linked=linked,
                                old_prediction=a["prediction"],
                                new_prediction=b["prediction"],
                                old_correct=a["correct"],
                                new_correct=b["correct"],
                                both_valid=a["valid"] and b["valid"],
                                both_definitive=a["definitive"] and b["definitive"],
                                label_changed=a["prediction"] != b["prediction"],
                            )
                        )
                joint += rr
        dump("joint_identity_order_pairs.csv", joint)
        jr = []
        for model in ["gpt-oss:20b", "mistral-small:24b", "gemma4:26b"]:
            for seed in [17, 43]:
                rr = [r for r in joint if r["model"] == model and r["seed"] == seed]
                jr.append(
                    [
                        NAMES[model],
                        seed,
                        sum(r["old_correct"] for r in rr),
                        sum(r["new_correct"] for r in rr),
                        sum(r["label_changed"] for r in rr),
                        sum(r["both_definitive"] and r["label_changed"] for r in rr),
                    ]
                )
        table(
            "identities.tex",
            "llrrrr",
            "Model & Seed & $H$ correct & $R$ correct & Changes & Def. changes",
            jr,
        )
        macro("IdentityChangedAll", sum(r["label_changed"] for r in joint))
        macro(
            "IdentityChangedDef",
            sum(r["both_definitive"] and r["label_changed"] for r in joint),
        )
        macro("IdentityBothDef", sum(r["both_definitive"] for r in joint))
        macro("SingletonChangedAll", sum(r["label_changes"] for r in controls))
        macro("SingletonChangedDef", sum(r["definitive_changes"] for r in controls))
        macro("SingletonBothDef", sum(r["both_definitive"] for r in controls))
        macro("SingletonBatchCorrect", sum(r["batch_correct"] for r in controls))
        macro("SingletonSingleCorrect", sum(r["single_correct"] for r in controls))
        lex = read(REPL / "results/lexical_sanity_controls.json")
        macro(
            "TargetNameCorrect",
            sum(r["correct"] for r in lex if r["scope"] == "target"),
        )
        macro(
            "ContextNameCorrect",
            sum(r["correct"] for r in lex if r["scope"] == "context"),
        )
    (TEX / "numbers.tex").write_text("\n".join(macros) + "\n")
    design_figure()
    plot(effects, outcomes, controls, complete)
    summary = dict(
        replication_complete=complete,
        calls=len(calls),
        observations=len(obs),
        primary_replication_unique_questions=60,
        source_project_families=5,
        discovery_array_failures=sum(
            r["failure"] for r in calls if r["phase"] == "discovery_array"
        ),
        discovery_keyed_failures=sum(
            r["failure"] for r in calls if r["phase"] == "discovery_keyed"
        ),
        all_failure_partitions_reconciled=True,
    )
    if complete:
        assert len(calls) == 624 and len(obs) == 6288 and len(effects) == 68
    (ROOT / "output/numeric_verification.json").write_text(
        json.dumps(dict(status="PASS", **summary), indent=2)
    )
    print("RESULT_TABLES_BUILT", json.dumps(summary))


def plot(effects, outcomes, controls, complete):
    which = "identity_control" if complete else "exploratory"
    models = sorted({r["model"] for r in effects if r["phase"] == which})
    families = FAMS if complete else ["mediastore", "teastore"]
    fig, axes = plt.subplots(
        len(models),
        2,
        figsize=(4.724, 4.55 if complete else 3.8),
        squeeze=False,
        sharey=True,
    )
    for j, model in enumerate(models):
        for k, linked in enumerate([False, True]):
            ax = axes[j, k]
            for offset, seed, marker in [(-0.1, 17, "o"), (0.1, 43, "s")]:
                values = [
                    100
                    * next(
                        r["layout_linked" if linked else "layout_unlinked"]
                        for r in effects
                        if r["phase"] == which
                        and r["model"] == model
                        and r["seed"] == seed
                        and r["family"] == fam
                    )
                    for fam in families
                ]
                ax.plot(
                    [i + offset for i in range(len(families))],
                    values,
                    marker=marker,
                    color="#387b87" if seed == 17 else "#c2a446",
                    linestyle="none",
                    label=str(seed),
                    markersize=4,
                )
            ax.axhline(0, color="black", lw=0.7)
            ax.set_xticks(
                range(len(families)), [SHORT[f] for f in families], fontsize=10
            )
            ax.set_title(
                NAMES[model] + " / " + ("linked" if linked else "unlinked"), fontsize=10
            )
            ax.tick_params(axis="y", labelsize=10)
            ax.set_ylabel("S - P (pp)", fontsize=10)
            ax.set_ylim(-62, 42)
            ax.set_yticks([-50, 0, 25])
    fig.legend(
        *axes[0, 0].get_legend_handles_labels(),
        title="Seed",
        ncol=2,
        loc="lower center",
        frameon=False,
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.09, 1, 1), pad=0.5)
    fig.savefig(TEX / "figures/layout_effects.pdf")
    plt.close(fig)
    rows = [r for r in outcomes if r["phase"] == which]
    fig, ax = plt.subplots(figsize=(4.724, 3.3))
    bottom = [0] * len(rows)
    colors = {
        "definitive": "#387b87",
        "explicit_uncertain": "#c2a446",
        "item_invalid": "#bc6d45",
        "batch_failure": "#444444",
    }
    for (state, color), hatch in zip(colors.items(), ["", "...", "///", "xx"]):
        values = [r["states"].get(state, 0) for r in rows]
        ax.bar(
            range(len(rows)),
            values,
            bottom=bottom,
            label=state.replace("_", " "),
            color=color,
            hatch=hatch,
            edgecolor="#333333",
            linewidth=0.3,
        )
        bottom = [a + b for a, b in zip(bottom, values)]
    ax.set_xticks(
        range(len(rows)),
        [
            ("P" if r["layout"] == "prose" else "S") + ("L" if r["linked"] else "U")
            for r in rows
        ],
        fontsize=10,
    )
    ax.tick_params(axis="y", labelsize=10)
    ax.set_ylabel("Repeated item decisions", fontsize=10)
    ax.legend(ncol=2, fontsize=10, loc="upper center", bbox_to_anchor=(0.5, 1.33))
    for position, model in [(1.5, "GPT-OSS"), (5.5, "Mistral"), (9.5, "Gemma")]:
        ax.text(
            position,
            -0.20,
            model,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10,
        )
    for boundary in [3.5, 7.5]:
        ax.axvline(boundary, color="#999999", linewidth=0.6)
    fig.tight_layout(rect=(0, 0.05, 1, 1), pad=0.4)
    fig.savefig(TEX / "figures/response_states.pdf")
    plt.close(fig)
    if controls:
        fig, axes = plt.subplots(1, 2, figsize=(4.724, 2.7))
        for model, ax in zip(["gpt-oss:20b", "mistral-small:24b"], axes):
            rows = [r for r in controls if r["model"] == model]
            x = range(4)
            ax.bar(
                [i - 0.17 for i in x],
                [r["batch_correct"] for r in rows],
                width=0.34,
                color="#387b87",
                label="Batch (12 questions)",
            )
            ax.bar(
                [i + 0.17 for i in x],
                [r["single_correct"] for r in rows],
                width=0.34,
                color="#c2a446",
                label="Singleton",
                hatch="///",
                edgecolor="#444444",
                linewidth=0.3,
            )
            ax.set_xticks(
                list(x),
                [
                    ("P" if r["layout"] == "prose" else "S")
                    + ("L" if r["linked"] else "U")
                    for r in rows
                ],
                fontsize=10,
            )
            ax.set_ylim(0, 11)
            ax.set_yticks([0, 5, 10])
            ax.set_ylabel("Correct / all 10", fontsize=10)
            ax.set_title(NAMES[model], fontsize=10)
        fig.legend(
            *axes[0].get_legend_handles_labels(),
            ncol=2,
            loc="lower center",
            frameon=False,
            fontsize=10,
            bbox_to_anchor=(0.5, 0),
        )
        fig.tight_layout(rect=(0, 0.13, 1, 1), pad=0.5)
        fig.savefig(TEX / "figures/singleton_accuracy.pdf", bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    build()
