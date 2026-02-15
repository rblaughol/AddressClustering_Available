import torch
import torch.multiprocessing as mp
import pandas as pd
import time
import numpy as np
import os
import gc
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import normalize

# ================= Configuration =================
CSV_PATH = '/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_ens.csv'
# CSV_PATH = 'clean_ens.csv' # For local testing
MODEL_PATH = '/public/home/blockchain/yanruibin/LLM/LLM4TX/Model/Qwen3-Embedding-0.6B'

# Directory to save results
OUTPUT_DIR = 'ens_500_clusters_2'

NUM_PROCESSES = 4
BATCH_SIZE = 2048  # Inference Batch Size (VRAM dependent)
N_CLUSTERS = 500  # Number of clusters

# Clustering batch size (CPU/Memory dependent, larger is faster)
CLUSTER_BATCH_SIZE = 65536


# ================= Core Functions =================
def last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Extract the hidden state of the last token in the sequence.
    """
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_states.shape[0]
    return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


# ================= Worker: Sub-process Logic =================
def run_worker(rank, world_size, all_texts, result_list):
    # VRAM allocation logic
    num_gpus = torch.cuda.device_count()
    device = f"cuda:{rank % num_gpus}" if num_gpus > 0 else "cpu"

    # Data slicing
    total_len = len(all_texts)
    chunk_size = total_len // world_size
    start_idx = rank * chunk_size
    end_idx = (rank + 1) * chunk_size if rank != world_size - 1 else total_len
    my_texts = all_texts[start_idx: end_idx]

    print(f"[P{rank}] Started! Device: {device} | Processing {len(my_texts)} items")

    # padding_side='right' is a critical fix for Qwen and similar models
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, padding_side='right', trust_remote_code=True)
    model = AutoModel.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16, trust_remote_code=True).to(device)
    model.eval()

    local_embeddings = []

    # Inference loop
    for i in tqdm(range(0, len(my_texts), BATCH_SIZE), desc=f"P{rank}", position=rank):
        batch_texts = my_texts[i: i + BATCH_SIZE]
        # Note: max_length=32 might truncate long domains; adjust based on your data distribution
        inputs = tokenizer(batch_texts, padding=True, truncation=True, max_length=32, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            embeddings = last_token_pool(outputs.last_hidden_state, inputs['attention_mask'])
            local_embeddings.append(embeddings.cpu().float().numpy())

    result_list[rank] = np.concatenate(local_embeddings, axis=0)


# ================= Main Execution =================
if __name__ == "__main__":
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass

    print(f"--- Vectorization + MiniBatchKMeans Clustering ---")

    # Load Data
    print("Loading data...")
    df = pd.read_csv(CSV_PATH)

    # Ensure we only have string type texts
    all_texts = df['text'].dropna().astype(str).tolist()
    print(f"   Total Data Points: {len(all_texts)}")

    # Parallel Feature Extraction
    manager = mp.Manager()
    result_list = manager.list([None] * NUM_PROCESSES)

    print(f"Starting parallel inference (Processes: {NUM_PROCESSES})...")
    start_inference = time.time()

    mp.spawn(
        run_worker,
        args=(NUM_PROCESSES, all_texts, result_list),
        nprocs=NUM_PROCESSES,
        join=True
    )

    print(f"   Inference complete, time elapsed: {time.time() - start_inference:.2f}s")

    # Aggregate and Normalize
    print("Aggregating and normalizing...")
    all_embeddings = np.concatenate(list(result_list), axis=0)

    # Release sub-process memory
    del result_list
    gc.collect()

    # L2 Normalization (Important: makes Euclidean distance equivalent to Cosine Similarity)
    all_embeddings = normalize(all_embeddings, norm='l2')

    # Clustering
    print(f"Starting clustering (MiniBatchKMeans, k={N_CLUSTERS})...")
    start_cluster = time.time()

    # Use MiniBatchKMeans
    # batch_size: number of samples per iteration, larger is more accurate but higher memory
    # n_init: number of re-initializations, 3 is a balance between speed and quality
    kmeans = MiniBatchKMeans(
        n_clusters=N_CLUSTERS,
        batch_size=CLUSTER_BATCH_SIZE,
        n_init=3,
        random_state=42,
        max_no_improvement=10,
        verbose=0
    )

    cluster_labels = kmeans.fit_predict(all_embeddings)

    print(f"   Clustering complete, time elapsed: {time.time() - start_cluster:.2f}s")

    # Save Results
    print("-" * 30)
    print(f"Saving results to directory: {OUTPUT_DIR}/ ...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Build temporary DataFrame for filtering
    df_result = pd.DataFrame({
        'text': all_texts,
        'cluster': cluster_labels
    })

    # Use groupby to accelerate saving process (faster than loop filtering)
    grouped = df_result.groupby('cluster')

    for cluster_id, group_data in tqdm(grouped, total=N_CLUSTERS, desc="Saving Files"):
        file_path = os.path.join(OUTPUT_DIR, f'cluster_{cluster_id}.csv')
        # Save only the text column
        group_data['text'].to_csv(file_path, index=False, header=False)

    print("-" * 30)
    print(f"✅ All tasks completed!")