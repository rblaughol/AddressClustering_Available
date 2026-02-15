import json
import os

# ========== File Paths ==========
ENTITY_FILE = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/LABEL/Entity-LLM/final_entities_reviewed.txt"
JSON_FILE = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/LABEL/dataset/combinedAllLabels.json"
OUTPUT_FILE = "./label_entity.txt"

# ========== Load JSON Data ==========
print("[INFO] Loading JSON dataset...")

with open(JSON_FILE, "r", encoding="utf-8") as f:
    addr_data = json.load(f)

print(f"[INFO] Loaded {len(addr_data)} address entries from JSON.")

# ========== Build name -> address lookup table ==========
print("[INFO] Building name-to-address index...")

name_to_address = {}
for addr, info in addr_data.items():
    name = info.get("name", "").strip()
    if name:  # only index non-empty names
        if name not in name_to_address:
            name_to_address[name] = []
        name_to_address[name].append(addr)

print(f"[INFO] Indexed {len(name_to_address)} unique names.")

# ========== Read entity file and match addresses ==========
print("[INFO] Processing entity file and matching addresses...")

results = []  # store final output

with open(ENTITY_FILE, "r", encoding="utf-8") as f:
    for line_idx, line in enumerate(f):
        line = line.strip()
        if not line:
            continue

        # Each line may contain multiple names separated by commas
        names = [n.strip() for n in line.split(",")]

        matched_addresses = set()

        for name in names:
            if name in name_to_address:
                matched_addresses.update(name_to_address[name])

        # If any address matched, record result
        if matched_addresses:
            results.append({
                "entity_names": names,
                "addresses": sorted(matched_addresses)
            })

print(f"[INFO] Matching completed. Found {len(results)} matched entity groups.")

# ========== Write output file ==========
print(f"[INFO] Writing results to {OUTPUT_FILE} ...")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for item in results:
        names_str = ", ".join(item["entity_names"])
        addrs_str = ", ".join(item["addresses"])
        f.write(f"{addrs_str}\n")

print(f"[SUCCESS] Done! Results saved to: {OUTPUT_FILE}")
