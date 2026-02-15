import pandas as pd
import random
import requests
import json
import os
import glob
import time
from datetime import datetime
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

# ================= Configuration =================
API_URL = "https://tianshu.tones-ai.com/v1/chat/completions"
CONFIG_FILE = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/env.conf"
MODEL_NAME = "gpt-5-mini"

# Path Settings
DATA_DIR = './exp_data'
# Modify to the initial cluster path for Label
INITIAL_CLUSTERS_DIR = '/public/home/blockchain/yanruibin/deanonymization/label_16_clusters'
OUTPUT_DIR = './eval_chain_results_label'  # Distinguish output directory
HISTORY_DIR = './llm_chain_history_label'

# === [Specify the Label result file to evaluate here] ===
TARGET_FILENAME = 'Proposed_Label_exp.csv'

NUM_SAMPLES = 500
MAX_WORKERS = 16


# ===========================================

def load_api_key_from_conf(conf_path):
    if not os.path.exists(conf_path):
        return os.getenv("CHAINNODE_API_KEY", "")
    api_key = ""
    try:
        with open(conf_path, "r", encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if line.startswith("llm_API"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        api_key = parts[1].strip().strip('"').strip("'")
                        break
    except Exception:
        pass
    return api_key


API_KEY = load_api_key_from_conf(CONFIG_FILE)


def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_print(msg):
    print(f"[{get_timestamp()}] {msg}", flush=True)


# ================= Data Loading =================

def load_initial_clusters(directory):
    log_print(f"Loading initial clusters from: {directory} ...")
    item_to_cid = {}
    cid_to_items = {}

    count_files = 0
    # Assume cluster_0.csv to cluster_15.csv exist (inferred from path name label_16_clusters)
    # Here iterate through all csvs for robustness
    files = glob.glob(os.path.join(directory, "cluster_*.csv"))

    if not files:
        # Attempt without extension
        files = glob.glob(os.path.join(directory, "cluster_*"))

    for fname in files:
        try:
            members = []
            with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    members.append(line)

            if not members: continue

            # Use filename as Cluster ID
            base_name = os.path.basename(fname)
            global_cid = f"init_{base_name}"

            cid_to_items[global_cid] = members
            for m in members:
                item_to_cid[m] = global_cid
            count_files += 1

        except Exception as e:
            log_print(f"Failed to read {fname}: {e}")

    log_print(f"Loaded {count_files} files, covering {len(item_to_cid)} items.")
    return item_to_cid, cid_to_items


def generate_hard_triplets(df, item_to_cid, cid_to_items, num_samples):
    log_print("Generating Hard Negative samples...")

    final_clusters = []
    for idx, row in df.iterrows():
        # Label might contain commas, but previous processing script joined with ", "
        # Here simply split, might break if Label itself has ", " but usually Label is short
        members_str = str(row['Members'])
        members = [m.strip() for m in members_str.split(',')]
        # Filter out empty strings
        members = [m for m in members if m]

        if len(members) >= 2:
            final_clusters.append(members)

    tasks = []
    attempts = 0
    max_attempts = num_samples * 200

    if not final_clusters:
        log_print("Error: No valid clusters found in target file.")
        return []

    cluster_indices = list(range(len(final_clusters)))

    while len(tasks) < num_samples and attempts < max_attempts:
        attempts += 1
        final_cid = random.choice(cluster_indices)
        members = final_clusters[final_cid]

        if len(members) < 2: continue
        anchor, positive = random.sample(members, 2)

        init_cid = item_to_cid.get(anchor)
        if not init_cid: continue

        potential_negatives = cid_to_items.get(init_cid, [])
        if not potential_negatives: continue

        negative = None
        for _ in range(10):
            cand = random.choice(potential_negatives)
            if cand not in members:
                negative = cand
                break

        if not negative: continue

        items = [anchor, positive, negative]
        display_items = items.copy()
        random.shuffle(display_items)

        correct_remove_idx = -1
        for i, item in enumerate(display_items):
            if item == negative:
                correct_remove_idx = i + 1

        tasks.append({
            'options': display_items,
            'negative_item': negative,
            'positive_pair': [anchor, positive],
            'ground_truth_remove_idx': correct_remove_idx
        })

    log_print(f"Generated {len(tasks)} Hard Negative samples (Attempts: {attempts}).")
    return tasks


# ================= LLM Helpers =================

def call_llm_base(messages, temperature=0.0):
    if not API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature
    }

    try:
        for _ in range(3):
            try:
                response = requests.post(API_URL, headers=headers, json=data, timeout=30)
                if response.status_code == 429:
                    time.sleep(2)
                    continue
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                return content
            except requests.exceptions.RequestException:
                time.sleep(1)
        return None
    except Exception:
        return None


def extract_choice_index(content):
    if not content: return None
    match = re.search(r'\b([1-3])\b', content)
    if match: return int(match.group(1))
    if '1' in content: return 1
    if '2' in content: return 2
    if '3' in content: return 3
    return None


def extract_yes_no(content):
    if not content: return None
    content_lower = content.lower()
    if re.search(r'\byes\b', content_lower): return True
    if re.search(r'\bno\b', content_lower): return False
    if 'belong to the same' in content_lower and 'do not' not in content_lower: return True
    if 'different' in content_lower: return False
    return None


# ================= Core Evaluation Logic =================

def run_evaluation_chain(task, sample_id):
    """
    Executes evaluation for LABELS.
    """

    minimal_log = {
        "sample_id": sample_id,
        "input": {
            "options": task['options'],
            "negative_item": task['negative_item'],
            "ground_truth_remove_idx": task['ground_truth_remove_idx']
        },
        "steps": []
    }

    opts = task['options']

    # === Rewritten System Prompt, targeting Label clustering ===
    system_prompt = """
You are an expert in Ethereum blockchain analysis, address labeling, and entity resolution (Deanonymization).
Your task is to identify whether a group of address labels belongs to the **SAME real-world entity, service, or protocol**.

**Criteria for 'Same Entity' (YES):**
1. **Enumerated Accounts**: Wallets belonging to the same exchange or service (e.g., 'Binance 1', 'Binance 14', 'Binance Hot Wallet').
2. **Protocol Components**: Different smart contracts part of the same DApp/Protocol (e.g., 'Maker: MCD Pot', 'Maker: Vat', 'Maker: Deployer').
3. **Name Variations**: Abbreviations or slight formatting differences for the same entity (e.g., 'Curve.fi', 'Curve Finance', 'CRV').
4. **Token & Infrastructure**: The main token contract and its auxiliary contracts (e.g., 'Aave Token', 'Aave: Lending Pool').

**Criteria for 'Different Entity' (NO):**
1. **Different Projects**: e.g., 'Uniswap' vs 'SushiSwap' (even if they perform similar functions).
2. **Distinct Users**: e.g., 'Vitalik' vs 'Satoshi' (unless proof of same ownership exists).

Focus on whether these labels represent the **same controlling authority or software system**.
"""

    # --- Step 1: Are they all the same? ---
    prompt_q1 = f"""
{system_prompt}

I have three blockchain address labels:
1. {opts[0]}
2. {opts[1]}
3. {opts[2]}

Based on the criteria above, do these three labels belong to the SAME entity?
Answer ONLY with "Yes" or "No".
"""
    ans_q1 = call_llm_base([{"role": "user", "content": prompt_q1}])
    is_all_same = extract_yes_no(ans_q1) if ans_q1 else None

    # Log Step 1
    minimal_log["steps"].append({
        "step": 1,
        "prompt": prompt_q1,
        "response_text": ans_q1,
        "parsed_choice": is_all_same
    })

    result_data = {
        "sample_id": sample_id,
        "q1_all_same": is_all_same,
        "q2_correct_removal": None,
        "q3_remaining_same": None,
        "final_status": "PENDING",
        "is_perfect_chain": False
    }

    if is_all_same:
        log_print(f"Sample {sample_id} -> Ended at Q1 (All same).")
        result_data["final_status"] = "Q1_YES_STOP"
        result_data["q1_all_same"] = True
        return result_data, minimal_log

    # --- Step 2: Remove Outlier ---
    prompt_q2 = f"""
{system_prompt}

Among the following three labels, ONE is the outlier (least likely to belong to the same entity/protocol as the other two).
Which one should be removed?

1. {opts[0]}
2. {opts[1]}
3. {opts[2]}

Respond with ONLY the number (1, 2, or 3) of the item to remove.
"""
    ans_q2 = call_llm_base([{"role": "user", "content": prompt_q2}])
    remove_idx = extract_choice_index(ans_q2) if ans_q2 else None

    ground_truth_idx = task['ground_truth_remove_idx']
    q2_is_correct = (remove_idx == ground_truth_idx)

    # Log Step 2
    minimal_log["steps"].append({
        "step": 2,
        "prompt": prompt_q2,
        "response_text": ans_q2,
        "parsed_choice": remove_idx,
        "ground_truth": ground_truth_idx,
        "is_correct": q2_is_correct
    })

    result_data["q1_all_same"] = False

    if remove_idx is None:
        result_data["q2_correct_removal"] = False
        result_data["final_status"] = "Q2_PARSE_ERROR"
        return result_data, minimal_log

    result_data["q2_correct_removal"] = q2_is_correct

    # --- Step 3: Remaining Same? ---
    remaining_opts = [opt for i, opt in enumerate(opts) if (i + 1) != remove_idx]
    if len(remaining_opts) != 2: remaining_opts = opts[:2]

    prompt_q3 = f"""
{system_prompt}

I have two blockchain address labels:
1. {remaining_opts[0]}
2. {remaining_opts[1]}

Based on the criteria above, do these two labels belong to the SAME entity?
Answer ONLY with "Yes" or "No".
"""
    ans_q3 = call_llm_base([{"role": "user", "content": prompt_q3}])
    remaining_are_same = extract_yes_no(ans_q3) if ans_q3 else None

    # Log Step 3
    minimal_log["steps"].append({
        "step": 3,
        "prompt": prompt_q3,
        "response_text": ans_q3,
        "parsed_choice": remaining_are_same
    })

    # Check Perfect Chain
    is_perfect = (q2_is_correct and remaining_are_same)
    result_data["q3_remaining_same"] = remaining_are_same
    result_data["final_status"] = "COMPLETED"
    result_data["is_perfect_chain"] = is_perfect

    return result_data, minimal_log


def main():
    if not API_KEY:
        log_print("Error: API Key not found.")
        return

    init_item_map, init_cluster_map = load_initial_clusters(INITIAL_CLUSTERS_DIR)
    if not init_item_map:
        log_print("Failed to load initial clusters.")
        return

    target_path = os.path.join(DATA_DIR, TARGET_FILENAME)
    if not os.path.exists(target_path):
        log_print(f"Error: Target file not found: {target_path}")
        return

    filename_base = TARGET_FILENAME
    log_print(f"Starting evaluation for: {filename_base}")

    df = pd.read_csv(target_path)
    tasks = generate_hard_triplets(df, init_item_map, init_cluster_map, NUM_SAMPLES)

    if not tasks:
        log_print("Failed to generate valid samples.")
        return

    results_summary = []
    full_history_log = []

    if not os.path.exists(HISTORY_DIR): os.makedirs(HISTORY_DIR)
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    print(f"\n--- Starting Label Evaluation ({MAX_WORKERS} Workers) ---")

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_evaluation_chain, task, i): i for i, task in enumerate(tasks)}

        completed_count = 0
        for future in as_completed(futures):
            try:
                result, history = future.result()
                result['file'] = filename_base
                results_summary.append(result)
                full_history_log.append(history)

                completed_count += 1
                if completed_count % 5 == 0:
                    log_print(f"Progress: {completed_count}/{len(tasks)} samples completed.")

            except Exception as e:
                log_print(f"A task failed with error: {e}")

    results_summary.sort(key=lambda x: x['sample_id'])
    full_history_log.sort(key=lambda x: x['sample_id'])

    # 1. Save Summary CSV
    output_csv = os.path.join(OUTPUT_DIR, f"chain_eval_{filename_base}")
    pd.DataFrame(results_summary).to_csv(output_csv, index=False, encoding='utf-8-sig')

    # 2. Save Consolidated JSON Log
    output_json = os.path.join(HISTORY_DIR, f"full_log_{filename_base.replace('.csv', '.json')}")

    final_json_data = {
        "file": filename_base,
        "type": "Label Evaluation",
        "total_samples": len(full_history_log),
        "logs": full_history_log
    }

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_json_data, f, indent=2, ensure_ascii=False)

    # --- Statistics ---
    completed_chains = [r for r in results_summary if r['final_status'] == 'COMPLETED']
    perfect_chains = [r for r in results_summary if r['is_perfect_chain'] == True]

    q2_acc = len([r for r in completed_chains if r['q2_correct_removal']]) / len(
        completed_chains) if completed_chains else 0
    q3_consist = len([r for r in completed_chains if r['q3_remaining_same']]) / len(
        completed_chains) if completed_chains else 0
    overall_acc = len(perfect_chains) / len(results_summary) if results_summary else 0

    log_print("\n" + "=" * 30)
    log_print("       LABEL EVAL REPORT       ")
    log_print("=" * 30)
    log_print(f"Target File      : {filename_base}")
    log_print("-" * 30)
    log_print(f"Q2 Accuracy      : {q2_acc:.2%} (Removal Correctness)")
    log_print(f"Q3 Consistency   : {q3_consist:.2%} (Remaining Coherence)")
    log_print("-" * 30)
    log_print(f"OVERALL ACCURACY : {overall_acc:.2%} ({len(perfect_chains)}/{len(results_summary)})")
    log_print("=" * 30)
    log_print(f"Logs saved to    : {output_json}")


if __name__ == "__main__":
    main()