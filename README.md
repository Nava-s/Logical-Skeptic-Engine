# Logical Skeptic Engine (LSE)

An open-source, neuro-symbolic gatekeeper for LLM multi-agent decision loops. LSE
decomposes a proposal into an explicit, **id-referenced** logical structure, verifies
each premise against the source text, and runs a small **deterministic** Python rule
engine that blocks proposals resting on an unverified causal premise (the
*Affirming-the-Consequent* pattern) before they reach the reviewing agent.

This repository now ships as a **reproducible benchmark**: the proposals under test
are frozen and labelled, so every run is interpretable and every claim below is backed
by `results/`.

---

## What changed from the original prototype

The first version of LSE generated the proposal under review on the fly with a "Model A"
and matched fallacies with fuzzy token overlap. That made results non-reproducible and
the engine brittle. The current version:

1. **Referential (id-based) structure.** The extractor emits `claims` with ids; the
   `asserted_as_fact` and `causal_relationships` fields reference those ids only. The
   Python join is now exact — no token-overlap heuristics, no stopword lists, immune to
   the extractor's paraphrasing.
2. **Deterministic evidence verification.** Each "confirmed" verdict from the checker
   must carry a verbatim quote from the source text; the engine machine-checks that the
   quote actually appears there and **downgrades fabricated confirmations**.
3. **Fail-closed.** Malformed JSON, dangling id references, or an incomplete fact-check
   block the proposal instead of silently approving it.
4. **Coverage contract.** If the checker skips any required claim, the run is rejected
   as unreliable rather than scored as a pass.
5. **Frozen, labelled benchmark.** Proposals live as static files with ground-truth
   labels, balanced 12 fallacious / 12 sound across 6 domains, enabling a real
   confusion matrix (including a false-positive rate, which the prototype could not
   measure).

---

## Results (Llama 3.1 8B, all four roles on the same local model)

> Reproduce with `python benchmark.py && python score.py`. Raw rows in
> `results/results.json`.

### The engine as a fallacy detector

![engine confusion matrix](results/fig_engine_confusion.png)

| Metric | Value |
|---|---|
| Recall (fallacies caught) | **12 / 12 = 100%** |
| Precision | **80%** (3 sound proposals wrongly blocked) |
| F1 | **0.89** |
| Infra-failures (fail-closed, excluded from scoring) | 1 / 24 |

On the targeted fallacy class, across six domains, the engine missed nothing.

### But: the problem it targets did not appear at baseline

![reviewer shift](results/fig_reviewer_shift.png)

The honest headline is in the reviewer table. **Baseline sycophancy was already zero**:
the 8B reviewer, with no help from LSE, rejected or held all 12 fallacious proposals.
So on this dataset LSE corrected *no* real sycophancy — and the enforcement arm
**increased false alarms on sound proposals from 4 to 7**. Skepticism injection has a
cost, and here the cost exceeded a benefit that was already saturated.

This is a result worth publishing precisely because it is not a victory lap: it
isolates *where* the system needs work.

### Where the 3 false positives come from (all extractor errors, not engine errors)

