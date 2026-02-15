import os
import time
from typing import List, Dict, Set, Optional

import pandas as pd
import tiktoken
from openai import OpenAI

from multiprocessing import Pool


############################################
# Global Config
############################################

ENV_PATH = "../../env.conf"
DATA_PATH = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/ENS/dataset/preprocessed_ens.csv"
PROMPT_PATH = "./entity_recognition_prompt.txt"

MODEL_NAME = "gpt-5-mini"
API_URL = "https://tianshu.tones-ai.com/v1"

MODEL_CONTEXT_LIMITS = {
    "gpt-5-mini": 272000
}

RESERVE_RATIO = 0.85
MAX_ROWS = 10000
TOKEN_TO_WORD_RATIO = 0.25
TOKEN_TOLERANCE_RATIO = 0.01  # 1%

# Batch tuning controls (kept for compatibility; no longer used in partition)
ADD_BATCH_START = 512
ADD_BATCH_MIN = 1
TRIM_BATCH_START = 256
TRIM_BATCH_MIN = 1
MAX_TUNE_ITERS = 200

# NEW: fixed group size (no token counting)
CHUNK_SIZE = 2000

# Review output
REVIEW_ENABLE = True
OUTPUT_PATH = "./final_entities_reviewed.txt"

# LLM robustness
LLM_MAX_RETRIES = 6
LLM_BACKOFF_BASE = 2  # exponential backoff base seconds


############################################
# Utility
############################################

def load_api_key(env_path: str) -> str:
    with open(env_path) as f:
        for line in f:
            if line.startswith("llm_API"):
                return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("llm_API not found in env.conf")

def get_tokenizer(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, tokenizer) -> int:
    if not text:
        return 0
    return len(tokenizer.encode(text))

def usable_half_budget() -> int:
    max_ctx = MODEL_CONTEXT_LIMITS[MODEL_NAME]
    return int(max_ctx * (1 - RESERVE_RATIO)) // 2

def estimate_word_budget(token_budget: int) -> int:
    return int(token_budget * TOKEN_TO_WORD_RATIO)

def prefix_by_word_budget(lines: List[str], max_words: int) -> int:
    used = 0
    n = 0
    for line in lines:
        w = len(line.split())
        if used + w > max_words:
            break
        used += w
        n += 1
    return max(1, n) if lines else 0

def _sleep_backoff(attempt: int):
    time.sleep((LLM_BACKOFF_BASE ** attempt))

def call_llm(api_key: str, messages: List[dict], allow_empty: bool = True) -> str:
    """
    Robust LLM call:
    - Retries on exceptions
    - Retries on None or literal 'None'
    - allow_empty=True means empty content is accepted (represents "no change")
    """
    client = OpenAI(api_key=api_key, base_url=API_URL)

    last_err = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            print(f"[LLM] attempt {attempt}")
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
            )
            content = None
            try:
                content = resp.choices[0].message.content
            except Exception:
                content = None

            if content is None:
                raise ValueError("LLM returned None content")
            if isinstance(content, str) and content.strip().lower() == "none":
                raise ValueError("LLM returned 'None' string")

            if not allow_empty:
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("LLM returned empty content but allow_empty=False")

            return content if isinstance(content, str) else str(content)

        except Exception as e:
            last_err = e
            print(f"[LLM] error: {e}")
            if attempt < LLM_MAX_RETRIES:
                _sleep_backoff(attempt)
                continue
            break

    raise RuntimeError(f"LLM failed after retries. Last error: {last_err}")

def _split_ens(line: str) -> List[str]:
    return [x.strip() for x in (line or "").split(",") if x.strip()]

def normalize_entity_line(line: str) -> str:
    parts = _split_ens(line)
    seen = set()
    out = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ",".join(out)

def parse_clusters(text: Optional[str]) -> List[List[str]]:
    """
    Robust parser: accept None/"" safely.
    Each non-empty line => one cluster, split by comma.
    """
    if not text:
        return []
    s = text.strip()
    if not s:
        return []
    clusters = []
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        items = [x.strip() for x in line.split(",") if x.strip()]
        if items:
            clusters.append(items)
    return clusters


############################################
# Prompt (UPDATED: base prompt + diff-only requirement)
############################################

