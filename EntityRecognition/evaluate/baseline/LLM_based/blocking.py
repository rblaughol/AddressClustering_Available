import pandas as pd
from retriv import SparseRetriever
import os
import shutil


def generate_char_ngrams(text, n=4):
    """
    Helper: Convert string to character N-gram sequence.
    Contains core denoising logic: Removes .eth suffix.
    """
    if not text:
        return ""

    # Lowercase and strip
    text = str(text).lower().strip()

    if text.endswith('.eth'):
        text = text[:-4]

    if not text:
        return ""

    if len(text) < n:
        return text

    # Sliding window segmentation
    grams = [text[i:i + n] for i in range(len(text) - n + 1)]

    return " ".join(grams)


def run_blocking(df_input: pd.DataFrame, top_k: int = 20, min_score: float = 6.0, index_name="blocking_index"):
    """
    Use BM25 (based on Character 4-grams) for DataFrame self-retrieval.
    """

    df = df_input.copy()
    df = df.reset_index(drop=True)

    # Force clean old index
    if os.path.exists(index_name):
        try:
            shutil.rmtree(index_name)
            print(f"[Info] Cleaned old index: {index_name}")
        except Exception as e:
            print(f"[Warning] Failed to clean old index: {e}")

    def generate_docs(dataframe):
        # idx here is definitely a safe integer: 0, 1, 2...
        for idx, row in dataframe.iterrows():
            raw_text = str(row.get('clean_text', ""))
            ngram_text = generate_char_ngrams(raw_text, n=4)

            yield {
                "id": str(idx),  # Storing safe ID from reset index
                "text": ngram_text,
            }

    print("Initializing retriever (Disabling Stopwords and Stemmer)...")

    # Initialize retriever
    retriever = SparseRetriever(
        index_name=index_name,
        stopwords=[],
        stemmer=None,
        min_df=1,
        tokenizer="whitespace"
    )

    print("Building index (based on Character 4-grams, .eth suffix removed)...")
    retriever.index(
        generate_docs(df),
        show_progress=True
    )

    print(f"Running global blocking, current min_score={min_score}...")
    queries = list(generate_docs(df))

    # Execute batch search
    results = retriever.bsearch(queries, cutoff=top_k, show_progress=True)

    blocked_data = []

    # Parse results
    for q_id, candidates_dict in results.items():
        # q_id is a string integer (e.g. "10")
        try:
            # int(q_id) is safe now because we reset_index
            current_idx = int(q_id)
            anchor_row = df.loc[current_idx]
            anchor_text = anchor_row.get('clean_text', "")
        except (KeyError, ValueError):
            continue

        valid_candidates = []

        for doc_id, score in candidates_dict.items():
            # Skip self
            if str(doc_id) == str(q_id):
                continue

            # Score filtering
            if score < min_score:
                continue

            try:
                # doc_id is also safe
                cand_idx = int(doc_id)
                cand_text = df.loc[cand_idx].get('clean_text', "")
                valid_candidates.append(cand_text)
            except (KeyError, ValueError):
                continue

        if valid_candidates:
            blocked_data.append({
                "anchor": anchor_text,
                "candidates": valid_candidates,
                "original_id": int(q_id)
            })

    return blocked_data