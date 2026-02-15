#!/usr/bin/env python
import numpy as np
from transformers import BertTokenizer, BertModel
from transformers import DistilBertTokenizer, DistilBertModel
from transformers import RobertaTokenizer, RobertaModel
from transformers import XLNetTokenizer, XLNetModel
from sentence_transformers import SentenceTransformer
from transformers import AlbertTokenizer, AlbertModel
import transformers
import torch
from time import time
import os
import pandas as pd
import json

transformers.logging.set_verbosity_error()

# --- Auto-detect Device ---
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Current device: {DEVICE}")

# ================= Configuration =================
MODEL_ROOT = './'


# ===============================================

def create_embeddings(text, vectorizer, log, log_file, output_path, output_index,
                      static_dir, b=500):
    # [Safety Optimization] Force convert all inputs to strings to prevent replace errors
    text = [str(t) for t in text]

    # Handle HuggingFace Transformers Models (e.g., DistilBERT)
    if vectorizer in ['bert', 'distilbert', 'roberta', 'xlnet', 'albert']:
        b = 32
        init_time = time()
        model_name_or_path = ""

        if vectorizer == 'distilbert':
            # Point to local distilbert_model folder
            model_name_or_path = os.path.join(MODEL_ROOT, 'distilbert_model')
            print(f"Loading local model: {model_name_or_path}")

            if not os.path.exists(model_name_or_path):
                print(f"❌ Error: Model folder {model_name_or_path} not found")
                return []

            tokenizer = DistilBertTokenizer.from_pretrained(model_name_or_path)
            model = DistilBertModel.from_pretrained(model_name_or_path)

        # Compatibility: Other models remain as they were
        elif vectorizer == 'bert':
            tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
            model = BertModel.from_pretrained("bert-base-uncased")
        elif vectorizer == 'roberta':
            tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
            model = RobertaModel.from_pretrained('roberta-base')
        elif vectorizer == 'xlnet':
            tokenizer = XLNetTokenizer.from_pretrained('xlnet-base-cased')
            model = XLNetModel.from_pretrained('xlnet-base-cased')
        elif vectorizer == 'albert':
            tokenizer = AlbertTokenizer.from_pretrained('albert-base-v2')
            model = AlbertModel.from_pretrained("albert-base-v2")

        model.to(DEVICE)
        init_time = time() - init_time
        vect_time = 0

        with open(output_path, 'w') as o:
            total = len(range(0, len(text), b))
            for i in range(0, len(text), b):
                print(f'\r\t {i // b}/{total}', end='')
                t1 = time()
                temp_text = text[i:i + b]
                temp_index = output_index[i:i + b]

                encoded_input = tokenizer(temp_text, return_tensors='pt', truncation=True,
                                          max_length=100, padding='max_length')
                encoded_input = encoded_input.to(DEVICE)

                with torch.no_grad():
                    output = model(**encoded_input)

                vectors = output.last_hidden_state[:, 0, :]
                t2 = time()
                vect_time += t2 - t1

                vectors = vectors.detach().cpu().numpy()
                df = pd.DataFrame(vectors)
                df.index = temp_index
                df.to_csv(o, index=True, header=False)

    # Handle SentenceTransformers Models (e.g., S-MPNet, GloVe)
    elif vectorizer in ['smpnet', 'st5', 'glove', 'sdistilroberta', 'sminilm']:
        b = 500
        init_time = time()
        local_path = ""

        # Set Paths
        if vectorizer == 'smpnet':
            local_path = os.path.join(MODEL_ROOT, 'smpnet_model')
        elif vectorizer == 'glove':
            local_path = os.path.join(MODEL_ROOT, 'glove_model')
            # [GloVe Special Handling] Text is already string, safe to replace
            print("Preprocessing input for GloVe (replacing . and _ with spaces)...")
            text = [t.replace('.', ' ').replace('_', ' ') for t in text]

        # Other models not downloaded locally yet
        elif vectorizer == 'st5':
            local_path = 'gtr-t5-base'
        elif vectorizer == 'sdistilroberta':
            local_path = 'all-distilroberta-v1'
        elif vectorizer == 'sminilm':
            local_path = 'all-MiniLM-L6-v2'

        print(f"Loading model: {local_path}")
        if os.path.exists(local_path) or '/' not in local_path:
            model = SentenceTransformer(local_path, device=DEVICE)
        else:
            print(f"❌ Error: Local model folder {local_path} not found")
            return []

        init_time = time() - init_time
        vect_time = 0

        with open(output_path, 'w') as o:
            total = len(range(0, len(text), b))
            for i in range(0, len(text), b):
                print(f'\r\t {i // b}/{total}', end='')
                t1 = time()
                temp_text = text[i:i + b]
                temp_index = output_index[i:i + b]

                vectors = model.encode(temp_text)

                t2 = time()
                vect_time += t2 - t1

                df = pd.DataFrame(vectors)
                df.index = temp_index
                df.to_csv(o, index=True, header=False)

    else:
        print(f"Warning: Unknown vectorizer '{vectorizer}'")
        return []

    # Logging
    log['init_time'] = init_time
    log['time'] = vect_time
    if 'vectors' in locals() and len(vectors) > 0:
        log['dimensions'] = vectors.shape[1]
    elif 'df' in locals() and not df.empty:
        log['dimensions'] = df.shape[1]
    else:
        log['dimensions'] = 0

    with open(log_file, 'a') as f:
        f.write(json.dumps(log) + "\n")

    return []