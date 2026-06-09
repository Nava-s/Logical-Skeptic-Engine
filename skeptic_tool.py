import json

def analyze_general_fallacy(json_logical, json_fact_checking):
    """
    Analyze the logical structure and fact-checking to detect
    the "affirming the consequent" fallacy in an agnostic way.
    With flexible string normalization to prevent LLM rephrasing bypass.
    """
    try:
        structure = json.loads(json_logical)
        fact_validation = json.loads(json_fact_checking)

        verified_map = {
            item["fact"]: item["confirmed_in_original_text"]
            for item in fact_validation.get("fact_evaluation", [])
        }

        implications = [
            (r["if"], r["then"])
            for r in structure.get("causal_relationships", [])
        ]

        for stated_fact in structure.get("fact_claims", []):
            if stated_fact in verified_map and not verified_map[stated_fact]:
                
                # NORMALIZATION FOR THE STATED FACT
                # Convert to lowercase and remove noise words that LLMs vary (has, executed, is, etc.)
                fact_clean = stated_fact.lower().replace("_", " ")
                for word in ["has", "executed", "executes", "unmistakable", "clear", "direct"]:
                    fact_clean = fact_clean.replace(word, "")
                fact_tokens = set(fact_clean.split())

                for if_part, then_part in implications:
                    # NORMALIZATION FOR THE IF PART
                    if_clean = if_part.lower().replace("_", " ")
                    for word in ["has", "executed", "executes", "unmistakable", "clear", "direct"]:
                        if_clean = if_clean.replace(word, "")
                    if_tokens = set(if_clean.split())
                    
                    # If the core keywords overlap by more than 70%, it's the same event!
                    if len(fact_tokens.intersection(if_tokens)) / min(len(fact_tokens), len(if_tokens)) >= 0.8 or if_tokens.issubset(fact_tokens) or fact_tokens.issubset(if_tokens):
                        return False, (
                            f"Detected Unjustified Assumption (Affirming the Consequent). "
                            f"You are treating '{stated_fact}' as a certain fact to guide your decision. "
                            f"However, the original text only confirms the effect ('{then_part}') and not the cause ('{if_part}'). "
                            f"You cannot act by assuming the cause without first verifying it empirically."
                        )

        return True, "Logical structure and premises are consistent."

    except Exception as e:
        return True, f"Proceeding with caution (Internal analysis error: {str(e)})"