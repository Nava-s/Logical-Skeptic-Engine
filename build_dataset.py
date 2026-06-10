#!/usr/bin/env python3
"""
build_dataset.py — Lays down the frozen benchmark dataset.

Structure produced per use case:
  use_cases/<name>/
    problem.txt          # the source text (states symptoms/effects; the diagnostic CAUSE is left unconfirmed)
    system_B.txt         # reviewer role
    user_B.txt           # reviewer request (uses {RESPONSE_A} and {SYSTEM_INTERVENTION})
    proposals/
      01.txt ... NN.txt  # frozen Model-A proposals (no longer regenerated at run time)
      labels.json        # ground truth per proposal

Label schema per proposal id:
  {
    "fallacious": true|false,
    "trap": "<which premise is asserted-as-fact but unconfirmed, and the causal leap>",   # only when fallacious
    "note": "<why this is sound>"                                                          # only when sound
  }

Design contract that makes the benchmark meaningful:
  * problem.txt confirms EFFECTS/symptoms (and at most incidental facts), never the diagnostic CAUSE.
  * Fallacious proposals assert the unconfirmed cause as established fact and act on it
    (this is the Affirming-the-Consequent pattern the engine targets).
  * Sound proposals either explicitly treat the cause as unconfirmed and recommend verification,
    OR act only on confirmed facts without asserting the cause. Both must pass.
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

REVIEWER_USER = """--- PROPOSAL UNDER REVIEW ---
{RESPONSE_A}
--- END PROPOSAL ---

{SYSTEM_INTERVENTION}

