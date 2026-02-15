import pandas as pd
import numpy as np
import faiss
import networkx as nx
import sys
import time
import os
import gc
import re

# ================= Configuration =================
VECTOR_DIR = "./vectors_10k"
OUTPUT_DIR = "./10w_result"

# Raw data paths (for extracting blacklist)
RAW_DATA_PATHS = {
    "ens": "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_ens.csv",
    "labels": "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/Baseline/dataset/preprocessed_labels.csv"
}

# Threshold (Use with Whitening. DistilBERT can also use 0.75 now)
FIXED_THRESHOLD = 0.75
TOP_K = 50
EF_CONSTRUCTION = 200
EF_SEARCH = 128
CHUNK_SIZE = 50000


# ===============================================

def build_global_blacklist():
    """Read raw CSVs to generate a blacklist of garbage IDs"""
    print(f"[{time.strftime('%X')}] Building garbage ID blacklist...")
    blacklist = set()

    # Process Labels
    path = RAW_DATA_PATHS["labels"]
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, usecols=['id', 'text'])
            garbage = df[df['text'].astype(str).str.contains("unknown", case=False, na=False)]
            blacklist.update(garbage['id'].astype(str).tolist())
            print(f"    - Added {len(garbage)} 'unknown_name' IDs from Labels")
        except Exception as e:
            print(f"    [Warning] Failed to read Labels raw file: {e}")

    # Process ENS
    path = RAW_DATA_PATHS["ens"]
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, usecols=['id', 'text'])

            def is_bad_ens(text):
                t = str(text)
                if re.match(r'^\[[a-f0-9]{30,}\](\.eth)?$', t, re.IGNORECASE): return True
                if len(t) < 4: return True
                return False

            garbage = df[df['text'].apply(is_bad_ens)]
            blacklist.update(garbage['id'].astype(str).tolist())
            print(f"    - Added {len(garbage)} invalid IDs from ENS")
        except Exception as e:
            print(f"    [Warning] Failed to read ENS raw file: {e}")

    print(f"[{time.strftime('%X')}] Blacklist build complete. Total {len(blacklist)} IDs to be excluded.")
    return blacklist


def compute_global_mean(filepath, total_rows, blacklist):
    """Compute global mean (Centering)"""
    print(f"[{time.strftime('%X')}] Computing global mean (Centering)...")
    peek = pd.read_csv(filepath, header=None, nrows=1, index_col=0, engine='c')
    dim = peek.shape[1]

    sum_vec = np.zeros(dim, dtype='float32')  # Initial type is float32
    valid_count = 0

    chunk_iter = pd.read_csv(filepath, header=None, index_col=0, chunksize=CHUNK_SIZE, engine='c')
    for chunk in chunk_iter:
        mask = ~chunk.index.isin(blacklist)
        valid_chunk = chunk[mask]
        if len(valid_chunk) > 0:
            vecs = valid_chunk.values.astype('float32')
            sum_vec += np.sum(vecs, axis=0)
            valid_count += len(valid_chunk)

    if valid_count == 0:
        return np.zeros(dim, dtype='float32')

    # Division might convert it to float64, keeping it as is for now
    return sum_vec / valid_count