- `manufacturing/03`, `smart_agriculture/03` — the *diagnosis-first* proposals. The
  extractor encoded a **cautionary** clause ("spraying against a non-fungal problem
  wastes money") as an *asserted* causal relationship. The model does not distinguish
  "the author asserts X as the cause" from "the author cites X hypothetically to argue
  *against* acting."
- `manufacturing/04` — engine output was `clean`; the reviewer rejected anyway. Not an
  engine false positive: the 8B reviewer refused on its own. The scorer attributes it to
  the final verdict, as it should.

The single infra-failure (`aws/03`) was the extractor emitting dangling ids `C3/C4`;
fail-closed caught it.

**Takeaway for the roadmap:** the bottleneck is extraction quality, not the Python rule.
Run the utility roles (extractor + checker) on a stronger model via `LSE_UTILITY_MODEL`
(e.g. Qwen-class) and keep the small model as the reviewer under test — which is LSE's
actual thesis.

---

## Scope and honest limitations

- **One fallacy class.** The engine detects unverified causal premises
  (Affirming-the-Consequent). All 12 fallacious proposals are of this single logical
  type. The benchmark therefore measures precision/recall *on that class*, not "logical
  fallacies" in general. New rules require new labelled traps.
- **The reviewer is the dependent variable.** A reviewer that is already skeptical (as
  the 8B was here) leaves LSE nothing to fix. The interesting regime is a model that
  *does* defer to confident prose; demonstrating uplift there is future work.
- **Synthetic, small dataset.** 24 proposals, hand-authored. Useful as a controlled
  probe, not a population estimate.

---

## Architecture

```
proposal (frozen file)
   │
   ▼
Extractor (LLM, temp 0)  ──►  id-referenced JSON: {claims, asserted_as_fact, causal_relationships}
   │
   ▼
Checker (LLM, temp 0)    ──►  per-claim grounding + verbatim evidence quotes
   │
   ▼
skeptic_tool.py (pure Python, deterministic)
   ├─ referential-integrity + coverage contracts  ─► fail-closed on any breach
   ├─ verbatim evidence check                      ─► downgrade fabricated confirmations
   └─ rule: asserted-but-unconfirmed causal premise ─► BLOCK
   │
   ├── clean  ─►  Reviewer (free evaluation)
   └── blocked ─► Reviewer (with injected skepticism warning)
```

## Repository layout

```
lse/
├── skeptic_tool.py        # deterministic rule engine (referential join, evidence check, fail-closed)
├── benchmark.py           # runs every use case × proposal, baseline + enforced arms
├── score.py               # confusion matrix + reviewer table (infra-failures counted separately)
├── make_figures.py        # regenerates the result charts
├── build_dataset.py       # (re)generates the frozen use_cases/ tree
├── requirements.txt
├── prompts/               # shared extractor + checker prompts (same across scenarios)
│   ├── system_extractor.txt   user_extractor.txt
│   └── system_checker.txt     user_checker.txt
└── use_cases/<scenario>/
    ├── problem.txt        # source text: confirms symptoms, NOT the diagnostic cause
    ├── system_B.txt       # reviewer role
    ├── user_B.txt         # reviewer request ({RESPONSE_A}, {SYSTEM_INTERVENTION})
    └── proposals/
        ├── 01.txt 02.txt  # fallacious (asserted unverified cause)
        ├── 03.txt 04.txt  # sound (verify-first; act on confirmed facts only)
        └── labels.json    # ground truth per proposal
```

## How to run

```bash
pip install -r requirements.txt          # just the openai client

# 1. Validate the whole pipeline without any model server:
python benchmark.py --mock
python score.py

# 2. Real run against an OpenAI-compatible local server (LM Studio / Ollama) on :1234
#    Optionally separate the roles:
export LSE_UTILITY_MODEL="qwen3-30b"      # extractor + checker
export LSE_REVIEWER_MODEL="llama3.1-8b"   # the reviewer under test
python benchmark.py                       # add --usecase aws to restrict
python score.py
python make_figures.py
```

The model endpoint is `http://127.0.0.1:1234/v1` in `benchmark.py`; change it if yours
differs.

## Adding scenarios or proposals

Either extend the `USE_CASES` dict in `build_dataset.py` and re-run it, or hand-create a
folder under `use_cases/` matching the layout above. The runner discovers scenarios and
proposals from the filesystem — no code changes needed. Keep the contract: `problem.txt`
states the symptoms/effects and leaves the diagnostic **cause** unconfirmed; fallacious
proposals assert that cause and act on it; sound proposals verify first or act only on
confirmed facts.

## Contributing

The highest-value contributions right now: (1) additional fallacy rules in
`skeptic_tool.py` with matching labelled traps; (2) a reviewer model that exhibits
real baseline sycophancy, to show enforcement uplift; (3) extractor-prompt improvements
that fix the cautionary-clause false positives.

## License

See `LICENSE`.
