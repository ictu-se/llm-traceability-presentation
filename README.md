# Evidence presentation in LLM traceability decisions

This artifact contains the code and data for an empirical study of supplied component–sentence decisions. It preserves 624 calls and 6,288 repeated item observations, including every failed response and abstention. It contains no manuscript files or model weights.

## Offline reproduction

Python 3.10 or later is required (tested with Python 3.12). No model server, GPU, API credential, LaTeX installation, or network call is needed after installing dependencies.

```sh
git clone https://github.com/ictu-se/llm-traceability-presentation.git
cd llm-traceability-presentation
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce.py
python verify.py
```

`reproduce.py` recomputes all analysis CSVs, editable LaTeX table fragments, and vector figures in `output/`. Table fragments and figures are research results, not an article source package. `verify.py` checks the manifest, request hashes, and original phase-specific validation rules against every raw response, then compares every regenerated CSV with the preserved analysis. No successful-only filtering or response repair is used. Plot files may have different PDF metadata across runs; numerical CSVs are byte-identical under canonical sorting.

## Experimental structure

| Phase | Questions | Calls | Interpretation |
|---|---:|---:|---|
| D array/keyed | 72 shared | 144 | Historical response-contract control; three families and six snapshots |
| E factorial | 80 | 128 | Two projects, two models, two seeds, four input cells |
| E order/repeat | 20 reused | 32 | Same-order repeat and reversed-order diagnostic |
| H factorial | 60 | 120 | Five previously inspected families, three models, two seeds |
| H singleton | 10 reused | 80 | Matched subset, two models, four cells, seed 17 |
| R | Same 60 as H | 120 | Independent query IDs and order; required output keys change jointly |

H and R use six listed and six unlisted pairs per family. These are case-control samples, not natural link prevalence. Unlisted pairs are nonlinks under the published closed reference, not independently verified semantic negatives. Repeated calls do not create independent projects. The H input audit found selection-linked ID/class association; R was frozen separately before its inference. R does not isolate the causal effect of IDs from order or grammar realization.

## Provenance and interpretation

Data are derived from the ArDoCo benchmark, revision `e60ddb2676358048131178c925e86a5b33ec38f2`. See `source_revision.json`, the preserved original sources, and `UPSTREAM_BENCHMARK_LICENSE.txt`; upstream attribution and terms are retained. Labels in directories historically named `private` are published reference labels, withheld from prompts but included here for reproduction. No participant or new expert ratings were collected. The LLMs provide experimental decisions; deterministic validation and existing benchmark references provide the reported scores.

`data/D`, `data/E`, `data/H`, and `data/R` preserve raw requests, responses, question content, and labels. H/R also include frozen protocols, planned jobs, ID mapping, original benchmark snapshots, and the initial diagnostic analyses. Historical field names and provenance strings remain unchanged inside raw records; they must not be interpreted as new human judgments. `freeze_provenance.json` records hashes of the original local freeze manifests, and `manifest.json` checksums the portable files. Local absolute paths and personal profile data are excluded.

The original array validator checks completeness and duplicate answer IDs but does not reject duplicate JSON object keys. The keyed discovery control adds duplicate-key rejection. E/H/R also check the declared schema. All phases reject unavailable evidence IDs at item level and links with no evidence. A valid `uncertain` is an abstention. `validation.py` preserves the historical validator vocabulary; `records.py` applies the appropriate phase rules.

## Optional inference replay

Exact request replay additionally requires Ollama 0.34.4 and the exact local model digests in `model_artifacts.json`, plus sufficient memory (the recorded host had 48 GiB). Aliases alone are insufficient. The Gemma-labelled configuration is a locally prepared quantized artifact; this repository does not distribute its weights or claim it is a standard publicly retrievable model release. Consequently, all reported analyses are reproducible offline, while exact new inference is conditional on obtaining those artifacts. Even matching artifacts/settings need not guarantee bitwise identical sampling on other hardware.

```sh
python rerun.py --phase identity_control --output ../new-inference
```

Replay verifies model digests and server version, preserves the exact prompts/options/schemas, writes to a separate directory, and records errors without selecting favorable retries. `--limit 1` provides an optional smoke run. Resuming skips existing matching requests, including failures. Replayed outputs are new measurements and never replace the archived study outcomes.

## Scope of the release

The repository contains code, benchmark-derived inputs, raw outputs, and analysis results. Article PDF/TeX, author contact metadata, credentials, and manuscript submission files are intentionally absent. No Zenodo deposit or DOI is claimed. Citation order, page layout, and article preparation are handled separately from this analysis artifact.

## Compact article tables (v1.2.0)

`table_layout.py` pivots discovery and factorial cells, combines identical H/R design rows, and represents identical Mistral singleton cells once. Paired entries are counts, not computed ratios. The failure partition places U/L contributions side by side and moves cohort-constant denominators into the article caption. Round-trip assertions check that pivoted tables retain every original value. All eight numerical CSVs are unchanged. Figure labels retain ten-point typography.
