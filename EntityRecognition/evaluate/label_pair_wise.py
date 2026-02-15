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
DATA_DIR = '/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/evaluate/exp_data'
# Initial cluster path for Labels
INITIAL_CLUSTERS_DIR = '/public/home/blockchain/yanruibin/deanonymization/label_16_clusters'
OUTPUT_DIR = './eval_pairwise_results_label'
HISTORY_DIR = './llm_pairwise_history_label'

# === Specify the Label file to evaluate ===
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
    # Attempt to iterate through files under label_16_clusters
    for i in range(20):
        fname = os.path.join(directory, f"cluster_{i}.csv")
        if not os.path.exists(fname):
            fname_no_ext = os.path.join(directory, f"cluster_{i}")
            if os.path.exists(fname_no_ext):
                fname = fname_no_ext
            else:
                continue

        try:
            members = []
            with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    members.append(line)

            if not members: continue

            global_cid = f"init_{i}"
            cid_to_items[global_cid] = members
            for m in members:
                item_to_cid[m] = global_cid
            count_files += 1

        except Exception as e:
            log_print(f"Failed to read {fname}: {e}")

    # If no files found, try glob scanning
    if count_files == 0:
        log_print("No indexed files found, scanning directory...")
        all_files = glob.glob(os.path.join(directory, "*"))
        for fname in all_files:
            if os.path.isdir(fname): continue
            try:
                members = []
                with open(fname, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        members.append(line)
                if members:
                    base = os.path.basename(fname)
                    global_cid = f"init_{base}"
                    cid_to_items[global_cid] = members
                    for m in members:
                        item_to_cid[m] = global_cid
                    count_files += 1
            except:
                pass

    log_print(f"Loaded {count_files} files, covering {len(item_to_cid)} items.")
    return item_to_cid, cid_to_items


def generate_anchor_tasks(df, item_to_cid, cid_to_items, num_samples):
    log_print("Generating Anchor-based samples...")

    final_clusters = []
    for idx, row in df.iterrows():
        # Label might contain commas, here we simply split by comma.
        # If the original Label contains a comma (e.g. "Compound: cUSDC, cDAI"), this split might fragment the Label.
        # But given previous processing logic was uniform, we keep it consistent here.
        members = [m.strip() for m in str(row['Members']).split(',')]
        members = [m for m in members if m]
        if len(members) >= 2:
            final_clusters.append(members)

    tasks = []
    attempts = 0
    max_attempts = num_samples * 200

    if not final_clusters:
        log_print("Error: No valid clusters found in input file.")
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

        candidates = [positive, negative]
        random.shuffle(candidates)

        correct_candidate_idx = candidates.index(positive) + 1

        tasks.append({
            'anchor': anchor,
            'candidates': candidates,
            'positive_item': positive,
            'negative_item': negative,
            'ground_truth_idx': correct_candidate_idx
        })

    log_print(f"Generated {len(tasks)} tasks.")
    return tasks


# ================= LLM Helpers =================

def call_llm_base(messages, temperature=0.0):
    if not API_KEY: return None

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


def extract_choice_1_or_2(content):
    if not content: return None
    match = re.search(r'\b([1-2])\b', content)
    if match: return int(match.group(1))
    if '1' in content: return 1
    if '2' in content: return 2
    return None


def extract_yes_no(content):
    if not content: return None
    content_lower = content.lower()
    if re.search(r'\byes\b', content_lower): return True
    if re.search(r'\bno\b', content_lower): return False
    return None


# ================= Core Logic: Anchor Evaluation =================

def run_anchor_evaluation(task, sample_id):
    minimal_log = {
        "sample_id": sample_id,
        "anchor": task['anchor'],
        "candidates": task['candidates'],
        "positive": task['positive_item'],
        "negative": task['negative_item'],
        "steps": []
    }

    anchor = task['anchor']
    opts = task['candidates']

    # === Rewritten: Label Expert Prompt with Etherscan context ===
    system_prompt = """
You are an expert in Ethereum blockchain analysis, address labeling, and entity resolution (Deanonymization).
These labels are scraped from **Etherscan**, a leading Ethereum block explorer.
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

    # --- Step 1: Selection ---
    prompt_q1 = f"""
{system_prompt}

I have a target Blockchain Label (Anchor): **{anchor}**

Which of the following candidates belongs to the SAME entity as the Anchor?

1. {opts[0]}
2. {opts[1]}

Respond with ONLY the number (1 or 2).
"""
    ans_q1 = call_llm_base([{"role": "user", "content": prompt_q1}])
    selected_idx = extract_choice_1_or_2(ans_q1) if ans_q1 else None

    ground_truth = task['ground_truth_idx']
    q1_is_correct = (selected_idx == ground_truth)

    minimal_log["steps"].append({
        "step": 1,
        "type": "Selection",
        "prompt": prompt_q1,
        "response": ans_q1,
        "selected_idx": selected_idx,
        "ground_truth": ground_truth,
        "is_correct": q1_is_correct
    })

    result_data = {
        "sample_id": sample_id,
        "q1_correct_selection": q1_is_correct,
        "q2_verification_pass": None,
        "final_result": "PENDING",
        "is_success": False
    }

    if selected_idx is None:
        result_data["final_result"] = "Q1_PARSE_ERROR"
        return result_data, minimal_log

    selected_candidate = opts[selected_idx - 1]

    # --- Step 2: Verification ---
    prompt_q2 = f"""
{system_prompt}

I have two Blockchain Labels:
1. {anchor}
2. {selected_candidate}

Based on the criteria above, do these two items belong to the SAME entity?
Answer ONLY with "Yes" or "No".
"""
    ans_q2 = call_llm_base([{"role": "user", "content": prompt_q2}])
    is_verified = extract_yes_no(ans_q2) if ans_q2 else None

    minimal_log["steps"].append({
        "step": 2,
        "type": "Verification",
        "prompt": prompt_q2,
        "subject_pair": [anchor, selected_candidate],
        "response": ans_q2,
        "verified_as_same": is_verified
    })

    result_data["q2_verification_pass"] = is_verified
    result_data["final_result"] = "COMPLETED"

    if q1_is_correct and is_verified:
        result_data["is_success"] = True
    else:
        result_data["is_success"] = False

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

    log_print(f"Starting Anchor-based LABEL evaluation for: {TARGET_FILENAME}")

    df = pd.read_csv(target_path)
    tasks = generate_anchor_tasks(df, init_item_map, init_cluster_map, NUM_SAMPLES)

    if not tasks:
        log_print("Failed to generate tasks.")
        return

    results_summary = []
    full_history_log = []

    if not os.path.exists(HISTORY_DIR): os.makedirs(HISTORY_DIR)
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    print(f"\n--- Running Evaluation ({MAX_WORKERS} Workers) ---")

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_anchor_evaluation, task, i): i for i, task in enumerate(tasks)}

        completed_count = 0
        for future in as_completed(futures):
            try:
                result, history = future.result()
                results_summary.append(result)
                full_history_log.append(history)

                completed_count += 1
                if completed_count % 5 == 0:
                    log_print(f"Progress: {completed_count}/{len(tasks)}")
            except Exception as e:
                log_print(f"Task failed: {e}")

    results_summary.sort(key=lambda x: x['sample_id'])
    full_history_log.sort(key=lambda x: x['sample_id'])

    # 1. CSV
    output_csv = os.path.join(OUTPUT_DIR, f"anchor_eval_{TARGET_FILENAME}")
    pd.DataFrame(results_summary).to_csv(output_csv, index=False, encoding='utf-8-sig')

    # 2. JSON
    output_json = os.path.join(HISTORY_DIR, f"anchor_log_{TARGET_FILENAME.replace('.csv', '.json')}")
    final_json = {
        "file": TARGET_FILENAME,
        "type": "Label Anchor Selection",
        "total": len(full_history_log),
        "logs": full_history_log
    }
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)

    # Stats
    completed = [r for r in results_summary if r['final_result'] == 'COMPLETED']
    correct_selections = [r for r in completed if r['q1_correct_selection']]
    verified_pairs = [r for r in completed if r['q2_verification_pass']]
    success_cases = [r for r in completed if r['is_success']]

    sel_acc = len(correct_selections) / len(completed) if completed else 0
    ver_rate = len(verified_pairs) / len(completed) if completed else 0
    overall = len(success_cases) / len(results_summary) if results_summary else 0

    log_print("\n" + "=" * 30)
    log_print("    LABEL ANCHOR EVAL REPORT")
    log_print("=" * 30)
    log_print(f"Selection Acc (Q1) : {sel_acc:.2%} (Picked Positive)")
    log_print(f"Verification Rate  : {ver_rate:.2%} (Said Yes to Selected)")
    log_print(f"OVERALL SUCCESS    : {overall:.2%} (Picked Pos + Said Yes)")
    log_print("=" * 30)
    log_print(f"Saved: {output_csv}")


if __name__ == "__main__":
    main()