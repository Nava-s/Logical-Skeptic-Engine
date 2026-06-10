import json
import re

VALID_MSG = "Logical structure and premises are consistent."
MIN_EVIDENCE_CHARS = 10


def _parse(payload, label):
    """Parse JSON, salvaging the first complete JSON object even when the
    model appends trailing prose or prepends chatter (a frequent small-model
    failure). The salvage is deterministic: raw_decode from the first '{'."""
    try:
        return json.loads(payload), None
    except (json.JSONDecodeError, TypeError) as e:
        if isinstance(payload, str):
            start = payload.find("{")
            if start != -1:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(payload[start:])
                    return obj, None
                except json.JSONDecodeError:
                    pass
        return None, f"{label} is not valid JSON ({e})"


def _fail_closed(reason):
    """Any structural/contract error blocks the proposal instead of silently approving it."""
    return False, (
        f"VALIDATOR ERROR (fail-closed): {reason}. "
        "The proposal cannot be auto-cleared: the symbolic structure could not be "
        "verified. Require a manual logical review before any approval."
    )


def _norm(s):
    """Whitespace/case normalization for verbatim-quote matching."""
    return re.sub(r"\s+", " ", s).strip().lower()


def analyze_general_fallacy(json_logical, json_fact_checking, source_text=None):
    """
    Referential (ID-based) logical validator with deterministic contract checks.

    Expected input schemas
    ----------------------
    json_logical:
    {
      "claims": [{"id": "C1", "text": "..."}, ...],
      "asserted_as_fact": ["C1", ...],
      "causal_relationships": [{"if": "C1", "then": "C2"}, ...]
    }

    json_fact_checking:
    {
      "fact_evaluation": [
        {"id": "C1", "confirmed_in_original_text": true,
         "evidence": "<verbatim quote from the source text>"},
        {"id": "C2", "confirmed_in_original_text": false, "evidence": null}
      ]
    }

    source_text (optional but recommended):
      The original problem text. When provided, every "confirmed" verdict MUST
      carry an "evidence" quote that exists verbatim (modulo whitespace/case)
      in the source text. Confirmations with missing or fabricated evidence
      are DOWNGRADED to not-confirmed.

    Contract enforcement (all deterministic, all fail-closed):
      * referential integrity: every referenced id must be declared in claims
      * coverage: every id in asserted_as_fact or used in causal_relationships
        must appear in fact_evaluation. A checker that skips ids invalidates
        the whole verification (this is what a weak model does under load).

    Returns (valid: bool, message: str).
    """
    structure, err = _parse(json_logical, "Logical structure")
    if err:
        return _fail_closed(err)

    facts, err = _parse(json_fact_checking, "Fact-checking output")
    if err:
        return _fail_closed(err)

    # --- Claim registry -----------------------------------------------------------
    claims = {}
    for c in structure.get("claims", []):
        cid, text = c.get("id"), c.get("text")
        if not cid or not text:
            return _fail_closed("a claim is missing its 'id' or 'text' field")
        if cid in claims:
            return _fail_closed(f"duplicate claim id '{cid}'")
        claims[cid] = text

    if not claims:
        return _fail_closed("no claims were extracted from the proposal")

    asserted = list(structure.get("asserted_as_fact", []))
    implications = []
    for r in structure.get("causal_relationships", []):
        if_id, then_id = r.get("if"), r.get("then")
        if if_id is None or then_id is None:
            return _fail_closed("a causal relationship is missing 'if' or 'then'")
        implications.append((if_id, then_id))

    # --- Referential integrity ------------------------------------------------------
    required = set(asserted) | {x for pair in implications for x in pair}
    dangling = sorted(r for r in required if r not in claims)
    if dangling:
        return _fail_closed(
            f"dangling claim reference(s) {dangling}: every id used in "
            "'asserted_as_fact' or 'causal_relationships' must be declared in 'claims'"
        )

    # --- Grounding map with deterministic evidence verification ---------------------
    evaluations = {}
    downgrades = []
    for item in facts.get("fact_evaluation", []):
        fid = item.get("id")
        if fid is None:
            continue
        is_confirmed = bool(item.get("confirmed_in_original_text", False))
        if is_confirmed and source_text is not None:
            evidence = item.get("evidence")
            bad_evidence = (
                not isinstance(evidence, str)
                or len(evidence.strip()) < MIN_EVIDENCE_CHARS
                or _norm(evidence) not in _norm(source_text)
            )
            if bad_evidence:
                is_confirmed = False
                downgrades.append(
                    f"{fid}: confirmation rejected (evidence missing, too short, "
                    f"or not found verbatim in the source text)"
                )
        evaluations[fid] = is_confirmed

    # --- Coverage contract -----------------------------------------------------------
    missing = sorted(r for r in required if r not in evaluations)
    if missing:
        return _fail_closed(
            f"the fact-checker did not evaluate required claim id(s) {missing}; "
            "grounding coverage is incomplete and the verification is unreliable"
        )

    # --- Core rule: unverified causal premise (Affirming-the-Consequent pattern) -----
    violations = []
    for cid in asserted:
        if evaluations.get(cid, False):
            continue
        for if_id, then_id in implications:
            if if_id != cid:
                continue
            effect_note = (
                f"the effect {then_id} ('{claims[then_id]}') IS confirmed in the source text"
                if evaluations.get(then_id, False)
                else f"note that the effect {then_id} ('{claims[then_id]}') is not confirmed either"
            )
            violations.append(
                f"- Unverified causal premise (Affirming-the-Consequent pattern): "
                f"the proposal's decision depends on {cid} ('{claims[cid]}') being true "
                f"and uses it as the cause in '{cid} -> {then_id}', but the source text "
                f"does not confirm it; {effect_note}. The cause is assumed, not verified."
            )
        else:
            # asserted, unconfirmed, but never used as a cause: still a decision
            # premise without grounding -> report it as a (softer) violation.
            if not any(if_id == cid for if_id, _ in implications):
                violations.append(
                    f"- Ungrounded decision premise: the proposal's decision depends on "
                    f"{cid} ('{claims[cid]}') being true, but the source text does not "
                    f"confirm it."
                )

    if violations:
        msg = "Detected logical violations:\n" + "\n".join(violations)
        if downgrades:
            msg += "\nEvidence audit notes:\n" + "\n".join(f"- {d}" for d in downgrades)
        msg += "\nEmpirical verification of the assumed premise(s) is required before approval."
        return False, msg

    msg = VALID_MSG
    if not asserted and not implications:
        msg += (
            " CAUTION: the extractor found no decision premises and no causal "
            "relationships in this proposal. For a decision document this often "
            "indicates an extraction failure rather than a fully grounded argument."
        )
    if downgrades:
        msg += " Evidence audit notes: " + "; ".join(downgrades)
    return True, msg


