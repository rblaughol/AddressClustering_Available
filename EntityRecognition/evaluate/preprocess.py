import pandas as pd
import os

# Configure data directory
DATA_DIR = './exp_data'


def get_path(filename):
    """Helper function: Get the full path of the file"""
    return os.path.join(DATA_DIR, filename)


def process_baseline_llm(filename, output_filename):
    """Process Baseline LLM (Pipe separated)"""
    input_path = get_path(filename)
    output_path = get_path(output_filename)

    print(f"Processing: {filename} -> {output_filename}")
    data = []
    try:
        if not os.path.exists(input_path):
            print(f"File does not exist: {input_path}")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Skip header
            if lines and "entity_cluster" in lines[0]:
                lines = lines[1:]

            for idx, line in enumerate(lines):
                # Parse members
                members = [m.strip() for m in line.strip().split('|') if m.strip()]
                if members:
                    data.append({
                        'Cluster_ID': idx + 1,
                        'Members': ', '.join(members),
                        'Size': len(members)
                    })

        # Save file
        pd.DataFrame(data).to_csv(output_path, index=False, encoding='utf-8-sig')

    except Exception as e:
        print(f"Error processing {filename}: {e}")


def process_embedding_csv(filename, output_filename, type_label):
    """Process Embedding Method (CSV format, Semicolon separated)"""
    input_path = get_path(filename)
    output_path = get_path(output_filename)

    print(f"Processing: {filename} -> {output_filename}")
    try:
        if not os.path.exists(input_path):
            print(f"File does not exist: {input_path}")
            return

        df = pd.read_csv(input_path)
        data = []

        # Select column name based on type: Label task only takes members_names
        target_col = 'members' if type_label == 'ENS' else 'members_names'

        if target_col not in df.columns:
            print(f"Warning: Column '{target_col}' not found in {filename}")
            return

        for idx, row in df.iterrows():
            val = row[target_col]
            if pd.isna(val):
                continue

            # Clean data
            members = [m.strip() for m in str(val).split(';') if m.strip()]

            if members:
                data.append({
                    'Cluster_ID': idx + 1,
                    'Members': ', '.join(members),
                    'Size': len(members)
                })

        # Save file
        pd.DataFrame(data).to_csv(output_path, index=False, encoding='utf-8-sig')

    except Exception as e:
        print(f"Error processing {filename}: {e}")


def process_txt_method(filename, output_filename):
    """Process Proposed Method (TXT format, Comma separated)"""
    input_path = get_path(filename)
    output_path = get_path(output_filename)

    print(f"Processing: {filename} -> {output_filename}")
    data = []
    try:
        if not os.path.exists(input_path):
            print(f"File does not exist: {input_path}")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                members = [m.strip() for m in line.strip().split(',') if m.strip()]
                if members:
                    data.append({
                        'Cluster_ID': idx + 1,
                        'Members': ', '.join(members),
                        'Size': len(members)
                    })

        # Save file
        pd.DataFrame(data).to_csv(output_path, index=False, encoding='utf-8-sig')

    except Exception as e:
        print(f"Error processing {filename}: {e}")


def delete_original_files(file_list):
    """Delete original files"""
    print(f"\nStart cleaning original files from {DATA_DIR}...")
    for filename in file_list:
        file_path = get_path(filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted: {filename}")
            except Exception as e:
                print(f"Failed to delete {filename}: {e}")
        else:
            print(f"File not found, skipping: {filename}")


def main():
    # Check if directory exists
    if not os.path.exists(DATA_DIR):
        print(f"Error: Directory {DATA_DIR} not found. Please ensure it exists or modify DATA_DIR variable.")
        return

    # Define list of files to process (for later deletion)
    original_files = [
        'baseline_LLM_ENS.csv',
        'baseline_LLM_LABEL.csv',
        'ens_distilbert.csv',
        'ens_glove.csv',
        'ens_smpnet.csv',
        'labels_distilbert.csv',
        'labels_glove.csv',
        'labels_smpnet.csv',
        'final_entities_reviewed_ens.txt',
        'final_entities_reviewed_label.txt'
    ]

    print(f"Start processing directory: {DATA_DIR}\n")

    # Baseline LLM Files
    process_baseline_llm('baseline_LLM_ENS.csv', 'Baseline_LLM_ENS_exp.csv')
    process_baseline_llm('baseline_LLM_LABEL.csv', 'Baseline_LLM_Label_exp.csv')

    # Baseline Embedding Files (ENS)
    process_embedding_csv('ens_distilbert.csv', 'DistilBERT_ENS_exp.csv', type_label='ENS')
    process_embedding_csv('ens_glove.csv', 'GloVe_ENS_exp.csv', type_label='ENS')
    process_embedding_csv('ens_smpnet.csv', 'SMPNet_ENS_exp.csv', type_label='ENS')

    # Baseline Embedding Files (Labels)
    process_embedding_csv('labels_distilbert.csv', 'DistilBERT_Label_exp.csv', type_label='Label')
    process_embedding_csv('labels_glove.csv', 'GloVe_Label_exp.csv', type_label='Label')
    process_embedding_csv('labels_smpnet.csv', 'SMPNet_Label_exp.csv', type_label='Label')

    # Proposed Method Files (TXT)
    process_txt_method('final_entities_reviewed_ens.txt', 'Proposed_ENS_exp.csv')
    process_txt_method('final_entities_reviewed_label.txt', 'Proposed_Label_exp.csv')

    print("\nAll files processed, preparing to clean original files.")

    # Delete original files
    delete_original_files(original_files)

    print("\nAll tasks completed! Result files saved in exp_data directory.")


if __name__ == "__main__":
    main()