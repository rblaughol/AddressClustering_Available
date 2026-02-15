import json
import pandas as pd
import sys
import os

def preprocess_ens(input_file, output_file):
    print(f"Reading ENS data: {input_file}...")
    
    if not os.path.exists(input_file):
        print(f"Error: File not found {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        ens_list = json.load(f)
    
    domains = []
    
    for domain in ens_list:
        if not domain: 
            continue 
        domains.append(domain)
    
    unique_domains = list(dict.fromkeys(domains))
    
    initial_count = len(domains)
    final_count = len(unique_domains)
    
    print(f"Original records: {initial_count}")
    print(f"Unique records: {final_count}")
    
    if initial_count != final_count:
        print(f"Removed {initial_count - final_count} duplicates")
    
    df = pd.DataFrame(unique_domains, columns=['domain'])
    df.to_csv(output_file, index=False, header=False, encoding='utf-8')
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    INPUT_FILE = "all_ens_domains.json"    
    OUTPUT_FILE = "preprocessed_ens.csv"   
    
    preprocess_ens(INPUT_FILE, OUTPUT_FILE)