def load_or_create_prompt(prompt_path: str) -> str:
    """
    System prompt for clustering:
    Decide whether multiple ENS names are POSSIBLY / LIKELY controlled/owned by the SAME on-chain entity.

    UPDATED per request:
    - Keep original content
    - Add diff-only instruction:
      Output ONLY entity lines that are DIFFERENT from the input grouping; if nothing changes, output NOTHING.
    """
    if not os.path.exists(prompt_path):
        prompt = (
            "You are an expert in blockchain identity analysis.\n"
            "Your task is to cluster label names into plausible entities based ONLY on string similarity.\n\n"
            "Definition:\n"
            "- SAME entity means it is plausible/likely the same on-chain owner/controller controls those labels\n"
            "  (e.g., naming conventions, consistent prefixes/suffixes, brand/persona patterns, systematic numbering, wallet/project naming).\n"
            "- You only see label names as strings (no on-chain data). Use reasonable inference.\n\n"
            "Policy:\n"
            "- Merge when there are clear or moderate name-based signals suggesting common ownership.\n"
            "IMPORTANT:\n"
            "- Output ONLY the entity lines that are DIFFERENT from the input grouping.\n"
            "- If nothing changes, output NOTHING.\n\n"
            "STRICT output format requirements:\n"
            "- Each line represents ONE entity\n"
            "- Label names of the SAME entity are separated by commas\n"
            "- DIFFERENT entities are separated by newline\n"
            "- Output ONLY the entities\n\n\n"
        "****MOST IMPORTANT CASE:****\n"
        "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
        "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
        "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
        "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics."
        )
        with open(prompt_path, "w") as f:
            f.write(prompt)
        return prompt

    with open(prompt_path, "r") as f:
        return f.read()

def forward_diff_prompt() -> str:
    """
    Forward stage (diff-only):
    Treat A+B as one set, allow merges/re-grouping when likely/possible same entity.
    If no changes, output NOTHING (empty).
    """
    return (
        "You are an expert in blockchain identity analysis.\n"
        "You will be given two label ENTITY LINE lists (A and B). Treat them as ONE combined set.\n"
        "Each entity line is a candidate cluster (comma-separated label names).\n\n"
        "PRIMARY GOAL:\n"
        "- Produce plausible entities: if names look similar by any reasonable string signal, group them.\n"
        "Rules:\n"
        "- Merge when there are clear or moderate name-based signals of common ownership.\n\n"
        "CRITICAL (diff-only output):\n"
        "- If an entity/grouping is unchanged, DO NOT output it.\n"
        "- If there are no changes needed, output NOTHING (empty output).\n\n"
        "STRICT output format:\n"
        "- Each output line is ONE entity\n"
        "- Label names separated by commas\n"
        "- Output ONLY the lines, no explanations\n\n\n"

        "****MOST IMPORTANT CASE:****\n"
        "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
        "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
        "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
        "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics."
    )

def review_diff_prompt() -> str:
    """
    Review stage (diff-only):
    Allow split/merge/re-group, but only output lines that should change.
    """
    return (
        "You are a reviewer for label entity clustering based on name strings.\n"
        "You will be given current ENTITY LINES (each line is an entity; comma-separated label names).\n"
        "Your job is to correct mistakes based on whether names are LIKELY or POSSIBLY controlled/owned by the SAME entity.\n\n"
        "Policy:\n"
        "- If a merge looks plausible/likely from names, it can stay merged.\n"
        "- Split only when the merge is wrong.\n"
        "- Merge only when there are clear/moderate signals they belong together.\n\n"
        "CRITICAL (diff-only output):\n"
        "- Output ONLY the entity lines that should CHANGE compared to the input.\n"
        "- If a line is correct as-is, DO NOT output it.\n"
        "- If you split a line like 'ABC,DEF', output:\n"
        "  ABC\n"
        "  DEF\n"
        "- If nothing needs changing, output NOTHING.\n\n"
        "STRICT output format:\n"
        "- Each output line is ONE entity\n"
        "- Label names separated by commas\n"
        "- Output ONLY the lines, no explanations\n"
        "****MOST IMPORTANT CASE:****\n"
        "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
        "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
        "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
        "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics.\n"
    )


