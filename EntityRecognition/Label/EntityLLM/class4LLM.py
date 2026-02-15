import pandas as pd
import re
from collections import defaultdict
from tqdm import tqdm  # Progress bar library
import os

# Hyperparameter: length of the common substring
substring_length = 3  # You can adjust this to 2 or any other value

# Read the file
file_path = '/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/ENS/dataset/preprocessed_ens.csv'
df = pd.read_csv(file_path, header=None, names=['name'])

# Remove the .eth suffix
df['name'] = df['name'].str.replace(r'\.eth$', '', regex=True)

# Determine if a character is a special character (not distinguishing between specific symbols)
def is_special_char(char):
    return not (char.isalnum())  # Any character that is not a letter or digit is considered special

# Extract common substring from two strings
def get_common_substring(str1, str2, is_alpha=True):
    common_substring = ''
    min_len = min(len(str1), len(str2))
    
    for i in range(min_len):
        if is_alpha and str1[i].isalpha() and str1[i] == str2[i]:
            common_substring += str1[i]
        elif not is_alpha and not str1[i].isalnum() and str1[i] == str2[i]:
            common_substring += str1[i]
    
    return common_substring[:substring_length]  # Truncate to the specified length

# Assign shards based on letters, digits, and special characters
def get_shard_key(name):
    alpha_part = ''.join([c for c in name if c.isalpha()])
    digit_part = ''.join([c for c in name if c.isdigit()])
    special_part = ''.join([c for c in name if is_special_char(c)])

    return (alpha_part, digit_part, special_part)

# Create a dictionary to store members of each shard
shards = defaultdict(list)

# Process names with a progress bar
for name in tqdm(df['name'], desc="Processing names", unit="name"):
    alpha, digits, special = get_shard_key(name)

    # Build the shard key
    shard_key = (alpha[:substring_length], digits[:substring_length], special[:substring_length])

    # Add the name to the corresponding shard
    shards[shard_key].append(name)

# Ensure the output directory exists
output_dir = './dataset'
os.makedirs(output_dir, exist_ok=True)

# Save each shard to a separate file
for shard_key, names in shards.items():
    # Create a file name for each shard
    file_name = '_'.join(shard_key) + '.csv'
    file_path = os.path.join(output_dir, file_name)
    
    # Save the shard as a CSV file
    shard_df = pd.DataFrame(names, columns=['names'])
    shard_df.to_csv(file_path, index=False)

    print(f"Saved shard {shard_key} to {file_path}")