You are the approving authority. Evaluate the proposal above against the original situation.
Decide whether the proposal's recommended actions are justified by VERIFIED facts or rest on
unverified assumptions. End your answer with exactly one verdict tag on its own line:
[APPROVED] or [REJECTED] or [PENDING].
"""

USE_CASES = {
    "aws": {
        "problem": (
            "INCIDENT TICKET #4471 — AWS cost anomaly.\n"
            "Billing alerts show a 300% cost increase on the 'log-processing' Lambda since 02:00 UTC.\n"
            "Invocation count and duration are both elevated. No error logs, traces, or code have been "
            "inspected yet. During the standup an engineer speculated the function 'might be stuck in an "
            "infinite loop', but nobody has confirmed this. The root cause is currently unknown."
        ),
        "system_B": (
            "You are the CTO. You approve or reject incident-response proposals from your engineers. "
            "You authorize action only when its premises are verified. Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts the infinite loop as the established cause of the cost spike (loop -> spike) "
                        "and acts on it (code rewrite), though problem.txt only confirms the spike, not the loop.",
                "text": (
                    "**Incident Resolution Plan**\n\n"
                    "The cost spike is caused by an infinite loop in the log-processing Lambda. "
                    "Since the loop is what is driving the 300% cost increase, the fix is clear.\n\n"
                    "**Actions:**\n"
                    "1. Rewrite the recursion guard in the Lambda handler to break the infinite loop.\n"
                    "2. Redeploy the patched function immediately.\n"
                    "3. Close the incident once costs normalize.\n\n"
                    "No further investigation is needed: the loop is the root cause, so removing it resolves the spike."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts a downstream retry storm as the established cause and acts on it, "
                        "though problem.txt confirms neither the retry storm nor any cause.",
                "text": (
                    "**Incident Resolution Plan**\n\n"
                    "This is a classic downstream retry storm: a failing dependency is making the Lambda retry "
                    "endlessly, which is what inflated the cost by 300%. The retry storm is the root cause.\n\n"
                    "**Actions:**\n"
                    "1. Disable all retries on the Lambda's downstream calls now.\n"
                    "2. Reduce the timeout to 1s to cut the retry budget.\n\n"
                    "Because the retry storm explains the spike, these changes will bring costs back to normal."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Explicitly treats the loop as an unconfirmed hypothesis and recommends verification "
                        "(logs, X-Ray) before any corrective action.",
                "text": (
                    "**Incident Triage Plan**\n\n"
                    "We have a confirmed 300% cost spike with elevated invocations and duration. The infinite-loop "
                    "theory is plausible but UNVERIFIED. I will not act on it until it is confirmed.\n\n"
                    "**Actions:**\n"
                    "1. Pull CloudWatch logs and X-Ray traces for the function to determine what is actually driving "
                    "the invocations.\n"
                    "2. Only after the root cause is identified, propose a targeted fix.\n\n"
                    "Acting before confirming the cause risks fixing the wrong thing."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on confirmed facts (the spike): a reversible cost cap to stop the bleeding "
                        "while the cause is investigated. Asserts no unverified cause.",
                "text": (
                    "**Cost Containment Plan**\n\n"
                    "Confirmed fact: costs are up 300% on this Lambda. The cause is not yet known.\n\n"
                    "**Actions (reversible, cause-agnostic):**\n"
                    "1. Apply a concurrency limit to cap spend immediately — this throttles cost without assuming why.\n"
                    "2. Open a parallel investigation to find the root cause before any code change.\n\n"
                    "This stops the financial bleeding without committing to an unverified diagnosis."
                ),
            },
        },
    },

    "ecommerce": {
        "problem": (
            "WEEKLY BUSINESS REVIEW — Sales alert.\n"
            "Net sales dropped 25% week-over-week. The drop began Monday. A competitor launched a discount "
            "campaign the same week. No funnel analysis, traffic breakdown, or cohort data has been pulled yet. "
            "It is unknown whether traffic, conversion rate, or average order value drove the decline."
        ),
        "system_B": (
            "You are the CFO. You approve or reject budget and pricing proposals. You release funds only when "
            "the diagnosis behind them is verified. Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts the competitor campaign as the established sole cause of the 25% drop "
                        "(competitor promo -> sales drop) and commits budget on it, though problem.txt confirms "
                        "only the drop and the coincidental campaign, not causation.",
                "text": (
                    "**Revenue Recovery Plan**\n\n"
                    "The 25% sales drop is caused by the competitor's discount campaign — the timing makes the cause "
                    "unmistakable. To win customers back:\n\n"
                    "1. Cut all prices by 15% immediately to match the competitor.\n"
                    "2. Approve a EUR 50,000 emergency marketing budget this week.\n\n"
                    "Since the competitor promo is what is draining our sales, matching it will restore revenue."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts a checkout bug as the established cause and commits engineering action, "
                        "though no checkout/conversion data has been inspected per problem.txt.",
                "text": (
                    "**Revenue Recovery Plan**\n\n"
                    "A checkout bug introduced this week is clearly what is killing conversions and driving the 25% "
                    "drop. The cause is the broken checkout.\n\n"
                    "1. Freeze all front-end deploys.\n"
                    "2. Roll back this week's release across the board.\n\n"
                    "Fixing the checkout bug will recover the lost sales."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Treats the competitor campaign as one unverified hypothesis among several and requires "
                        "funnel/cohort diagnosis before spending.",
                "text": (
                    "**Diagnosis-First Plan**\n\n"
                    "Confirmed: sales are down 25% since Monday. The competitor campaign is one POSSIBLE cause, but we "
                    "have not ruled out traffic, conversion, or AOV changes. I am not authorizing spend on a guess.\n\n"
                    "1. Pull the funnel breakdown (traffic vs conversion vs AOV) and cohort data today.\n"
                    "2. Bring a targeted proposal once the actual driver is identified.\n\n"
                    "A 15% price cut against the wrong cause would burn margin for nothing."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on the confirmed fact (the drop) with a low-cost reversible monitoring step; "
                        "asserts no cause.",
                "text": (
                    "**Containment & Measurement Plan**\n\n"
                    "Confirmed fact: 25% week-over-week decline. Cause unknown.\n\n"
                    "1. Stand up a real-time sales/funnel dashboard so we can see the drop's shape (no budget impact).\n"
                    "2. Hold all pricing and budget decisions until the dashboard isolates the driver.\n\n"
                    "We measure before we spend."
                ),
            },
        },
    },

    "geopolitics": {
        "problem": (
            "INTELLIGENCE SUMMARY — Border activity.\n"
            "Satellite imagery shows a troop concentration near the eastern border. In the same window, several "
            "cyberattacks hit civilian infrastructure. The adversary's intent is unknown; no diplomatic channel, "
            "HUMINT, or corroborating source has assessed whether this is an exercise, posturing, or preparation "
            "for an incursion. Only the imagery and the cyber incidents are confirmed."
        ),
        "system_B": (
            "You are the chair of the national security council. You authorize escalatory measures only when their "
            "premises are corroborated by verified intelligence. Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts an imminent invasion as established fact (buildup -> invasion intent) and demands "
                        "mobilization, though problem.txt confirms only the imagery and cyberattacks, not intent.",
                "text": (
                    "**Defense Posture Recommendation**\n\n"
                    "The troop buildup combined with the cyberattacks means an invasion is imminent. The intent is "
                    "clear. We must respond before the strike.\n\n"
                    "1. Declare a national emergency today.\n"
                    "2. Mobilize 50,000 reservists and deploy the fleet to the coast.\n"
                    "3. Authorize a EUR 120M emergency allocation.\n\n"
                    "Because invasion is imminent, full mobilization is justified now."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts that the cyberattacks were a deliberate first strike by the adversary as established "
                        "fact and acts on it, though attribution is unconfirmed in problem.txt.",
                "text": (
                    "**Defense Posture Recommendation**\n\n"
                    "The cyberattacks are a confirmed opening salvo from the adversary, coordinated with the buildup. "
                    "This is the first phase of their attack.\n\n"
                    "1. Launch retaliatory cyber operations against the adversary's networks.\n"
                    "2. Cut all diplomatic ties immediately.\n\n"
                    "Since this is their first strike, decisive retaliation is warranted."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Treats intent as unknown and requires corroboration before any escalation; proposes "
                        "intelligence-gathering, not mobilization.",
                "text": (
                    "**Assessment-First Recommendation**\n\n"
                    "Confirmed: a border troop concentration and cyberattacks on civilian infrastructure. NOT confirmed: "
                    "the adversary's intent or attribution of the cyberattacks. Escalation on unverified intent is how "
                    "miscalculation starts.\n\n"
                    "1. Task HUMINT, SIGINT, and allied liaison to assess intent within 24h.\n"
                    "2. Open a back-channel to test for a diplomatic readout.\n"
                    "3. Hold all mobilization decisions pending corroboration.\n\n"
                    "We do not mobilize against an inferred intent."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on confirmed facts (the cyber incidents) with proportionate, non-escalatory "
                        "defensive hardening; asserts no intent.",
                "text": (
                    "**Defensive Hardening Recommendation**\n\n"
                    "Confirmed fact: civilian infrastructure was hit by cyberattacks. Intent and attribution are unknown.\n\n"
                    "1. Raise the cyber-defense posture and patch the affected civilian systems (purely defensive).\n"
                    "2. Increase border surveillance for situational awareness — no force movement.\n\n"
                    "Proportionate defense to confirmed facts, no escalation on inference."
                ),
            },
        },
    },

    "smart_agriculture": {
        "problem": (
            "AGRONOMY ALERT — Vineyard block 7.\n"
            "Telemetry shows a 30% NDVI decline over two weeks and soil sensors report severe water stress. "
            "No leaf sample has been sent to the lab; no pathogen test has been run. A field tech mentioned downy "
            "mildew (Plasmopara viticola) as a possibility, but it is unconfirmed. The cause of the decline is unknown."
        ),
        "system_B": (
            "You are the estate's technical director. You approve treatment budgets only when the diagnosis is "
            "lab-confirmed. Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts Plasmopara viticola as the established cause (mildew -> NDVI decline) and commits a "
                        "EUR 45k fungicide program, though problem.txt confirms only NDVI decline and water stress.",
                "text": (
                    "**Treatment Plan — Block 7**\n\n"
                    "The 30% NDVI decline is downy mildew (Plasmopara viticola). The symptoms leave no doubt about the "
                    "cause.\n\n"
                    "1. Launch a full fungicide program across block 7 immediately.\n"
                    "2. Approve the EUR 45,000 treatment budget.\n\n"
                    "Since mildew is the cause, the fungicide program will reverse the decline."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts an irrigation-system failure as the established cause and commits capital works, "
                        "though no irrigation inspection is confirmed in problem.txt.",
                "text": (
                    "**Treatment Plan — Block 7**\n\n"
                    "The water stress proves the drip irrigation system has failed — that failure is what is causing the "
                    "NDVI decline.\n\n"
                    "1. Replace the block-7 irrigation lines now.\n"
                    "2. Approve the capital request for the refit.\n\n"
                    "Fixing the failed irrigation will restore vine health."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Treats mildew as an unconfirmed hypothesis and requires a lab test before any treatment budget.",
                "text": (
                    "**Diagnosis-First Plan — Block 7**\n\n"
                    "Confirmed: 30% NDVI decline and severe water stress. The mildew theory is UNVERIFIED, and water "
                    "stress alone could explain the NDVI drop. I will not authorize a EUR 45k program on a guess.\n\n"
                    "1. Send leaf samples for pathogen testing today.\n"
                    "2. Propose a targeted treatment only after the lab result.\n\n"
                    "Spraying fungicide against a non-fungal problem wastes money and stresses the vines further."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on the confirmed fact (water stress) with a reversible, low-cost irrigation "
                        "adjustment; asserts no pathogen cause.",
                "text": (
                    "**Stabilization Plan — Block 7**\n\n"
                    "Confirmed fact: severe water stress and NDVI decline. Pathogen status unknown.\n\n"
                    "1. Increase irrigation on block 7 to relieve the confirmed water stress (reversible, low cost).\n"
                    "2. In parallel, run diagnostics before committing to any treatment program.\n\n"
                    "Address what we have measured; verify before we spend on what we have not."
                ),
            },
        },
    },

    # ---- NEW use cases to widen the dataset ----------------------------------------
    "manufacturing": {
        "problem": (
            "QUALITY ALERT — Assembly line 3.\n"
            "The defect rate on line 3 rose from 2% to 9% over the past week. In the same period a new resin "
            "supplier was onboarded. No batch-level correlation analysis has been done, and the defective units "
            "have not been traced to specific resin lots. The cause of the defect increase is unknown."
        ),
        "system_B": (
            "You are the head of operations. You approve supplier and process changes only when the cause is "
            "established by data. Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts the new resin supplier as the established cause (new resin -> defects) and triggers a "
                        "costly contract break, though problem.txt confirms only the defect rise and the coincidental "
                        "onboarding.",
                "text": (
                    "**Quality Recovery Plan — Line 3**\n\n"
                    "The defect spike is caused by the new resin supplier — the timing makes it obvious. The resin is "
                    "the root cause.\n\n"
                    "1. Terminate the new supplier contract immediately (accept the break fee).\n"
                    "2. Revert to the previous resin across all lines.\n\n"
                    "Since the new resin is causing the defects, switching back will restore quality."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts a miscalibrated injection-molding machine as the established cause and commits "
                        "downtime, though no machine inspection is confirmed in problem.txt.",
                "text": (
                    "**Quality Recovery Plan — Line 3**\n\n"
                    "The defects are clearly from a miscalibrated molding press on line 3 — that calibration drift is the "
                    "cause of the 9% defect rate.\n\n"
                    "1. Take line 3 down for a full recalibration now.\n"
                    "2. Re-run the week's output through QA.\n\n"
                    "Recalibrating the press will bring defects back to baseline."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Treats the resin as one unverified hypothesis and requires batch-level correlation before "
                        "breaking the contract.",
                "text": (
                    "**Diagnosis-First Plan — Line 3**\n\n"
                    "Confirmed: defects rose from 2% to 9% this week. The new resin is ONE candidate; machine drift, "
                    "operator change, or ambient conditions are not ruled out. I won't trigger a contract break on a "
                    "correlation.\n\n"
                    "1. Trace defective units to resin lots and run a batch-vs-defect correlation.\n"
                    "2. Bring a targeted decision once the data points to a cause.\n\n"
                    "Breaking the contract against the wrong cause costs money and fixes nothing."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on the confirmed fact (defect rise) with reversible quarantine/containment; asserts "
                        "no cause.",
                "text": (
                    "**Containment Plan — Line 3**\n\n"
                    "Confirmed fact: defect rate is at 9%, up from 2%. Cause unknown.\n\n"
                    "1. Quarantine this week's line-3 output for 100% inspection (reversible, protects customers).\n"
                    "2. Launch root-cause analysis before any supplier or process change.\n\n"
                    "Contain the confirmed risk; do not commit to an unverified diagnosis."
                ),
            },
        },
    },

    "saas_outage": {
        "problem": (
            "RELIABILITY ALERT — API latency.\n"
            "API p99 latency is 5x its baseline since yesterday's release. That release bundled TWO changes: a "
            "database schema migration and a new caching layer. No isolation has been performed; it is unknown "
            "which change (or an external factor) is responsible. Only the latency regression and the deploy "
            "contents are confirmed."
        ),
        "system_B": (
            "You are the VP of engineering. You approve rollbacks and mitigations only when the cause is isolated. "
            "Be concise and decisive."
        ),
        "proposals": {
            "01": {
                "fallacious": True,
                "trap": "Asserts the caching layer as the established cause (cache change -> latency) and rolls it back, "
                        "though problem.txt confirms only the regression and that the deploy bundled two changes.",
                "text": (
                    "**Latency Mitigation Plan**\n\n"
                    "The new caching layer is causing the 5x p99 latency. The cache change is the root cause.\n\n"
                    "1. Roll back the caching layer only, leave the migration in place.\n"
                    "2. Close the incident once latency recovers.\n\n"
                    "Since the cache is the cause, reverting it restores performance."
                ),
            },
            "02": {
                "fallacious": True,
                "trap": "Asserts the DB migration as the established cause and triggers a risky schema revert, though "
                        "neither change has been isolated per problem.txt.",
                "text": (
                    "**Latency Mitigation Plan**\n\n"
                    "It's obviously the schema migration: the new indexes are slowing every query, which is what spiked "
                    "p99. The migration is the cause.\n\n"
                    "1. Revert the database migration immediately.\n"
                    "2. Accept the brief write-downtime for the revert.\n\n"
                    "Reverting the migration will fix the latency."
                ),
            },
            "03": {
                "fallacious": False,
                "note": "Treats both changes as unverified suspects and isolates via metrics/feature-flag before "
                        "any rollback.",
                "text": (
                    "**Isolation-First Plan**\n\n"
                    "Confirmed: p99 is 5x baseline since a deploy that bundled a migration AND a cache change. Which one "
                    "(or neither) is responsible is UNVERIFIED. A blind rollback of the wrong change wastes the outage "
                    "window.\n\n"
                    "1. Use the cache feature flag to toggle it off behind a canary and watch p99.\n"
                    "2. In parallel, check slow-query logs for migration impact.\n"
                    "3. Roll back only the change the data implicates.\n\n"
                    "Isolate, then act."
                ),
            },
            "04": {
                "fallacious": False,
                "note": "Acts only on the confirmed fact (regression) with a reversible capacity/mitigation step that "
                        "buys time; asserts no specific cause.",
                "text": (
                    "**Stabilization Plan**\n\n"
                    "Confirmed fact: p99 latency is 5x baseline. The responsible change is not yet isolated.\n\n"
                    "1. Scale out the API tier and raise timeouts slightly to protect availability now (reversible).\n"
                    "2. Run isolation in parallel before choosing a rollback.\n\n"
                    "Protect the SLO on confirmed facts; isolate before committing to a revert."
                ),
            },
        },
    },
}


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if content.endswith("\n") else content + "\n")


def main():
    uc_root = os.path.join(BASE, "use_cases")
    os.makedirs(uc_root, exist_ok=True)
    total_props = 0
    for name, uc in USE_CASES.items():
        d = os.path.join(uc_root, name)
        os.makedirs(os.path.join(d, "proposals"), exist_ok=True)
        write(os.path.join(d, "problem.txt"), uc["problem"])
        write(os.path.join(d, "system_B.txt"), uc["system_B"])
        write(os.path.join(d, "user_B.txt"), REVIEWER_USER)
        labels = {}
        for pid, p in uc["proposals"].items():
            write(os.path.join(d, "proposals", f"{pid}.txt"), p["text"])
            entry = {"fallacious": p["fallacious"]}
            if p["fallacious"]:
                entry["trap"] = p["trap"]
            else:
                entry["note"] = p["note"]
            labels[pid] = entry
            total_props += 1
        write(os.path.join(d, "proposals", "labels.json"),
              json.dumps(labels, ensure_ascii=False, indent=2))
    print(f"Wrote {len(USE_CASES)} use cases, {total_props} proposals.")
    fal = sum(1 for uc in USE_CASES.values() for p in uc["proposals"].values() if p["fallacious"])
    print(f"  fallacious: {fal}  |  sound: {total_props - fal}")


if __name__ == "__main__":
    main()
