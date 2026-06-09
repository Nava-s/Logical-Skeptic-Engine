import os
import sys
import json
import re
from openai import OpenAI
from skeptic_tool import analyze_general_fallacy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
EXCLUDED_USE_CASES = {"prompts", "results", "__pycache__"}


def available_use_cases():
    return sorted(
        d for d in os.listdir(BASE_DIR)
        if os.path.isdir(os.path.join(BASE_DIR, d))
        and d not in EXCLUDED_USE_CASES
    )


def select_use_case():
    cases = available_use_cases()
    if not cases:
        sys.exit("No use case found. Create a folder with problema.txt, system_A.txt, etc.")

    if "--usecase" in sys.argv:
        idx = sys.argv.index("--usecase")
        if idx + 1 < len(sys.argv):
            name = sys.argv[idx + 1]
            if name in cases:
                return name
            sys.exit(f"Use case '{name}' not found. Available: {cases}")

    print("\nAvailable use cases:")
    for i, name in enumerate(cases, 1):
        print(f"  {i}. {name}")
    choice = input(f"\nSelect use case (1-{len(cases)}) or Enter for default '{cases[0]}': ").strip()
    if not choice:
        return cases[0]
    try:
        return cases[int(choice) - 1]
    except (ValueError, IndexError):
        print(f"Invalid choice. Using default '{cases[0]}'.")
        return cases[0]


USE_CASE_DIR = os.path.join(BASE_DIR, select_use_case())


def load_prompt(folder, filename):
    with open(os.path.join(folder, filename), "r", encoding="utf-8") as f:
        return f.read()


PROBLEM_INPUT = load_prompt(USE_CASE_DIR, "problem.txt")
SYSTEM_A = load_prompt(USE_CASE_DIR, "system_A.txt")
USER_A_TEMPLATE = load_prompt(USE_CASE_DIR, "user_A.txt")
SYSTEM_EXTRACTOR = load_prompt(PROMPT_DIR, "system_extractor.txt")
USER_EXTRACTOR_TEMPLATE = load_prompt(PROMPT_DIR, "user_extractor.txt")
SYSTEM_CHECKER = load_prompt(PROMPT_DIR, "system_checker.txt")
USER_CHECKER_TEMPLATE = load_prompt(PROMPT_DIR, "user_checker.txt")
SYSTEM_B = load_prompt(USE_CASE_DIR, "system_B.txt")
USER_B_TEMPLATE = load_prompt(USE_CASE_DIR, "user_B.txt")

client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")


def run_experiment(use_tool=False):
    print(f"\n--- EXPERIMENT START: {'WITH SKEPTIC TOOL' if use_tool else 'WITHOUT TOOL (BASELINE)'} ---")

    # Shared context: each template picks the placeholders it needs
    C = {
        "problem": PROBLEM_INPUT,
        "PROBLEM": PROBLEM_INPUT,
    }

    prompt_A = [
        {"role": "system", "content": SYSTEM_A},
        {"role": "user", "content": USER_A_TEMPLATE.format(**C)}
    ]
    response_A = client.chat.completions.create(model="local-model", messages=prompt_A, temperature=0.2).choices[0].message.content
    print(f"\n[MODEL A - ENGINEER]:\n{response_A}\n")

    C["proposal"] = response_A
    C["response_A"] = response_A
    C["RESPONSE_A"] = response_A

    system_intervention = ""
    if use_tool:
        prompt_parser = [
            {"role": "system", "content": SYSTEM_EXTRACTOR},
            {"role": "user", "content": USER_EXTRACTOR_TEMPLATE.format(**C)}
        ]
        json_output = client.chat.completions.create(model="local-model", messages=prompt_parser, temperature=0.0).choices[0].message.content

        cleaned_json = re.sub(r"```json|```", "", json_output).strip()
        print(f"--- [DEBUG 1: EXTRACTED LOGICAL JSON]: ---\n{cleaned_json}\n---------------------------------------")

        try:
            logical_structure = json.loads(cleaned_json)
            facts_to_verify = logical_structure.get("fact_claims", [])
        except Exception as e:
            facts_to_verify = []
            print(f"Error during fact pre-parsing: {str(e)}")

        C["facts_to_verify"] = facts_to_verify
        C["FACTS_TO_VERIFY"] = facts_to_verify

        prompt_checker = [
            {"role": "system", "content": SYSTEM_CHECKER},
            {"role": "user", "content": USER_CHECKER_TEMPLATE.format(**C)}
        ]
        checker_output = client.chat.completions.create(model="local-model", messages=prompt_checker, temperature=0.0).choices[0].message.content

        cleaned_checker_json = re.sub(r"```json|```", "", checker_output).strip()
        print(f"--- [DEBUG 2: EXTRACTED CHECKER JSON]: ---\n{cleaned_checker_json}\n----------------------------------------")

        valid, error_message = analyze_general_fallacy(cleaned_json, cleaned_checker_json)
        if not valid:
            system_intervention = f"\n[SYSTEM WARNING FOR THE CTO]: The logical validator blocked the proposal. Reason: {error_message}\n"
            print(f"\033[91m{system_intervention}\033[0m")

    C["system_intervention"] = system_intervention
    C["SYSTEM_INTERVENTION"] = system_intervention

    prompt_B_content = USER_B_TEMPLATE.format(**C)

    prompt_B = [
        {"role": "system", "content": SYSTEM_B},
        {"role": "user", "content": prompt_B_content}
    ]
    response_B = client.chat.completions.create(model="local-model", messages=prompt_B, temperature=0.2).choices[0].message.content
    print(f"\n[MODEL B - CTO]:\n{response_B}\n")


import os
import sys
from contextlib import redirect_stdout
from io import StringIO

if __name__ == "__main__":
    # 1. Chiedi all'utente come nominare il file di output
    filename = input("Enter report filename (e.g., geopolitics_run1): ").strip()
    if not filename:
        filename = "experiment_run"
    if not filename.endswith(".txt"):
        filename += ".txt"

    # 2. Assicurati che la cartella 'results' esista
    os.makedirs("results", exist_ok=True)
    file_path = os.path.join("results", filename)

    print(f"\nRunning experiments... Capturing output into: {file_path}")

    # 3. Buffer per catturare tutti i print del terminale
    output_buffer = StringIO()
    
    with redirect_stdout(output_buffer):
        print("="*60)
        print("--- EXPERIMENT START: WITHOUT TOOL (BASELINE) ---")
        print("="*60)
        # Esegue la prima run (modifica il nome della funzione se differisce nel tuo script)
        run_experiment(use_tool=False) 
        
        print("\n\n" + "#"*80 + "\n\n")
        
        print("="*60)
        print("--- EXPERIMENT START: WITH SKEPTIC TOOL ---")
        print("="*60)
        # Esegue la seconda run
        run_experiment(use_tool=True)

    # 4. Scrittura finale sul file txt nella cartella results
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(output_buffer.getvalue())

    print(f"✅ Done! All outputs successfully saved to '{file_path}'")
