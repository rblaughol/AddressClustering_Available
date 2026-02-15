#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

CSV_PATH = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/analysis/entity_cleaned.csv"

def norm_addr(x: str) -> str:
    """Normalize address/hash: strip + lowercase."""
    return (x or "").strip().lower()

def main():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    unique_hashes = set()
    total_seen = 0  

    print(f"Reading: {CSV_PATH}")

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue  

            parts = [norm_addr(x) for x in line.split(",")]
            parts = [p for p in parts if p]  

            total_seen += len(parts)
            unique_hashes.update(parts)

    print("\n========== SUMMARY ==========")
    print(f"Total hashes seen (with duplicates): {total_seen:,}")
    print(f"Unique hashes (deduplicated):        {len(unique_hashes):,}")
    print("================================\n")

if __name__ == "__main__":
    main()
