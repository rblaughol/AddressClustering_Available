import pandas as pd
import os
import sys
# Import the core library you uploaded
from vectorization import create_embeddings

# --- Configuration Area ---
INPUT_FILES = {
    'ens': '/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_ens.csv',
    'labels': '/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_labels.csv'
}

# The three models you specified
# Note: Strings correspond to 'glove', 'distilbert', 'smpnet' in vectorization.py
MODELS = ['glove', 'distilbert', 'smpnet']
# MODELS = ['glove']

OUTPUT_DIR = 'vectors/'  # Directory to save results
LOG_DIR = 'logs/'  # Directory to save logs
STATIC_DIR = 'static_models/'  # Placeholder path, these models download from HuggingFace automatically


def run_vectorization():
    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Iterate through datasets
    for dataset_name, filepath in INPUT_FILES.items():
        print(f"\n==========================================")
        print(f"Processing dataset: {dataset_name} ({filepath})")
        print(f"==========================================")

        if not os.path.exists(filepath):
            print(f"❌ Error: File not found {filepath}")
            continue

        # Read data
        try:
            df = pd.read_csv(filepath)
            # Force cast to string to prevent pure numbers being identified as numeric types
            df['text'] = df['text'].astype(str)

            text_list = df['text'].tolist()
            index_list = df['id'].tolist()
            print(f"Data loaded successfully, total {len(df)} records.")

        except Exception as e:
            print(f"❌ Failed to read CSV: {e}")
            continue

        # Iterate through models
        for model_name in MODELS:
            print(f"\n[Task Started] Model: {model_name} -> Dataset: {dataset_name}")

            # Construct output filename, e.g., vectors/ens_glove.csv
            output_path = os.path.join(OUTPUT_DIR, f"{dataset_name}_{model_name}.csv")
            log_file = os.path.join(LOG_DIR, f"log_{dataset_name}.txt")

            # Prepare log dictionary for create_embeddings
            log_info = {
                'dataset': dataset_name,
                'model': model_name,
                'total_records': len(df)
            }

            try:
                # Call core function
                create_embeddings(
                    text=text_list,
                    vectorizer=model_name,
                    log=log_info,
                    log_file=log_file,
                    output_path=output_path,
                    output_index=index_list,
                    static_dir=STATIC_DIR
                )
                print(f"✅ Done! Results saved to: {output_path}")

            except RuntimeError as e:
                if "CUDA" in str(e):
                    print(f"❌ GPU Error: Your server might not have a GPU or CUDA is misconfigured.")
                    print(f"Detailed Error: {e}")
                else:
                    print(f"❌ Runtime Error: {e}")
            except Exception as e:
                print(f"❌ Unknown Error: {e}")


if __name__ == "__main__":
    run_vectorization()