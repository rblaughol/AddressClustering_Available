import os
import pandas as pd
import glob

def merge_processed_files(input_dir, output_file):    
    # Find all processed CSV files
    pattern = os.path.join(input_dir, "processed_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        print(f"No processed CSV files found in {input_dir}")
        return
    
    print(f"Found {len(csv_files)} processed CSV files")
    
    all_data = []
    total_rows = 0
    
    for file_path in csv_files:
        try:
            file_name = os.path.basename(file_path)
            print(f"Reading: {file_name}")
            
            # Read file without header
            df = pd.read_csv(file_path, header=None, names=['address', 'creator'])
            
            all_data.append(df)
            total_rows += len(df)
            print(f"  Added: {len(df)} rows")
            
        except Exception as e:
            print(f"Error reading {file_name}: {str(e)}")
    
    if all_data:
        # Merge all dataframes
        merged_df = pd.concat(all_data, ignore_index=True)
        
        # Remove duplicates (if any)
        initial_count = len(merged_df)
        merged_df = merged_df.drop_duplicates()
        final_count = len(merged_df)
        
        # Save to CSV without header
        merged_df.to_csv(output_file, index=False, header=False)
        
        
    else:
        print("No data to merge")

if __name__ == "__main__":
    # Configuration
    input_directory = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/dataset"
    output_file = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/dataset/merged_cc.csv"
    print("-" * 40)
    
    # Merge files
    merge_processed_files(input_directory, output_file)
    
    print("\nMerge completed!")