############################################
# Partition (UPDATED: fixed-size chunks only)
############################################

def partition_by_fixed_chunk_size(lines: List[str], chunk_size: int) -> List[List[str]]:
    """
    Partition input lines into fixed-size chunks (each chunk has up to chunk_size lines).
    No token counting.
    """
    if not lines:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    bulks: List[List[str]] = []
    n = len(lines)
    bulk_idx = 0
    for i in range(0, n, chunk_size):
        b = lines[i:i + chunk_size]
        bulks.append(b)
        print(f"[PARTITION] bulk {bulk_idx}: lines={len(b)} (fixed chunk_size={chunk_size})")
        bulk_idx += 1
    print()
    return bulks


############################################
# Forward clustering
############################################

def forward_cluster_one_bulk(ens_lines: List[str], api_key: str, system_prompt: str) -> List[str]:
    user_prompt = (
        "Below is a label list. Treat them as ONE combined set.\n"
        "Cluster by whether they are LIKELY or POSSIBLY controlled/owned by the SAME on-chain entity.\n"
        "IMPORTANT:\n"
        "- Output ONLY the entity lines that are DIFFERENT from the input grouping.\n"
        "- If nothing changes, output NOTHING.\n\n"
        "STRICT output format:\n"
        "- Each line is ONE entity\n"
        "- Label names separated by commas\n"
        "- Output ONLY the entities\n\n"
        "****MOST IMPORTANT CASE:****\n"
        "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
        "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
        "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
        "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics.\n\n\n"
        "LABEL list:\n" + "\n".join(label_lines)
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    print("[FORWARD] Calling LLM for single bulk clustering...")
    response = call_llm(api_key, messages, allow_empty=True)
    print("\n[FORWARD] LLM OUTPUT (single bulk):\n")
    print(response)
    print("-" * 60)

    clusters = parse_clusters(response)

    # Empty => no grouping => singletons
    if not clusters:
        out = [normalize_entity_line(x) for x in ens_lines if x and str(x).strip()]
        out = [x for x in out if x]
        return out

    out = [normalize_entity_line(",".join(c)) for c in clusters if c]
    out = [x for x in out if x]
    return out

def forward_bulk_merge(ens_list: List[str], api_key: str, system_prompt: str, tokenizer) -> List[str]:
    # 1) Fixed-size partition: each bulk has up to 2000 names (lines)
    raw_bulks = partition_by_fixed_chunk_size(ens_list, CHUNK_SIZE)
    if not raw_bulks:
        return []

    # NOTE: keep existing behavior: do NOT pre-cluster each bulk; bulks are raw ENS lines
    bulks: List[List[str]] = raw_bulks


    archived_bases: List[List[str]] = []

    round_idx = 0
    while len(bulks) > 1:
        base = bulks[0]
        print(f"\n===== [Round {round_idx}] START =====")
        print(f"[Round {round_idx}] base size = {len(base)} | remaining bulks = {len(bulks)}")

        for j in range(1, len(bulks)):
            other = bulks[j]
            print(f"[Round {round_idx}] Comparing base with bulk {j} (diff-only)...")

            user_prompt = (
                "Below are two label ENTITY LINE lists. Treat them as ONE combined clustering.\n"
                "Cluster by whether they are LIKELY or POSSIBLY controlled/owned by the SAME on-chain entity.\n"
                "IMPORTANT (diff-only):\n"
                "- Output ONLY the entity lines that are DIFFERENT from the input grouping.\n"
                "- If nothing changes, output NOTHING.\n\n\n"
                "STRICT output format:\n"
                "- Each line is ONE entity\n"
                "- Label names separated by commas\n"
                "- Output ONLY the entities\n\n"
                "****MOST IMPORTANT CASE:****\n"
                "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
                "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
                "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
                "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics.\n\n\n"
                "ENTITY LINES A:\n" + "\n".join(base) + "\n\nENTITY LINES B:\n" + "\n".join(other)
            )

            messages = [
                {"role": "system", "content": forward_diff_prompt()},
                {"role": "user", "content": user_prompt}
            ]

            response = call_llm(api_key, messages, allow_empty=True)
            clusters = parse_clusters(response)
            print(clusters)
            if not clusters:
                continue

            base_map = {}
            for ent in base:
                for e in ent.split(","):
                    base_map[e.strip()] = ent

            other_map = {}
            for ent in other:
                for e in ent.split(","):
                    other_map[e.strip()] = ent

            for cluster in clusters:
                involved_base_lines = set()
                involved_other_lines = set()

                for e in cluster:
                    if e in base_map:
                        involved_base_lines.add(base_map[e])
                    if e in other_map:
                        involved_other_lines.add(other_map[e])


                if not involved_base_lines or not involved_other_lines:
                    continue

                merged_items = set()
                for line in involved_base_lines:
                    merged_items.update(x.strip() for x in line.split(",") if x.strip())
                for line in involved_other_lines:
                    merged_items.update(x.strip() for x in line.split(",") if x.strip())


                for line in involved_other_lines:
                    if line in other:
                        other.remove(line)


                for line in involved_base_lines:
                    if line in base:
                        base.remove(line)

                other.append(normalize_entity_line(",".join(sorted(merged_items))))


            seen = set()
            cleaned = []
            for line in other:
                nl = normalize_entity_line(line)
                if nl and nl not in seen:
                    seen.add(nl)
                    cleaned.append(nl)
            bulks[j] = cleaned 


        archived_bases.append(base)


        bulks = bulks[1:]
        round_idx += 1


    all_lines: List[str] = []
    for b in archived_bases:
        all_lines.extend(b)
    if bulks:
        all_lines.extend(bulks[0])


    uniq: List[str] = []
    seen = set()
    for line in all_lines:
        nl = normalize_entity_line(line)
        if nl and nl not in seen:
            seen.add(nl)
            uniq.append(nl)


    multi_name_entities: List[str] = []
    for line in uniq:
        names = [x.strip() for x in line.split(",") if x.strip()]
        if len(names) >= 2:
            multi_name_entities.append(line)


    print("\n===== [FINAL] Entities with >= 2 ENS names =====")
    for line in multi_name_entities:
        print(line)

    return multi_name_entities


############################################
# Review: apply "diff-only clusters" as deltas
############################################

def _build_ens_to_line_index(lines: List[str]) -> Dict[str, int]:
    m = {}
    for idx, line in enumerate(lines):
        for e in _split_ens(line):
            m[e] = idx
    return m

def _line_to_set(line: str) -> Set[str]:
    return set(_split_ens(line))

def apply_review_deltas(current_lines: List[str], delta_clusters: List[List[str]]) -> List[str]:
    """
    Apply review deltas as:
      - If a delta cluster spans multiple existing lines => merge those lines into the delta cluster line.
      - If multiple delta clusters all come from one existing line => split it accordingly (leftover -> singleton lines).
    """
    if not delta_clusters:
        return current_lines

    delta_lines = [normalize_entity_line(",".join(c)) for c in delta_clusters if c]
    delta_lines = [d for d in delta_lines if d]
    if not delta_lines:
        return current_lines

    lines = [normalize_entity_line(x) for x in current_lines if x and x.strip()]
    ens_to_idx = _build_ens_to_line_index(lines)

    touched: List[tuple] = []
    for dl in delta_lines:
        s = _line_to_set(dl)
        idxs = set()
        for e in s:
            if e in ens_to_idx:
                idxs.add(ens_to_idx[e])
        touched.append((dl, idxs, s))

    # 1) merges across multiple existing lines
    to_remove = set()
    to_add = []
    for dl, idxs, s in touched:
        if len(idxs) >= 2:
            for idx in idxs:
                to_remove.add(idx)
            to_add.append(dl)

    if to_remove:
        new_lines = []
        for i, line in enumerate(lines):
            if i not in to_remove:
                new_lines.append(line)
        new_lines.extend(to_add)
        lines = [normalize_entity_line(x) for x in new_lines if x and x.strip()]
        ens_to_idx = _build_ens_to_line_index(lines)

    # 2) splits within one existing line
    from_one: Dict[int, List[str]] = {}
    for dl, idxs, s in touched:
        if len(idxs) == 1:
            idx = next(iter(idxs))
            from_one.setdefault(idx, []).append(dl)

    if from_one:
        lines2 = []
        for idx, line in enumerate(lines):
            if idx not in from_one:
                lines2.append(line)
                continue

            original_set = _line_to_set(line)
            proposed = from_one[idx]

            proposed_sets = []
            for p in proposed:
                ps = _line_to_set(p)
                if ps and ps.issubset(original_set):
                    proposed_sets.append(ps)

            if not proposed_sets:
                lines2.append(line)
                continue

            union = set()
            for ps in proposed_sets:
                union |= ps
            leftover = original_set - union

            for ps in proposed_sets:
                lines2.append(normalize_entity_line(",".join(ps)))
            for e in sorted(leftover):
                lines2.append(e)

        lines = [normalize_entity_line(x) for x in lines2 if x and x.strip()]

    # final clean: de-dup lines and ENS (keep first occurrence)
    seen_lines = set()
    out = []
    seen_ens = set()
    for line in lines:
        ens = _split_ens(line)
        filtered = []
        for e in ens:
            if e not in seen_ens:
                filtered.append(e)
                seen_ens.add(e)
        if not filtered:
            continue
        nl = normalize_entity_line(",".join(filtered))
        if nl and nl not in seen_lines:
            seen_lines.add(nl)
            out.append(nl)

    return out

def review_one_bulk_apply_deltas(entity_lines: List[str], api_key: str) -> List[str]:
    sys_prompt = review_diff_prompt()
    user_prompt = (
                "You are given ENTITY LINES.\n"
                "Decide changes based on whether names are LIKELY or POSSIBLY controlled/owned by the SAME entity.\n"
                "IMPORTANT:\n"
                "- Output ONLY the entity lines that are DIFFERENT from the input grouping.\n"
                "- If nothing changes, output NOTHING.\n\n"
                "****MOST IMPORTANT CASE:****\n"
                "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
                "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
                "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
                "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics.\n\n\n"
            )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]
    print("[REVIEW] Calling LLM for one-bulk review (diff-only)...")
    response = call_llm(api_key, messages, allow_empty=True)
    print("\n[REVIEW] LLM OUTPUT (diff-only):\n")
    print(response)
    print("-" * 60)

    deltas = parse_clusters(response)
    return apply_review_deltas(entity_lines, deltas)

