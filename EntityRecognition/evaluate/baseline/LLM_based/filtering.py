from rapidfuzz import fuzz

try:
    from sentence_transformers import SentenceTransformer, util

    HAS_BERT = True
except ImportError:
    HAS_BERT = False


class ENSFilter:
    def filter(self, instance, top_k: int = 5, threshold: int = 85):  # Default threshold changed to 85
        anchor = instance["anchor"]
        candidates = instance["candidates"]

        scored = []
        for cand in candidates:
            # partial_ratio is suitable for substring matching
            score = fuzz.partial_ratio(anchor.lower(), cand.lower())

            # Length penalty: Prevent "abc" from matching "abcde...xyz"
            # Crucial for short domains
            len_diff = abs(len(anchor) - len(cand))
            if len_diff > 10:
                score -= 15  # Heavy penalty
            elif len(anchor) < 5 and len_diff > 0:
                score -= 20  # Severe penalty for very short text

            if score >= threshold:
                scored.append((cand, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:top_k]]


class LabelFilter:

    def __init__(self, all_texts=None, model_name='all-MiniLM-L6-v2'):
        """
        :param all_texts: A list containing all possible texts (List[str]).
                          Usually pass df['clean_text'].unique()
        """
        if not HAS_BERT:
            raise ImportError("Please install sentence-transformers to use LabelFilter")

        model_path = "./all-MiniLM-L6-v2-local"

        # Attempt to load model
        try:
            print(f"[LabelFilter] Attempting to load model locally: {model_path} ...")
            self.model = SentenceTransformer(model_path)
        except Exception:
            print(f"[LabelFilter] Local load failed, downloading: {model_name} ...")
            self.model = SentenceTransformer(model_name)

        # ---------------- Core Pre-computation Logic ----------------
        self.embedding_cache = {}

        if all_texts is not None and len(all_texts) > 0:
            print(f"[LabelFilter] Pre-computing vectors for {len(all_texts)} texts (this may take a few minutes)...")

            # Batch Encoding, much faster than single item
            # convert_to_tensor=True returns PyTorch Tensor, convenient for GPU/CPU ops
            embeddings = self.model.encode(list(all_texts), convert_to_tensor=True, show_progress_bar=True)

            # Build Index: Text -> Vector
            for text, emb in zip(all_texts, embeddings):
                self.embedding_cache[text] = emb

            print(f"[LabelFilter] Pre-computation complete, cache size: {len(self.embedding_cache)}")
        else:
            print("[LabelFilter] Warning: all_texts not provided, falling back to real-time mode (very slow).")
        # ------------------------------------------------------------

    def filter(self, instance, top_k: int = 5, threshold: float = 0.85):
        anchor = instance["anchor"]
        candidates = instance["candidates"]

        if not candidates: return []

        # Get Anchor Vector
        if anchor in self.embedding_cache:
            anchor_emb = self.embedding_cache[anchor]
        else:
            # Cache miss (rare), fallback to real-time calc
            anchor_emb = self.model.encode(anchor, convert_to_tensor=True)

        scored = []

        # Get Candidates Vector and Calculate
        for cand in candidates:
            if cand in self.embedding_cache:
                cand_emb = self.embedding_cache[cand]
            else:
                cand_emb = self.model.encode(cand, convert_to_tensor=True)

            # Calculate Cosine Similarity
            score = float(util.cos_sim(anchor_emb, cand_emb)[0][0])

            if score >= threshold:
                scored.append((cand, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:top_k]]