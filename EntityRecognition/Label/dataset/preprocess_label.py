import json
import pandas as pd
import sys
import os

def extract_names(input_file, output_file):
    print(f"Reading: {input_file}")
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        data_dict = json.load(f)
    
    names = []
    
    for info in data_dict.values():
        name = info.get("name", "")
        
        if name is None: 
            name = ""
        name = str(name).strip()
        
        if name:
            names.append(name)
    
    # Remove duplicates
    unique_names = list(set(names))
    
    initial_count = len(names)
    final_count = len(unique_names)
    
    print(f"Original names: {initial_count}")
    print(f"Unique names: {final_count}")
    
    if initial_count != final_count:
        print(f"Removed {initial_count - final_count} duplicates")
    
    # Create dataframe and save
    df = pd.DataFrame(unique_names, columns=['name'])
    df.to_csv(output_file, index=False, header=False, encoding='utf-8')
    print(f"Saved: {output_file}")

if __name__ == "__main__":
    INPUT_FILE = "combinedAllLabels.json" 
    OUTPUT_FILE = "preprocessed_labels.csv"
    
    extract_names(INPUT_FILE, OUTPUT_FILE)