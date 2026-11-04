"""Lossless table presentation changes; all analysis CSVs remain untouched."""

import json
from pathlib import Path


def read_table(path):
    text = path.read_text()
    header = text.split("\\toprule\n", 1)[1].split("\\\\\\midrule", 1)[0]
    body = text.split("\\midrule\n", 1)[1].split("\\bottomrule", 1)[0]
    rows = [
        line.removesuffix("\\\\").split(" & ") for line in body.strip().splitlines()
    ]
    return header, rows


def write_table(path, columns, header, rows):
    path.write_text(
        "\\begin{tabular}{"
        + columns
        + "}\\toprule\n"
        + header
        + "\\\\\\midrule\n"
        + "\n".join(" & ".join(row) + "\\\\" for row in rows)
        + "\n\\bottomrule\\end{tabular}\n"
    )


def compact_tables(output):
    tables = output / "tables"
    checks = {}
    # Pivot discovery without pooling seeds or conditions. A/K are two counts.
    header, rows = read_table(tables / "discovery.tex")
    groups = {}
    for model, seed, condition, array, keyed, failed in rows:
        groups.setdefault((model, seed), {})[condition] = (array, keyed, failed)
    compact = []
    expanded = []
    for (model, seed), cells in groups.items():
        compact.append(
            [model, seed]
            + [cells[c][0] + "/" + cells[c][1] for c in ["T", "P", "S"]]
            + ["/".join(cells[c][2] for c in ["T", "P", "S"])]
        )
        expanded.extend([[model, seed, c, *cells[c]] for c in ["T", "P", "S"]])
    assert expanded == rows
    write_table(
        tables / "discovery.tex",
        "llrrrr",
        "Model & Seed & T (A/K) & P (A/K) & S (A/K) & Fail T/P/S",
        compact,
    )
    checks["discovery"] = {
        "before_rows": len(rows),
        "after_rows": len(compact),
        "all_counts_preserved": True,
    }
    # Pivot four factorial cells; do not divide C by D or drop failed attempts.
    header, rows = read_table(tables / "main.tex")
    groups = {}
    for model, cell, correct, definitive in rows:
        groups.setdefault(model, {})[cell] = (correct, definitive)
    compact = []
    expanded = []
    for model, cells in groups.items():
        compact.append(
            [model] + [" / ".join(cells[c]) for c in ["PU", "PL", "SU", "SL"]]
        )
        expanded.extend([[model, c, *cells[c]] for c in ["PU", "PL", "SU", "SL"]])
    assert expanded == rows
    write_table(
        tables / "main.tex", "lrrrr", "Arm / model & PU & PL & SU & SL", compact
    )
    checks["factorial"] = {
        "before_rows": len(rows),
        "after_rows": len(compact),
        "all_counts_preserved": True,
    }
    header, rows = read_table(tables / "arms.tex")
    h = next(row for row in rows if row[0] == "$H$: factorial")
    r = next(row for row in rows if row[0] == "$R$: remapped")
    assert h[1:] == r[1:]
    compact = [
        (["$H$, $R$ (each)"] + row[1:] if row is h else row)
        for row in rows
        if row is not r
    ]
    write_table(tables / "arms.tex", "lrrrrrrr", header, compact)
    checks["arms"] = {
        "before_rows": len(rows),
        "after_rows": len(compact),
        "identical_design_only": True,
    }
    header, rows = read_table(tables / "singletons.tex")
    mistral = [row for row in rows if row[0] == "Mistral"]
    assert len(mistral) == 4 and len({tuple(row[2:]) for row in mistral}) == 1
    compact = [row for row in rows if row[0] != "Mistral"] + [
        ["Mistral", "All four"] + mistral[0][2:]
    ]
    write_table(tables / "singletons.tex", "lcrrrr", header, compact)
    checks["singletons"] = {
        "before_rows": len(rows),
        "after_rows": len(compact),
        "identical_values_are_per_cell_not_summed": True,
    }
    header, rows = read_table(tables / "failure.tex")
    assert all(row[2] == ("160" if row[0].startswith("$E$") else "120") for row in rows)
    groups = {}
    for row in rows:
        groups.setdefault(row[0], {})[row[1]] = row[3:]
    compact = []
    expanded = []
    for model, cells in groups.items():
        compact.append(
            [model] + [cells["U"][i] + " / " + cells["L"][i] for i in range(4)]
        )
        expanded.extend(
            [
                [model, loc, "160" if model.startswith("$E$") else "120", *cells[loc]]
                for loc in ["U", "L"]
            ]
        )
    assert expanded == rows
    write_table(
        tables / "failure.tex",
        "lrrrr",
        r"Arm / model & $\Delta n$ & Both valid & $S$ only & $P$ only",
        compact,
    )
    checks["failure"] = {
        "before_rows": len(rows),
        "after_rows": len(compact),
        "all_counts_preserved": True,
        "removed_column": "N; constant within cohort, explicitly stated in caption",
        "paired_entries": "U / L contributions, not ratios",
        "zero_contributions_preserved": True,
    }
    (output / "table_consolidation.json").write_text(
        json.dumps({"status": "PASS", "checks": checks}, indent=2)
    )
