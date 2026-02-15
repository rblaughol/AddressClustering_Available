import pandas as pd
import os
import sys

# ================= Configuration =================
# Directory where clustering results are located (from previous step's output)
RESULTS_DIR = "./results_filtered"

# Raw Label data path (used to lookup Name by ID)
# Note: This is the path you provided previously
LABEL_SOURCE_FILE = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_labels.csv"


# ===============================================

def load_id_map():
    """Load raw data, build ID -> Name mapping dictionary"""
    print(f"Loading raw label mapping: {LABEL_SOURCE_FILE} ...")
    if not os.path.exists(LABEL_SOURCE_FILE):
        print(f"Error: File {LABEL_SOURCE_FILE} not found")
        sys.exit(1)

    try:
        # Read only id and text columns
        df = pd.read_csv(LABEL_SOURCE_FILE, usecols=['id', 'text'], dtype=str)
        # Convert to dictionary: {'0x123...': 'Uniswap V2', ...}
        # Use strip() to remove potential whitespace
        mapping = pd.Series(df.text.values, index=df.id).to_dict()
        print(f"Mapping loaded, total {len(mapping)} records.")
        return mapping
    except Exception as e:
        print(f"Read failed: {e}")
        sys.exit(1)


def translate_file(filename, id_map):
    input_path = os.path.join(RESULTS_DIR, filename)
    output_filename = filename.replace(".csv", "_translated.csv")
    output_path = os.path.join(RESULTS_DIR, output_filename)

    print(f"\n>>> Translating: {filename}")
    try:
        df = pd.read_csv(input_path)

        # Check if members column exists
        if 'members' not in df.columns:
            print("    [Skip] File does not have 'members' column")
            return

        new_rows = []

        # Iterate through each row (each cluster)
        for index, row in df.iterrows():
            cluster_id = row['cluster_id']
            size = row['size']
            members_str = str(row['members'])

            # Split IDs (Assuming separator is "; ")
            ids = members_str.split('; ')

            # Lookup corresponding names
            # If ID not found, show "UNKNOWN(id)"
            names = [str(id_map.get(i, f"UNKNOWN({i})")) for i in ids]

            # Recombine into string
            names_str = "; ".join(names)

            new_rows.append({
                "cluster_id": cluster_id,
                "size": size,
                "members_ids": members_str,  # Keep original IDs
                "members_names": names_str   # Add names column
            })

        # Save results
        df_out = pd.DataFrame(new_rows)
        # Move members_names to the front for easier viewing
        cols = ['cluster_id', 'size', 'members_names', 'members_ids']
        df_out = df_out[cols]

        df_out.to_csv(output_path, index=False)
        print(f"    Translation complete! Saved to: {output_filename}")

        # Print preview of first 3 rows
        print("    [Result Preview]:")
        for i in range(min(3, len(df_out))):
            print(f"    Cluster {i}: {df_out.iloc[i]['members_names'][:100]}...")

    except Exception as e:
        print(f"    Processing failed: {e}")


if __name__ == "__main__":
    if not os.path.exists(RESULTS_DIR):
        print(f"Error: Results directory {RESULTS_DIR} does not exist")
        sys.exit(1)

    # Load dictionary
    id_map = load_id_map()

    # Find all labels related result files
    files = [f for f in os.listdir(RESULTS_DIR) if "labels" in f and f.endswith(".csv") and "translated" not in f]
    files.sort()

    if not files:
        print("No labels-related cluster files found.")
        sys.exit(0)

    print(f"Found {len(files)} files to translate...")

    # Batch translation
    for f in files:
        translate_file(f, id_map)

    print("\nAll files translated!")