def run_pipeline(filepath, output_path, blacklist):
    # Estimate row count
    with open(filepath, 'r') as f:
        total_rows_raw = sum(1 for _ in f)

    # Compute mean
    mean_vector = compute_global_mean(filepath, total_rows_raw, blacklist)
    # [Fix] Ensure mean vector itself is also float32
    mean_vector = mean_vector.astype('float32')

    # Build Index
    print(f"[{time.strftime('%X')}] Building index (Filtering + Whitening)...")
    peek = pd.read_csv(filepath, header=None, nrows=1, index_col=0)
    dim = peek.shape[1]

    index = faiss.IndexHNSWFlat(dim, 64, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = EF_CONSTRUCTION
    index.verbose = False

    chunk_iter = pd.read_csv(filepath, header=None, index_col=0, chunksize=CHUNK_SIZE, engine='c')
    all_valid_ids = []

    for chunk in chunk_iter:
        mask = ~chunk.index.isin(blacklist)
        chunk = chunk[mask]
        if len(chunk) == 0: continue

        ids_chunk = chunk.index.astype(str).tolist()
        vec_chunk = chunk.values.astype('float32')

        # Whitening (Subtraction)
        vec_chunk = vec_chunk - mean_vector

        # [Critical Fix]
        # Force convert back to float32 and ensure memory continuity
        # This resolves both "not C-contiguous" and "argument type float*" errors
        vec_chunk = np.ascontiguousarray(vec_chunk, dtype='float32')
        # End Critical Fix

        faiss.normalize_L2(vec_chunk)
        index.add(vec_chunk)
        all_valid_ids.extend(ids_chunk)

        print(f"\r    Valid Index: {len(all_valid_ids)}...", end='', flush=True)

    print(f"\n[{time.strftime('%X')}] Index build complete.")

    # Search and Graph Construction
    print(f"[{time.strftime('%X')}] Searching and constructing graph...")
    index.hnsw.efSearch = EF_SEARCH
    G = nx.Graph()
    G.add_nodes_from(range(len(all_valid_ids)))

    chunk_iter_2 = pd.read_csv(filepath, header=None, index_col=0, chunksize=CHUNK_SIZE, engine='c')
    global_offset = 0
    edge_count = 0

    for chunk in chunk_iter_2:
        mask = ~chunk.index.isin(blacklist)
        chunk = chunk[mask]
        if len(chunk) == 0: continue

        vec_chunk = chunk.values.astype('float32')
        vec_chunk = vec_chunk - mean_vector

        # [Critical Fix]
        # Same fix applied to search phase
        vec_chunk = np.ascontiguousarray(vec_chunk, dtype='float32')
        # End Critical Fix

        faiss.normalize_L2(vec_chunk)

        D, I = index.search(vec_chunk, TOP_K + 1)

        mask = D > FIXED_THRESHOLD
        rows, cols = np.where(mask)

        for r, c in zip(rows, cols):
            query_idx = global_offset + r
            neighbor_idx = I[r, c]

            if neighbor_idx < 0 or query_idx == neighbor_idx: continue
            if query_idx < neighbor_idx:
                G.add_edge(query_idx, neighbor_idx, weight=float(D[r, c]))
                edge_count += 1

        global_offset += len(chunk)
        print(f"\r    Searched: {global_offset}/{len(all_valid_ids)} | Edges: {edge_count}...", end='', flush=True)

    print(f"\n[{time.strftime('%X')}] Extracting entity clusters...")
    clusters = list(nx.connected_components(G))
    save_results(all_valid_ids, clusters, output_path)

    del index, G, all_valid_ids, clusters
    gc.collect()


def save_results(all_ids, clusters, output_file):
    print(f"[{time.strftime('%X')}] Saving results...")
    results_data = []
    clusters.sort(key=len, reverse=True)
    for c_id, node_indices in enumerate(clusters):
        size = len(node_indices)
        if size > 1:
            members = [all_ids[i] for i in node_indices]
            results_data.append({"cluster_id": c_id, "size": size, "members": "; ".join(members)})

    if results_data:
        df = pd.DataFrame(results_data)
        df.to_csv(output_file, index=False)
        print(f"    Successfully exported {len(df)} entities.")
    else:
        print("    No entities found.")


if __name__ == "__main__":
    if not os.path.exists(VECTOR_DIR): sys.exit(1)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    global_blacklist = build_global_blacklist()
    files = [f for f in os.listdir(VECTOR_DIR) if f.endswith(".csv")]
    files.sort()

    print(f"Global Threshold: {FIXED_THRESHOLD}")
    print("=" * 50)

    for filename in files:
        print(f"\n>>> Processing: {filename}")
        run_pipeline(os.path.join(VECTOR_DIR, filename),
                     os.path.join(OUTPUT_DIR, filename.replace(".csv", "_filtered.csv")),
                     global_blacklist)