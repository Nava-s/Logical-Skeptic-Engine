#!/usr/bin/env python3
"""
benchmark.py — Frozen-input benchmark runner for the Logical Skeptic Engine.

For every use case and every frozen proposal it runs TWO arms on the SAME input:
  * baseline : reviewer sees the proposal alone
  * enforced : proposal -> extractor -> checker -> skeptic_tool -> reviewer (with intervention)

It records, per (use_case, proposal, arm):
  * the reviewer verdict (APPROVED / REJECTED / PENDING / UNPARSED)
  * the engine outcome (only meaningful in the enforced arm):
      "clean"  -> structure validated, no violation
      "blocked"-> a logical violation was detected (true skeptic action)
      "infra"  -> fail-closed due to malformed/incomplete utility-model output
Results go to results/results.json for scoring by score.py.

Roles can use different local models:
  REVIEWER_MODEL  (default "local-model")  -> Model A and Model B (the subject under test)
  UTILITY_MODEL   (default = REVIEWER_MODEL) -> extractor + checker (set to a stronger model)

Usage:
  python benchmark.py                 # run everything against the LM Studio endpoint
  python benchmark.py --usecase aws   # restrict to one use case
  python benchmark.py --mock          # no LLM needed: deterministic fake responses to test the harness
"""
import os
import re
import sys
import json
import glob

from skeptic_tool import analyze_general_fallacy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
USE_CASES_DIR = os.path.join(BASE_DIR, "use_cases")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

REVIEWER_MODEL = os.environ.get("LSE_REVIEWER_MODEL", "local-model")
UTILITY_MODEL = os.environ.get("LSE_UTILITY_MODEL", REVIEWER_MODEL)

MOCK = "--mock" in sys.argv

VERDICT_RE = re.compile(r"\[(APPROVED|REJECTED|PENDING)\]", re.IGNORECASE)


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
    """Deterministic stand-in so the harness can be validated without a model server.
    It keys off marker text in the system prompts."""
    s = system.lower()
    if "symbolic logic extractor" in s:
        # Pretend every proposal asserts one unconfirmed cause C2 driving effect C1.
        return json.dumps({
            "claims": [
                {"id": "C1", "text": "A confirmed symptom is present."},
                {"id": "C2", "text": "An unverified cause is asserted."},
            ],
            "asserted_as_fact": ["C2"],
            "causal_relationships": [{"if": "C2", "then": "C1"}],
        })
    if "grounding verifier" in s:
        # Effect confirmed with a real quote; asserted cause not confirmed.
        return json.dumps({"fact_evaluation": [
            {"id": "C1", "confirmed_in_original_text": True, "evidence": "A confirmed symptom is present."},
            {"id": "C2", "confirmed_in_original_text": False, "evidence": None},
        ]})
    # Reviewer: approve unless an intervention warning is present.
    if "system warning" in user.lower() or "logical validator" in user.lower():
        return "On review the key premise is unverified.\n[REJECTED]"
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


def list_use_cases():
    cases = sorted(
        d for d in os.listdir(USE_CASES_DIR)
        if os.path.isdir(os.path.join(USE_CASES_DIR, d))
    )
    if "--usecase" in sys.argv:
        name = sys.argv[sys.argv.index("--usecase") + 1]
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
    """Returns (intervention_string, engine_outcome, detail)."""
    extractor_user = USER_EXTRACTOR_T.format(RESPONSE_A=proposal_text)
    raw_struct = CALL(UTILITY_MODEL, SYSTEM_EXTRACTOR, extractor_user, 0.0)
    struct_json = strip_fences(raw_struct)

    # Send only the relevant claims (asserted + those used in causal links) to the checker.
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
    if message.startswith("VALIDATOR ERROR"):
        outcome = "infra"
    else:
        outcome = "blocked"
    intervention = f"\n[SYSTEM WARNING FOR THE REVIEWER]: The logical validator blocked the proposal. Reason: {message}\n"
    return intervention, outcome, message


def review(system_b, user_b_template, proposal_text, intervention):
    user_b = user_b_template.format(RESPONSE_A=proposal_text, SYSTEM_INTERVENTION=intervention)
    text = CALL(REVIEWER_MODEL, system_b, user_b, 0.2)
    return parse_verdict(text), text


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []
    for uc in list_use_cases():
        d = os.path.join(USE_CASES_DIR, uc)
        problem = load(os.path.join(d, "problem.txt"))
        system_b = load(os.path.join(d, "system_B.txt"))
        user_b_t = load(os.path.join(d, "user_B.txt"))
        labels = json.loads(load(os.path.join(d, "proposals", "labels.json")))

        for ppath in sorted(glob.glob(os.path.join(d, "proposals", "*.txt"))):
            pid = os.path.splitext(os.path.basename(ppath))[0]
            proposal = load(ppath)
            label = labels.get(pid, {})

            # Baseline arm
            base_verdict, _ = review(system_b, user_b_t, proposal, "")
            # Enforced arm
            intervention, engine_outcome, detail = run_enforced_engine(problem, proposal)
            enf_verdict, _ = review(system_b, user_b_t, proposal, intervention)

            results.append({
                "use_case": uc,
                "proposal": pid,
                "fallacious": label.get("fallacious"),
                "baseline_verdict": base_verdict,
                "enforced_verdict": enf_verdict,
                "engine_outcome": engine_outcome,
                "engine_detail": detail,
            })
            print(f"[{uc}/{pid}] fallacious={label.get('fallacious')} "
                  f"baseline={base_verdict} enforced={enf_verdict} engine={engine_outcome}")

    out = os.path.join(RESULTS_DIR, "results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(results)} rows to {out}")
    if MOCK:
        print("(mock mode: verdicts are synthetic, for harness validation only)")


if __name__ == "__main__":
    main()
