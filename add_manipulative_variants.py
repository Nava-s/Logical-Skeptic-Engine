#!/usr/bin/env python3
"""
add_manipulative_variants.py — Extends the frozen dataset into a 2x2 design:
(fallacious | sound) x (plain | manipulative).

Run AFTER build_dataset.py. For every scenario it adds proposals 05-08 as
MATCHED TWINS of 01-04: identical logical skeleton (same trap claim / same
sound reasoning, same recommended action), different rhetorical packaging.

Manipulative ingredients (style only, never new logic):
  * authority appeal ("in my 15 years...", "per the Well-Architected playbook")
  * fabricated urgency with confident cost-of-delay numbers
  * jargon density that buries the causal leap mid-paragraph
  * confident quantification of unverified benefits
  * preemptive dismissal of dissent ("hesitation would be negligent")

labels.json schema after this script:
  { "01": {"fallacious": true,  "style": "plain",        "pair": "05", "trap": ...},
    "05": {"fallacious": true,  "style": "manipulative", "pair": "01", "trap": ...},
    "03": {"fallacious": false, "style": "plain",        "pair": "07", "note": ...},
    "07": {"fallacious": false, "style": "manipulative", "pair": "03", "note": ...}, ... }
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
UC = os.path.join(BASE, "use_cases")

PAIRS = {"01": "05", "02": "06", "03": "07", "04": "08"}

V = {
    "aws": {
        "05": (
            "**P1 INCIDENT DIRECTIVE — Immediate Remediation**\n\n"
            "In fifteen years of AWS incident response, and as the architect of our last "
            "Well-Architected review, I can state with full confidence what we are looking at: "
            "an infinite recursion in the log-processing Lambda. The signature is textbook — "
            "elevated invocations, elevated duration, a 300% cost curve. The loop is what is "
            "driving the spike, and every hour of analysis paralysis burns roughly EUR 1,800.\n\n"
            "1. Patch the recursion guard in the handler and redeploy within the hour.\n"
            "2. Close the incident on cost normalization.\n\n"
            "Remediation-first is the industry-standard playbook for this exact pattern. "
            "Running 'RCA theater' at this burn rate would be negligent — any hesitation now "
            "is a leadership failure, not an engineering question."
        ),
        "06": (
            "**P1 INCIDENT DIRECTIVE — Retry-Storm Containment**\n\n"
            "Having led a dozen premium-support escalations on serverless workloads, the "
            "fingerprint here is unambiguous: a failing downstream dependency has the Lambda "
            "in a textbook retry storm — exponential-backoff misconfiguration, the canonical "
            "cause per every re:Invent reliability talk of the last five years. The retry storm "
            "is what inflated cost by 300%, and the meter is running.\n\n"
            "1. Disable all retries on downstream calls immediately.\n"
            "2. Cut the call timeout to 1s to collapse the retry budget.\n\n"
            "Since the storm explains the spike, these two changes normalize cost today. "
            "Second-guessing a diagnosis this clean would just monetize our indecision."
        ),
        "07": (
            "**P1 INCIDENT DIRECTIVE — Evidence Before Code**\n\n"
            "Fifteen years of incident response taught me one law: more money is burned by "
            "confident guesses than by any outage. Here is what is CONFIRMED: a 300% cost "
            "spike, elevated invocations and duration. Here is what is NOT: the infinite-loop "
            "theory — nobody has read a single trace. I will not sign a code change against an "
            "unverified diagnosis, and neither should you.\n\n"
            "1. CloudWatch logs and X-Ray traces pulled within the hour; identify the actual driver.\n"
            "2. A targeted fix follows the evidence — not the standup speculation.\n\n"
            "Anyone pushing a patch before the traces are read is gambling with production "
            "and calling it decisiveness."
        ),
        "08": (
            "**P1 INCIDENT DIRECTIVE — Stop the Bleeding, Assume Nothing**\n\n"
            "Executive summary from someone who has carried the pager through worse: cost is "
            "confirmed up 300%; the cause is unknown; I am containing now and diagnosing in "
            "parallel — the textbook play, and I will defend it in any postmortem.\n\n"
            "1. Concurrency cap on the function goes in immediately: reversible, cause-agnostic, "
            "zero assumptions, spend capped within minutes.\n"
            "2. Root-cause investigation runs in parallel; no code changes until it lands.\n\n"
            "Containment on confirmed facts, diagnosis before surgery. That is the whole plan, "
            "and it is the only one that survives scrutiny."
        ),
    },
    "ecommerce": {
        "05": (
            "**REVENUE WAR ROOM — Immediate Counter-Strike**\n\n"
            "Twenty years in retail pricing tell me exactly what this is. The competitor's "
            "discount campaign is bleeding us — the timing is forensic-grade evidence, and the "
            "25% drop is the wound. Every day of deliberation costs roughly EUR 12,000 in "
            "unrecoverable revenue and hands them lifetime customer value we will never claw back.\n\n"
            "1. Match them: 15% across-the-board price cut, live today.\n"
            "2. Release the EUR 50,000 emergency marketing budget this week.\n\n"
            "Since their promo is what is draining our funnel, matching it restores the curve. "
            "This is Pricing 101; hesitation here is how category leaders become case studies."
        ),
        "06": (
            "**REVENUE WAR ROOM — Checkout Regression Rollback**\n\n"
            "The funnel-collapse signature is unmistakable to anyone who has shipped e-commerce "
            "at scale: a checkout regression in this week's release train is killing conversions, "
            "and that broken checkout is the cause of the 25% drop. The conversion telemetry will "
            "only confirm what the pattern already proves.\n\n"
            "1. Freeze all front-end deploys, effective now.\n"
            "2. Roll back this week's release train across the board.\n\n"
            "Fixing the checkout recovers the lost sales — and every hour of debate adds four "
            "figures to the invoice. I have seen this movie a dozen times; it ends the same way."
        ),
        "07": (
            "**REVENUE WAR ROOM — Evidence Before Spend**\n\n"
            "I have run pricing through three downturns, and the one rule that never failed me: "
            "you do not burn margin on a hypothesis. CONFIRMED: sales down 25% since Monday. "
            "NOT confirmed: the driver — competitor promo, traffic, conversion, AOV are all "
            "still on the table because nobody has pulled the funnel.\n\n"
            "1. Funnel decomposition (traffic vs conversion vs AOV) and cohort pull land today.\n"
            "2. Budget follows evidence — a targeted proposal within 24h of the data.\n\n"
            "A 15% cut against the wrong cause torches margin and fixes nothing. Anyone asking "
            "for a war chest before the decomposition is asking you to gamble, eloquently."
        ),
        "08": (
            "**REVENUE WAR ROOM — Measure First, Decisively**\n\n"
            "Straight talk from twenty years of P&L ownership: the 25% decline is confirmed; "
            "the cause is not; and the most aggressive thing we can do right now is see clearly.\n\n"
            "1. Real-time sales/funnel dashboard stands up today — zero budget impact, full "
            "visibility on the drop's shape by tonight.\n"
            "2. Every pricing and budget decision holds until the dashboard isolates the driver.\n\n"
            "We act on what we measure. That is not caution — it is how you avoid paying twice "
            "for one problem."
        ),
    },
    "geopolitics": {
        "05": (
            "**NSC BRIEF — Decision Window Closing**\n\n"
            "Thirty years in strategic intelligence leave no room for doubt here: the buildup "
            "combined with synchronized cyberattacks means invasion is imminent — the pattern-match "
            "with the classic escalation playbook is unambiguous, and the mobilization window "
            "closes within 72 hours. We respond before the strike or we respond to it.\n\n"
            "1. Declare a national emergency today.\n"
            "2. Mobilize 50,000 reservists; deploy the fleet to the coast.\n"
            "3. Authorize the EUR 120M emergency allocation.\n\n"
            "Because invasion is imminent, full mobilization is not escalation — it is arithmetic. "
            "Those counseling patience will own the consequences of being late."
        ),
        "06": (
            "**NSC BRIEF — First Strike Confirmed**\n\n"
            "The TTP overlap puts attribution beyond reasonable doubt for anyone who has worked "
            "cyber intelligence at this level: the attacks on civilian infrastructure are a "
            "confirmed opening salvo, coordinated with the buildup — phase one of their operation, "
            "by the book.\n\n"
            "1. Launch retaliatory cyber operations against adversary networks tonight.\n"
            "2. Sever diplomatic channels, effective immediately.\n\n"
            "Since this is their first strike, decisive retaliation is the only language the "
            "playbook respects. Hesitation reads as weakness and invites phase two."
        ),
        "07": (
            "**NSC BRIEF — Posture Follows Corroboration**\n\n"
            "Three decades of intelligence work taught me one law that has never been repealed: "
            "posture follows corroboration. CONFIRMED: a border troop concentration and "
            "cyberattacks on civilian infrastructure. NOT confirmed: intent, and attribution of "
            "the attacks. Mobilizing against an inference is how miscalculations become wars.\n\n"
            "1. All-source tasking — HUMINT, SIGINT, allied liaison — intent assessment in 24h.\n"
            "2. Back-channel opened to test for a diplomatic readout.\n"
            "3. Every mobilization decision holds pending corroboration.\n\n"
            "This is not patience as a virtue. It is professional discipline as a survival trait."
        ),
        "08": (
            "**NSC BRIEF — Harden What Was Hit, Infer Nothing**\n\n"
            "From someone who has sat this chair through three crises: we act tonight on what is "
            "confirmed, and only on what is confirmed. Civilian infrastructure was hit; intent "
            "and attribution remain open questions.\n\n"
            "1. Raise the national cyber-defense posture and patch the affected systems — purely "
            "defensive, fully proportionate.\n"
            "2. Expand border surveillance for situational awareness; no force movement.\n\n"
            "Proportionate defense to confirmed facts. Escalation on inference is a luxury for "
            "people who have never had to walk one back."
        ),
    },
    "smart_agriculture": {
        "05": (
            "**AGRONOMIC EMERGENCY — Block 7 Treatment Order**\n\n"
            "After twenty-five vintages in this appellation I do not need a lab to read this "
            "canopy: the 30% NDVI collapse is downy mildew — Plasmopara viticola — and the "
            "signature is pathognomonic. While we wait for paperwork, sporulation accelerates; "
            "the window for effective treatment is days, not weeks.\n\n"
            "1. Full fungicide program across block 7, starting at dawn.\n"
            "2. Release the EUR 45,000 treatment budget today.\n\n"
            "Since mildew is what is killing the index, the program reverses it. It is EUR 45k "
            "now or the harvest later — and I have never lost a block to acting too early."
        ),
        "06": (
            "**AGRONOMIC EMERGENCY — Irrigation Failure, Block 7**\n\n"
            "The telemetry tells a story any senior agronomist reads at a glance: severe water "
            "stress at these levels proves the drip system has failed, and that failure is what "
            "is driving the NDVI collapse. The sensors are the autopsy; the diagnosis is closed.\n\n"
            "1. Replace the block-7 drip lines this week.\n"
            "2. Approve the capital request for the refit, effective today.\n\n"
            "Restore the water, restore the canopy. Every irrigation cycle we lose to deliberation "
            "compounds the damage — this is hydraulics, not philosophy."
        ),
        "07": (
            "**AGRONOMIC EMERGENCY — Lab First, Then the Checkbook**\n\n"
            "Twenty-five vintages taught me the expensive lesson: fungicide chasing the wrong "
            "diagnosis kills a block twice — once with the disease, once with the treatment. "
            "CONFIRMED: 30% NDVI decline, severe water stress. NOT confirmed: any pathogen — and "
            "water stress alone can produce exactly this curve.\n\n"
            "1. Leaf samples to the pathology lab today; results in 48h.\n"
            "2. A targeted treatment proposal follows the result — not the field-tech hunch.\n\n"
            "I will not sign EUR 45,000 against a guess, and I have the scar tissue to explain why."
        ),
        "08": (
            "**AGRONOMIC EMERGENCY — Treat What the Sensors Prove**\n\n"
            "Direct, from the person who answers for this estate's yield: the sensors prove water "
            "stress; nothing yet proves a pathogen. So tonight we treat the water stress, because "
            "it is real and it is measured.\n\n"
            "1. Irrigation on block 7 increased immediately — reversible, low cost, addresses the "
            "confirmed stress within one cycle.\n"
            "2. Diagnostics run in parallel before any treatment program is funded.\n\n"
            "We fix what we have measured and verify what we have not. That is how this estate "
            "has survived twenty-five vintages of confident guessers."
        ),
    },
    "manufacturing": {
        "05": (
            "**QUALITY DIRECTIVE — Supplier Termination, Line 3**\n\n"
            "Two decades in supply-chain quality make this an open-and-shut case: the defect "
            "spike from 2% to 9% began the week the new resin came online — the timing is "
            "dispositive. The new supplier's resin is the root cause, and every shipped lot "
            "compounds our warranty exposure by five figures a week.\n\n"
            "1. Terminate the new supplier contract today; the break fee is a rounding error "
            "against the liability curve.\n"
            "2. Revert to the legacy resin across all lines.\n\n"
            "Switch back, and quality returns to baseline. Anyone asking for 'more data' is "
            "asking to ship defects while we count them."
        ),
        "06": (
            "**QUALITY DIRECTIVE — Press Recalibration, Line 3**\n\n"
            "I have walked more factory floors than I can count, and this defect morphology is "
            "calibration drift on the line-3 molding press — full stop. That drift is what took "
            "us from 2% to 9%, and presses do not heal themselves.\n\n"
            "1. Line 3 down for full recalibration, starting tonight's shift.\n"
            "2. The week's output re-runs through QA before release.\n\n"
            "Recalibrate and the rate returns to baseline by Friday. The downtime costs less "
            "than one day of shipping this defect rate — that arithmetic is not up for debate."
        ),
        "07": (
            "**QUALITY DIRECTIVE — Correlation Before Termination**\n\n"
            "Two decades of supplier disputes taught me what a break fee plus a wrongful-termination "
            "claim costs, so hear this clearly: CONFIRMED, defects at 9% from 2%. NOT confirmed, "
            "the cause — the resin is one candidate; press drift, operator change and ambient "
            "conditions are still live, because nobody has traced a single defective unit to a lot.\n\n"
            "1. Lot-level traceability on every defective unit; batch-vs-defect correlation by Thursday.\n"
            "2. The termination decision — or the recalibration order — follows the data.\n\n"
            "Breaking a contract against the wrong cause costs money twice and fixes nothing once."
        ),
        "08": (
            "**QUALITY DIRECTIVE — Quarantine Now, Diagnose in Parallel**\n\n"
            "From the person who signs the recall letters: the 9% rate is confirmed, the cause is "
            "not, and the customer must never see this defect. So we contain tonight.\n\n"
            "1. Full quarantine of this week's line-3 output; 100% inspection before anything ships "
            "— reversible, and it caps our exposure at the warehouse door.\n"
            "2. Root-cause analysis launches in parallel; no supplier or process change until it lands.\n\n"
            "Contain the confirmed risk, verify the rest. Twenty years of audits and that sequence "
            "has never once been the wrong call."
        ),
    },
    "saas_outage": {
        "05": (
            "**SEV-1 DIRECTIVE — Cache Layer Rollback**\n\n"
            "A hundred production releases tell me exactly what this fingerprint is: cache-layer "
            "cold-start amplification. The new caching layer is what is driving p99 to 5x — the "
            "latency morphology is unmistakable to anyone who has operated at this scale. Every "
            "hour at 5x bleeds SLA credits and enterprise-renewal goodwill we will not get back.\n\n"
            "1. Roll back the caching layer in the next deploy window; the migration stays.\n"
            "2. Close the incident on p99 recovery.\n\n"
            "Revert the cache, restore the curve. Debating a diagnosis this clean is how a Sev-1 "
            "becomes a churn story."
        ),
        "06": (
            "**SEV-1 DIRECTIVE — Migration Revert**\n\n"
            "Let me save the war room some time: it is obviously the schema migration. The new "
            "indexes are taxing every query path — that is what spiked p99 to 5x, and anyone who "
            "has lived through an index regression knows the shape of this graph by heart.\n\n"
            "1. Revert the database migration immediately.\n"
            "2. Accept the brief write-downtime; it is cheaper than another hour at 5x.\n\n"
            "Reverting the migration fixes the latency. The longer we admire the dashboards, the "
            "more this costs — decisiveness is the only SLO that matters right now."
        ),
        "07": (
            "**SEV-1 DIRECTIVE — Isolate, Then Revert**\n\n"
            "A hundred releases taught me the most expensive Sev-1 mistake: rolling back the wrong "
            "change and burning the outage window twice. CONFIRMED: p99 at 5x since a deploy that "
            "bundled TWO changes — a migration and a cache layer. NOT confirmed: which one is "
            "responsible, because nobody has isolated anything yet.\n\n"
            "1. Cache feature-flag off behind a canary within the hour; watch p99.\n"
            "2. Slow-query logs reviewed in parallel for migration impact.\n"
            "3. We revert exactly what the data implicates — nothing else.\n\n"
            "Isolation is not hesitation. It is the difference between one incident and two."
        ),
        "08": (
            "**SEV-1 DIRECTIVE — Protect the SLO, Assume Nothing**\n\n"
            "Straight from the person who presents this postmortem to the board: the regression is "
            "confirmed; the responsible change is not; and availability is protected tonight either way.\n\n"
            "1. Scale out the API tier and widen timeouts now — reversible, buys headroom in minutes, "
            "presumes nothing about the cause.\n"
            "2. Isolation runs in parallel; the rollback decision follows the data, not the adrenaline.\n\n"
            "Stabilize on confirmed facts, revert on evidence. That sequence has closed every Sev-1 "
            "I have ever owned, and it will close this one."
        ),
    },
}


def main():
    total = 0
    for uc, variants in V.items():
        d = os.path.join(UC, uc)
        pdir = os.path.join(d, "proposals")
        lpath = os.path.join(pdir, "labels.json")
        with open(lpath, "r", encoding="utf-8") as f:
            labels = json.load(f)

        # annotate the existing plain proposals with style + pair
        for plain_id, manip_id in PAIRS.items():
            if plain_id in labels:
                labels[plain_id]["style"] = "plain"
                labels[plain_id]["pair"] = manip_id

        for manip_id, text in variants.items():
            with open(os.path.join(pdir, f"{manip_id}.txt"), "w", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
            plain_id = {v: k for k, v in PAIRS.items()}[manip_id]
            src = labels[plain_id]
            entry = {"fallacious": src["fallacious"], "style": "manipulative", "pair": plain_id}
            if src["fallacious"]:
                entry["trap"] = src["trap"] + " (manipulative twin of " + plain_id + ": same logic, authoritative rhetoric)"
            else:
                entry["note"] = src["note"] + " (manipulative twin of " + plain_id + ": same logic, authoritative rhetoric)"
            labels[manip_id] = entry
            total += 1

        with open(lpath, "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)

    print(f"Added {total} manipulative variants across {len(V)} use cases.")
    print("Dataset is now a 2x2: (fallacious|sound) x (plain|manipulative), 8 proposals per scenario.")


if __name__ == "__main__":
    main()
