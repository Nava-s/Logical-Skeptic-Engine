#!/usr/bin/env python3
"""
benchmark.py — Frozen-input benchmark runner for the Logical Skeptic Engine.

Experimental design (full factorial on frozen inputs):
  proposals (fallacious|sound x plain|manipulative)
    x reviewer posture (neutral | deferent)
    x arm (baseline | enforced)
    x N seeds (majority vote over reviewer samples)

The ENGINE pipeline (extractor -> checker -> skeptic_tool) runs ONCE per proposal
at temperature 0: it is the deterministic component, not the noisy variable under
study. Its intervention string is reused across postures, arms and seeds.

The REVIEWER runs at temperature 0.2 and is sampled --seeds times per condition;
the recorded verdict is the MAJORITY vote with a conservative tie-break
(REJECTED > PENDING > APPROVED). Per-seed verdicts and the agreement rate are
stored so score.py can report verdict stability (the noise floor).

Roles can use different local models:
  LSE_REVIEWER_MODEL  (default "local-model")          -> reviewer under test
  LSE_UTILITY_MODEL   (default = LSE_REVIEWER_MODEL)   -> extractor + checker

Usage:
  python benchmark.py                          # everything, 1 seed, both postures
  python benchmark.py --seeds 5                # 5 reviewer samples per condition
  python benchmark.py --postures neutral       # neutral | deferent | both
  python benchmark.py --usecase aws            # restrict to one scenario
  python benchmark.py --mock                   # validate the harness without a model
"""
import os
import re
import sys
import json
import glob
from collections import Counter

from skeptic_tool import analyze_general_fallacy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
USE_CASES_DIR = os.path.join(BASE_DIR, "use_cases")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

REVIEWER_MODEL = os.environ.get("LSE_REVIEWER_MODEL", "local-model")
UTILITY_MODEL = os.environ.get("LSE_UTILITY_MODEL", REVIEWER_MODEL)

MOCK = "--mock" in sys.argv
VERDICT_RE = re.compile(r"\[(APPROVED|REJECTED|PENDING)\]", re.IGNORECASE)
CONSERVATIVE_ORDER = ["REJECTED", "PENDING", "APPROVED", "UNPARSED"]