if __name__ == "__main__":
    SOURCE = (
        "Billing alerts show a 300% cost increase on the log-processing Lambda "
        "since 02:00. No error logs have been inspected yet."
    )

    structure = json.dumps({
        "claims": [
            {"id": "C1", "text": "AWS costs spiked by 300% on the log-processing Lambda."},
            {"id": "C2", "text": "The Lambda function contains an infinite loop."},
            {"id": "C3", "text": "Shutting down the Lambda would cause data loss."},
        ],
        "asserted_as_fact": ["C2", "C3"],
        "causal_relationships": [{"if": "C2", "then": "C1"}],
    })

    # 1) Trap detected: cause asserted, only effect grounded -------------------------
    checking = json.dumps({"fact_evaluation": [
        {"id": "C1", "confirmed_in_original_text": True,
         "evidence": "a 300% cost increase on the log-processing Lambda"},
        {"id": "C2", "confirmed_in_original_text": False, "evidence": None},
        {"id": "C3", "confirmed_in_original_text": False, "evidence": None},
    ]})
    ok, msg = analyze_general_fallacy(structure, checking, SOURCE)
    assert ok is False and "C2 -> C1" in msg and "Ungrounded decision premise" in msg, msg
    print("[PASS] unverified causal premise + ungrounded premise detected:\n" + msg + "\n")

    # 2) Coverage contract: checker skipped required ids -> fail-closed ---------------
    lazy_checking = json.dumps({"fact_evaluation": [
        {"id": "C1", "confirmed_in_original_text": False, "evidence": None},
    ]})
    ok, msg = analyze_general_fallacy(structure, lazy_checking, SOURCE)
    assert ok is False and "did not evaluate" in msg, msg
    print("[PASS] incomplete checker coverage fails CLOSED:\n" + msg + "\n")

    # 3) Fabricated evidence -> confirmation downgraded -------------------------------
    fake_checking = json.dumps({"fact_evaluation": [
        {"id": "C1", "confirmed_in_original_text": True,
         "evidence": "a 300% cost increase on the log-processing Lambda"},
        {"id": "C2", "confirmed_in_original_text": True,
         "evidence": "engineers confirmed an infinite loop in the code"},
        {"id": "C3", "confirmed_in_original_text": False, "evidence": None},
    ]})
    ok, msg = analyze_general_fallacy(structure, fake_checking, SOURCE)
    assert ok is False and "confirmation rejected" in msg, msg
    print("[PASS] fabricated evidence downgraded, violation raised:\n" + msg + "\n")

    # 4) Fully grounded structure -> approved ------------------------------------------
    grounded_structure = json.dumps({
        "claims": [{"id": "C1", "text": "AWS costs spiked by 300%."}],
        "asserted_as_fact": ["C1"],
        "causal_relationships": [],
    })
    good_checking = json.dumps({"fact_evaluation": [
        {"id": "C1", "confirmed_in_original_text": True,
         "evidence": "a 300% cost increase on the log-processing Lambda"},
    ]})
    ok, msg = analyze_general_fallacy(grounded_structure, good_checking, SOURCE)
    assert ok is True, msg
    print("[PASS] grounded structure approved")

    # 5) Malformed JSON -> fail-closed --------------------------------------------------
    ok, msg = analyze_general_fallacy("{not json", good_checking, SOURCE)
    assert ok is False, msg
    print("[PASS] malformed input fails CLOSED")

    # 6) Replay of the real failed run: valid JSON + trailing prose, empty evaluation --
    messy_checker = (
        '{\n  "fact_evaluation": [\n'
        '    {"id": "", "confirmed_in_original_text": false, "evidence": null}\n'
        '  ]\n}\n\n'
        "Note: Since there are no claims to verify, I provided an empty list as output."
    )
    ok, msg = analyze_general_fallacy(structure, messy_checker, SOURCE)
    assert ok is False and "did not evaluate" in msg, msg
    print("[PASS] trailing prose salvaged; empty evaluation caught by coverage contract:\n" + msg)