def review_bulk_merge_apply_deltas(entity_lines: List[str], api_key: str, tokenizer) -> List[str]:
    sys_prompt = review_diff_prompt()
    bulks = partition_by_fixed_chunk_size(entity_lines, CHUNK_SIZE)

    if len(bulks) == 0:
        return []
    if len(bulks) == 1:
        return review_one_bulk_apply_deltas(bulks[0], api_key)

    print(f"[REVIEW] total bulks = {len(bulks)}")
    all_delta_clusters: List[List[str]] = []

    # 你要的逻辑：0 和 1..n 比一次；1 和 2..n 比一次；...
    for i in range(len(bulks) - 1):
        base = bulks[i]
        print(f"\n===== [Review i={i}] START =====")
        print(f"[Review i={i}] base size = {len(base)}")
        print(f"[Review i={i}] comparing with bulks {i+1}..{len(bulks)-1}")

        for j in range(i + 1, len(bulks)):
            other = bulks[j]

            user_prompt = (
                "You are given ENTITY LINES A and ENTITY LINES B. Treat them as ONE combined clustering.\n"
                "Decide changes based on whether names are LIKELY or POSSIBLY controlled/owned by the SAME entity.\n"
                "IMPORTANT:\n"
                "- Output ONLY the entity lines that are DIFFERENT from the input grouping.\n"
                "- If nothing changes, output NOTHING.\n\n\n"
                "****MOST IMPORTANT CASE:****\n"
                "- 'Maker: Contract 2' and 'Eth2Dai: Old Contract' are likely the SAME entity because they are both MakerDAO contracts.\n"
                "- 'Fantom: Foundation Wallet 13' and 'Fantom: Foundation Wallet 5' should be merged as the same entity because both are Foundation Wallets from the Fantom team.\n"
                "- 'Fee Recipient: 0xBE...667' and 'Fee Recipient: 0x75...F42' should NOT be merged because they are fee recipients without further identifying characteristics.\n"
                "- Similarly, 'Multichain Hack Alert 2258' and 'Multichain Hack Alert 3103' should not be merged as they lack defining characteristics.\n\n\n"
                "STRICT output format:\n"
                "- Each line is ONE entity\n"
                "- Label names separated by commas\n"
                "- Output ONLY the entities\n\n"
                "ENTITY LINES A:\n" + "\n".join(base) + "\n\nENTITY LINES B:\n" + "\n".join(other)
            )


            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]

            print(f"[Review i={i}] Calling LLM (pair {i},{j}) diff-only...")
            response = call_llm(api_key, messages, allow_empty=True)
            print(f"\n[Review i={i}] LLM OUTPUT (pair {i},{j}, diff-only):\n")
            print(response)
            print("-" * 60)

            deltas = parse_clusters(response)
            if deltas:
                # 只存“变化”，不更新base，避免膨胀
                all_delta_clusters.extend(deltas)

        print(f"===== [Review i={i}] COMPLETE =====")

    print("\n[REVIEW] Applying all collected deltas in ONE shot...")
    reviewed = apply_review_deltas(entity_lines, all_delta_clusters)

    # final normalize + de-dup lines
    final = []
    seen = set()
    for line in reviewed:
        nl = normalize_entity_line(line)
        if nl and nl not in seen:
            seen.add(nl)
            final.append(nl)

    print("\n===== REVIEW COMPLETE =====")
    print(f"[REVIEW] total deltas collected: {len(all_delta_clusters)}")
    print(f"[REVIEW] final lines: {len(final)}")
    return final


