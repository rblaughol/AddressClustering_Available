import pandas as pd
from collections import Counter

def analyze_groups(input_file, output_file):
    print(f"Reading: {input_file}")
    
    try:
        df = pd.read_csv(input_file, header=0, names=['merged_group', 'group_size'])
    except Exception as e:
        print(f"Error: {str(e)}")
        return
    
    # Get group sizes
    group_sizes = df['group_size'].tolist()
    
    # Calculate statistics
    total_groups = len(df)
    total_elements = sum(group_sizes)
    
    # Count groups with different sizes
    groups_above_one = df[df['group_size'] > 1]
    groups_above_two = df[df['group_size'] >= 2]
    
    # Count elements in groups with more than 1 element
    elements_in_multi_groups = groups_above_one['group_size'].sum()
    
    # Create statistics
    stats = {
        'total_groups': [total_groups],
        'total_elements': [total_elements],
        'groups_size_1': [len(df[df['group_size'] == 1])],
        'groups_size_2_or_more': [len(groups_above_two)],
        'elements_in_groups_size_1': [df[df['group_size'] == 1]['group_size'].sum()],
        'elements_in_multi_groups': [elements_in_multi_groups],
        'avg_group_size': [total_elements / total_groups if total_groups > 0 else 0],
        'max_group_size': [max(group_sizes)],
        'min_group_size': [min(group_sizes)]
    }
    
    # Calculate size distribution
    size_dist = Counter(group_sizes)
    size_stats = []
    for size in sorted(size_dist.keys()):
        count = size_dist[size]
        elements = size * count
        size_stats.append([size, count, elements])
    
    # Create result DataFrames
    stats_df = pd.DataFrame(stats)
    size_df = pd.DataFrame(size_stats, columns=['group_size', 'count', 'elements'])
    
    # Save results
    stats_df.to_csv(output_file, index=False)
    size_file = output_file.replace('.csv', '_size_dist.csv')
    size_df.to_csv(size_file, index=False)
    
    print(f"\nTotal groups: {total_groups}")
    print(f"Total elements: {total_elements}")
    print(f"Groups with size 1: {len(df[df['group_size'] == 1])}")
    print(f"Groups with size >= 2: {len(groups_above_two)}")
    print(f"Elements in size 1 groups: {df[df['group_size'] == 1]['group_size'].sum()}")
    print(f"Elements in multi-element groups: {elements_in_multi_groups}")
    print(f"Average group size: {total_elements / total_groups:.2f}")
    print(f"Max group size: {max(group_sizes)}")
    print(f"Min group size: {min(group_sizes)}")
    
    print(f"\nSize distribution saved to: {size_file}")
    print(f"Summary statistics saved to: {output_file}")

if __name__ == "__main__":
    input_file = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/analysis/entity_cleaned.csv"
    output_file = "/public/home/blockchain_2/slave2/deanonymization/EntityRecognition/SCC/analysis/group_statistics.csv"
    
    analyze_groups(input_file, output_file)
    
    print("\nDone")