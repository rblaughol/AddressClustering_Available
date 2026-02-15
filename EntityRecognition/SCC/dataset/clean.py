import os
from tqdm import tqdm

input_file = "entity_cc.csv"
output_file = "entity_cleaned.csv"

print(f"[INFO] Reading file: {input_file}")

raw_line_count = 0
kept_line_count = 0

unique_addresses = set()
total_addresses_kept = 0  

with open(input_file, "r", encoding="utf-8") as f_in, open(output_file, "w", encoding="utf-8") as f_out:
    for line in tqdm(f_in, desc="Cleaning lines"):
        line = line.strip()
        if not line:
            continue

        raw_line_count += 1

        # split + strip
        parts = [x.strip() for x in line.split(",") if x.strip()]


        cleaned = [addr for addr in parts if addr.startswith("0x") and len(addr) == 42]


        if len(cleaned) < 2:
            continue

 
        f_out.write(",".join(cleaned) + "\n")
        kept_line_count += 1


        total_addresses_kept += len(cleaned)
        unique_addresses.update(cleaned)

dropped_line_count = raw_line_count - kept_line_count

print("\n[DONE] Cleaning completed!")
print(f"[INFO] Raw lines processed: {raw_line_count}")
print(f"[INFO] Kept lines written: {kept_line_count}")
print(f"[INFO] Dropped lines: {dropped_line_count}")
print(f"[INFO] Total addresses kept (with duplicates across lines): {total_addresses_kept}")
print(f"[INFO] Unique addresses kept: {len(unique_addresses)}")
print(f"[INFO] Output saved to: {output_file}")
