#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from tqdm import tqdm


JSON_PATH = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/analysis/eth_sum_OtherSourcesAdded_enriched.json"
CSV_PATH  = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/analysis/entity_cleaned.csv"


EXPAND_OUT = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/expanded_addresses.txt"


def norm_addr(x: str) -> str:
    """Normalize address/hash: strip + lowercase."""
    return (x or "").strip().lower()


def load_json_hashes(json_path: str) -> set:
    """Load JSON and extract address hashes (lowercased)."""
    print(f"[1/3] Loading JSON: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hashes = set()

    for k, v in data.items():
        nk = norm_addr(k)
        if nk:
            hashes.add(nk)
        if isinstance(v, dict):
            av = norm_addr(v.get("address", ""))
            if av:
                hashes.add(av)

    print(f"  - JSON unique hashes: {len(hashes):,}")
    return hashes


def iter_entity_rows(csv_path: str):
    """
    Iterate entity_cc.csv line by line.
    Each line: hash1,hash2,hash3,...
    Return (row_idx, row_hashes_list, row_hashes_set)
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            parts = [norm_addr(x) for x in line.split(",")]
            parts = [p for p in parts if p]  # drop empty
            if not parts:
                continue
            yield idx, parts, set(parts)


def main():
    # ---------- Load JSON hashes ----------
    json_hashes = load_json_hashes(JSON_PATH)
    if not json_hashes:
        print("[WARN] JSON hashes is empty. Exit.")
        return

    # ---------- First pass: build inverted index address -> row_id(s) ----------
    print(f"[2/3] Building address -> rows index from: {CSV_PATH}")
    addr2rows = {}
    rows = []  # store list of row hashes for later expansion
    row_count = 0
    addr_count = 0

    for row_idx, parts, partset in tqdm(iter_entity_rows(CSV_PATH), desc="Indexing rows"):
        rows.append(parts)  # keep original list (normalized)
        row_count += 1
        addr_count += len(parts)
        for a in partset:
            addr2rows.setdefault(a, []).append(row_idx)

    print(f"  - Indexed rows: {row_count:,}")
    print(f"  - Total addresses (with duplicates across rows): {addr_count:,}")
    print(f"  - Unique addresses in index: {len(addr2rows):,}")

    # ---------- Match JSON hashes to rows ----------
    print("[3/3] Matching JSON hashes to entity_cc rows ...")

    matched_json_hashes = set()      # JSON hashes that matched at least one row (dedup)
    matched_rows = set()             # rows hit by any json hash (dedup)
    expansions = set()               # extra hashes from matched rows excluding json hashes

    hit_pairs = 0

    for h in tqdm(sorted(json_hashes), desc="Matching hashes"):
        if h not in addr2rows:
            continue

        matched_json_hashes.add(h)
        row_ids = addr2rows[h]
        hit_pairs += len(row_ids)

        # Print out how many addresses are related to the current JSON address
        print(f"[HIT] hash={h} found in rows with {len(row_ids)} addresses")

        for rid in row_ids:
            matched_rows.add(rid)
            row_list = rows[rid]
            row_size = len(row_list)
            others_count = row_size - 1

            # Print the number of addresses in the current row
            print(f"    row_id={rid}  row_size={row_size}  others={others_count}")

    # ---------- Compute expansions ----------
    for rid in matched_rows:
        for a in rows[rid]:
            if a not in json_hashes:
                expansions.add(a)

    print(f"\n[WRITE] Writing expanded addresses to: {EXPAND_OUT}")
    with open(EXPAND_OUT, "w", encoding="utf-8") as f:
        # Write unique addresses to ensure deduplication
        for addr in sorted(set(expansions)):
            f.write(addr + "\n")

    print(f"  - Written {len(expansions):,} addresses to file.")

    # ---------- Final stats ----------
    print("\n========== SUMMARY ==========")
    print(f"JSON unique hashes:           {len(json_hashes):,}")
    print(f"Matched JSON hashes:          {len(matched_json_hashes):,}")
    print(f"Matched rows:                 {len(matched_rows):,}")
    print(f"Hash-row hit pairs (raw):     {hit_pairs:,}")
    print(f"Expanded extra hashes (uniq): {len(expansions):,}")
    print(f"Saved to:                     {EXPAND_OUT}")

    if len(matched_json_hashes) > 0:
        ratio = len(expansions) / len(matched_json_hashes)
        print(f"Expansion / matched_hashes:   {ratio:.3f}")
    print("================================\n")


if __name__ == "__main__":
    if not os.path.exists(JSON_PATH):
        raise FileNotFoundError(f"JSON not found: {JSON_PATH}")
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    main()
