import pandas as pd
import sys
from collections import Counter
from tqdm import tqdm
import re  # Import the regular expression module

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}
    
    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            return x
        
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x, y):
        root_x = self.find(x)
        root_y = self.find(y)
        
        if root_x != root_y:
            if self.rank[root_x] < self.rank[root_y]:
                self.parent[root_x] = root_y
            elif self.rank[root_x] > self.rank[root_y]:
                self.parent[root_y] = root_x
            else:
                self.parent[root_y] = root_x
                self.rank[root_x] += 1
            return True
        return False

def merge_connected_addresses(input_file, output_file):
    print(f"Reading: {input_file}")
    
    try:
        df = pd.read_csv(input_file, header=None, names=['address', 'creator'])
    except Exception as e:
        print(f"Error: {str(e)}")
        return
    
    print(f"Rows: {len(df)}")
    
    # Define the Ethereum address regex pattern
    address_pattern = r"^0x[a-fA-F0-9]{40}$"
    
    # Filter the rows where both address and creator match the pattern
    df = df[df['address'].apply(lambda x: x.startswith("0x") and len(x) == 42) &
            df['creator'].apply(lambda x: x.startswith("0x") and len(x) == 42)]
    
    print(f"Filtered Rows: {len(df)}")
    
    uf = UnionFind()
    print("Building connections...")
    
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing"):
        uf.union(row['address'], row['creator'])
    
    all_nodes = set(df['address']).union(set(df['creator']))
    
    groups = {}
    print("Grouping nodes...")
    
    for node in tqdm(all_nodes, desc="Grouping", total=len(all_nodes)):
        root = uf.find(node)
        if root not in groups:
            groups[root] = set()
        groups[root].add(node)
    
    output_data = []
    for group in tqdm(groups.values(), desc="Formatting"):
        if group:
            group_str = ",".join(sorted(group))
            output_data.append([group_str, len(group)])
    
    output_data.sort(key=lambda x: x[1], reverse=True)
    
    output_df = pd.DataFrame(output_data, columns=['merged_group', 'group_size'])
    output_df.to_csv(output_file, index=False)
    
    print(f"\nComponents: {len(output_data)}")
    print(f"Saved: {output_file}")

if __name__ == "__main__":
    input_file = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/dataset/merged_cc.csv"
    output_file = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/dataset/entity_cc.csv"
    
    merge_connected_addresses(input_file, output_file)
    
    print("\nDone")
