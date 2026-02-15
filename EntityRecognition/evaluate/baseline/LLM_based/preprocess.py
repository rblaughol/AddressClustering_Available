import pandas as pd
import re
import unicodedata


def clean_ens_text(text):
    if pd.isna(text):
        return ""

    text = str(text).strip()

    # Unicode Normalization (Ensure uniform character encoding)
    text = unicodedata.normalize('NFKC', text)

    # Unify lowercase (ENS protocol is case-insensitive)
    text = text.lower()

    # Remove invisible characters (e.g. zero-width space, prevents index interference)
    text = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff]', '', text)

    return text


def clean_label_text(text):
    if pd.isna(text):
        return ""

    text = str(text).strip()

    # Filter obvious useless data
    if "unknown_name" in text.lower():
        return ""

    # Normalization
    text = unicodedata.normalize('NFKC', text)
    text = text.strip()

    return text


def main():
    print("🚀 Starting adjusted preprocessing (ENS Hash will be kept)...")

    # Process ENS
    try:
        # Suggest specifying dtype to avoid warnings
        df_ens = pd.read_csv("preprocessed_ens_10k.csv")
        print(f"ENS original row count: {len(df_ens)}")

        df_ens['clean_text'] = df_ens['text'].apply(clean_ens_text)

        # Only filter completely empty rows
        df_ens = df_ens[df_ens['clean_text'] != ""]

        df_ens.to_csv("clean_ens.csv", index=False)
        print(f"✅ ENS processing complete, current row count: {len(df_ens)}")
    except FileNotFoundError:
        print("⚠️ preprocessed_ens_10k.csv not found")

    print("-" * 30)

    # Process Label
    try:
        df_labels = pd.read_csv("preprocessed_labels.csv")
        print(f"Label original row count: {len(df_labels)}")

        df_labels['clean_text'] = df_labels['text'].apply(clean_label_text)

        # Filter empty lines and very short texts
        df_labels = df_labels[df_labels['clean_text'] != ""]
        df_labels = df_labels[df_labels['clean_text'].str.len() > 1]

        # Deduplicate
        df_labels = df_labels.drop_duplicates(subset=['clean_text'])

        df_labels.to_csv("clean_labels.csv", index=False)
        print(f"✅ Label processing complete, current row count: {len(df_labels)}")

    except FileNotFoundError:
        print("⚠️ preprocessed_labels.csv not found")


if __name__ == "__main__":
    main()