def cli_arg(flag, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


SEEDS = max(1, int(cli_arg("--seeds", "1")))
POSTURES_ARG = cli_arg("--postures", "both").lower()
POSTURES = {"both": ["neutral", "deferent"],
            "neutral": ["neutral"],
            "deferent": ["deferent"]}.get(POSTURES_ARG)
if POSTURES is None:
    sys.exit("--postures must be one of: both, neutral, deferent")


# --------------------------------------------------------------------------- LLM client
def make_caller():
    if MOCK:
        return _mock_call
    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

    def _call(model, system, user, temperature):
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return client.chat.completions.create(
            model=model, messages=msgs, temperature=temperature
        ).choices[0].message.content
    return _call


def _mock_call(model, system, user, temperature):
    """Deterministic stand-in keyed off marker text, so the harness can be
    validated end-to-end (postures, seeds, majority vote) without a server."""
    s = system.lower()
    if "symbolic logic extractor" in s:
        return json.dumps({
            "claims": [
                {"id": "C1", "text": "A confirmed symptom is present."},
                {"id": "C2", "text": "An unverified cause is asserted."},
            ],
            "asserted_as_fact": ["C2"],
            "causal_relationships": [{"if": "C2", "then": "C1"}],
        })
    if "grounding verifier" in s:
        return json.dumps({"fact_evaluation": [
            {"id": "C1", "confirmed_in_original_text": True, "evidence": "A confirmed symptom is present."},
            {"id": "C2", "confirmed_in_original_text": False, "evidence": None},
        ]})
    if "system warning" in user.lower() or "logical validator" in user.lower():
        return "On review the key premise is unverified.\n[REJECTED]"
    if "important context on the proposer" in s:
        return "Trusting the senior expert's judgement.\n[APPROVED]"
    return "The plan looks thorough and well reasoned.\n[APPROVED]"


CALL = make_caller()


# --------------------------------------------------------------------------- helpers
def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_fences(txt):
    return re.sub(r"```json|```", "", txt).strip()


def parse_verdict(text):
    m = VERDICT_RE.search(text or "")
    return m.group(1).upper() if m else "UNPARSED"


def majority(verdicts):
    """Majority vote; ties broken conservatively (REJECTED > PENDING > APPROVED)."""
    counts = Counter(verdicts)
    top = max(counts.values())
    tied = [v for v, c in counts.items() if c == top]
    winner = min(tied, key=lambda v: CONSERVATIVE_ORDER.index(v)
                 if v in CONSERVATIVE_ORDER else len(CONSERVATIVE_ORDER))
    return winner, top / len(verdicts)


def list_use_cases():
    cases = sorted(
        d for d in os.listdir(USE_CASES_DIR)
        if os.path.isdir(os.path.join(USE_CASES_DIR, d))
    )
    name = cli_arg("--usecase", None)
    if name:
        if name not in cases:
            sys.exit(f"Use case '{name}' not found. Available: {cases}")
        return [name]
    return cases


# --------------------------------------------------------------------------- pipeline
SYSTEM_EXTRACTOR = load(os.path.join(PROMPT_DIR, "system_extractor.txt"))
USER_EXTRACTOR_T = load(os.path.join(PROMPT_DIR, "user_extractor.txt"))
SYSTEM_CHECKER = load(os.path.join(PROMPT_DIR, "system_checker.txt"))
USER_CHECKER_T = load(os.path.join(PROMPT_DIR, "user_checker.txt"))


def run_enforced_engine(problem_text, proposal_text):
    """Returns (intervention_string, engine_outcome, detail). Runs once per proposal."""
    extractor_user = USER_EXTRACTOR_T.format(RESPONSE_A=proposal_text)
    raw_struct = CALL(UTILITY_MODEL, SYSTEM_EXTRACTOR, extractor_user, 0.0)
    struct_json = strip_fences(raw_struct)

    try:
        parsed = json.loads(struct_json)
        relevant = set(parsed.get("asserted_as_fact", []))
        for r in parsed.get("causal_relationships", []):
            relevant.update([r.get("if"), r.get("then")])
        claims_to_check = [c for c in parsed.get("claims", []) if c.get("id") in relevant]
        facts_to_verify = json.dumps(claims_to_check, ensure_ascii=False, indent=2)
    except Exception:
        facts_to_verify = "[]"

    checker_user = USER_CHECKER_T.format(PROBLEM=problem_text, FACTS_TO_VERIFY=facts_to_verify)
    raw_check = CALL(UTILITY_MODEL, SYSTEM_CHECKER, checker_user, 0.0)
    check_json = strip_fences(raw_check)

    valid, message = analyze_general_fallacy(struct_json, check_json, source_text=problem_text)
    if valid:
        return "", "clean", message
    outcome = "infra" if message.startswith("VALIDATOR ERROR") else "blocked"
    intervention = (f"\n[SYSTEM WARNING FOR THE REVIEWER]: The logical validator blocked "
                    f"the proposal. Reason: {message}\n")
    return intervention, outcome, message


def review_majority(system_b, user_b_template, proposal_text, intervention):
    user_b = user_b_template.format(RESPONSE_A=proposal_text, SYSTEM_INTERVENTION=intervention)
    verdicts = []
    for _ in range(SEEDS):
        text = CALL(REVIEWER_MODEL, system_b, user_b, 0.2)
        verdicts.append(parse_verdict(text))
    win, agreement = majority(verdicts)
    return win, agreement, verdicts


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []
    for uc in list_use_cases():
        d = os.path.join(USE_CASES_DIR, uc)
        problem = load(os.path.join(d, "problem.txt"))
        user_b_t = load(os.path.join(d, "user_B.txt"))
        labels = json.loads(load(os.path.join(d, "proposals", "labels.json")))

        system_b_by_posture = {"neutral": load(os.path.join(d, "system_B.txt"))}
        deferent_path = os.path.join(d, "system_B_deferent.txt")
        if os.path.isfile(deferent_path):
            system_b_by_posture["deferent"] = load(deferent_path)

        for ppath in sorted(glob.glob(os.path.join(d, "proposals", "*.txt"))):
            pid = os.path.splitext(os.path.basename(ppath))[0]
            proposal = load(ppath)
            label = labels.get(pid, {})

            # Engine: once per proposal, reused across postures/arms/seeds.
            intervention, engine_outcome, detail = run_enforced_engine(problem, proposal)

            for posture in POSTURES:
                if posture not in system_b_by_posture:
                    print(f"  ! {uc}: no system_B_deferent.txt, skipping posture '{posture}'")
                    continue
                system_b = system_b_by_posture[posture]

                base_v, base_agr, base_all = review_majority(system_b, user_b_t, proposal, "")
                enf_v, enf_agr, enf_all = review_majority(system_b, user_b_t, proposal, intervention)

                results.append({
                    "use_case": uc,
                    "proposal": pid,
                    "fallacious": label.get("fallacious"),
                    "style": label.get("style"),
                    "pair": label.get("pair"),
                    "posture": posture,
                    "seeds": SEEDS,
                    "baseline_verdict": base_v,
                    "baseline_agreement": base_agr,
                    "baseline_verdicts": base_all,
                    "enforced_verdict": enf_v,
                    "enforced_agreement": enf_agr,
                    "enforced_verdicts": enf_all,
                    "engine_outcome": engine_outcome,
                    "engine_detail": detail,
                })
                print(f"[{uc}/{pid}|{posture}] fallacious={label.get('fallacious')} "
                      f"style={label.get('style')} baseline={base_v}({base_agr:.0%}) "
                      f"enforced={enf_v}({enf_agr:.0%}) engine={engine_outcome}")

    out = os.path.join(RESULTS_DIR, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(results)} rows to {out}  (seeds per condition: {SEEDS})")
    if MOCK:
        print("(mock mode: verdicts are synthetic, for harness validation only)")


if __name__ == "__main__":
    main()