############################################
# Output
############################################

def write_entities_to_file(entities: List[str], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for line in entities:
            f.write(line.strip() + "\n")
    print(f"[OUTPUT] Wrote {len(entities)} lines to: {out_path}")


############################################
# Main
############################################

def process_file(file_path: str, api_key: str, system_prompt: str, tokenizer: str) -> List[str]:
    """
    This function will handle the processing of each file in a separate process.
    It reads the dataset from the file, processes it and returns the entities.
    """
    print(f"[PROCESS] Processing file: {file_path}")

    # Read the dataset
    df = pd.read_csv(file_path, header=None)
    raw = df.iloc[:, 0].astype(str).tolist()
    print(f"[PROCESS] Loaded rows from {file_path}: {len(raw)}")

    # Preprocess ENS names (remove .eth suffix)
    ens_list = [name[:-4] if name.endswith(".eth") else name for name in raw]
    print(f"[PROCESS] ENS names prepared: {len(ens_list)}")

    # Start forward bulk merge
    entities = forward_bulk_merge(ens_list, api_key, system_prompt, tokenizer)

    return entities

def main():
    print("[MAIN] Loading API key...")
    api_key = load_api_key(ENV_PATH)

    print("[MAIN] Initializing tokenizer...")
    tokenizer = get_tokenizer(MODEL_NAME)

    # Load the system prompt
    print("[MAIN] Loading/creating system prompt...")
    system_prompt = load_or_create_prompt(PROMPT_PATH)

    # Define the directory path and get all files
    directory_path = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/LABEL/experiment/dataset"
    file_paths = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if f.endswith('.csv')]

    # Use multiprocessing to process each file
    print("[MAIN] Starting multiprocessing for file processing...")

    # Create a pool of workers (set to the number of files or a fixed number)
    with Pool(processes=min(len(file_paths), os.cpu_count())) as pool:
        results = pool.starmap(process_file, [(file_path, api_key, system_prompt, tokenizer) for file_path in file_paths])

    # Flatten the results (since each file produces a list of entities)
    all_entities = [entity for result in results for entity in result]

    # Perform the final review on all entities
    if REVIEW_ENABLE:
        print("\n[MAIN] Starting REVIEW stage (diff-only clustering deltas)...")
        all_entities = review_bulk_merge_apply_deltas(all_entities, api_key, tokenizer)

    print("\n========== FINAL RESULT ==========")
    for e in all_entities[:200]:
        print(e)
    if len(all_entities) > 200:
        print(f"... ({len(all_entities)} total lines)")

    print("\n[MAIN] Writing final result to file...")
    write_entities_to_file(all_entities, OUTPUT_PATH)


if __name__ == "__main__":
    main()
