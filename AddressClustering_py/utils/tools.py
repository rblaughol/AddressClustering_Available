import json
import os
import argparse
import sys
from typing import Set, List, Dict, Any

def save_cluster_nodes(cluster_nodes, file_path):
    """Save clustering results to file"""
    if isinstance(cluster_nodes, set):
        data = list(cluster_nodes)
    elif isinstance(cluster_nodes, dict):
        # Save directly if in dictionary format
        data = cluster_nodes
    else:
        data = cluster_nodes
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def load_cluster_nodes(file_path):
    """Load saved cluster nodes"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set(data.get('cluster_nodes', []))
    return set()

# Add command line argument parsing at the beginning of file
def parse_args():
    parser = argparse.ArgumentParser(description='Address Clustering & Expansion Tool')
    parser.add_argument('--start_num', type=int, required=True, help='Start index for seed addresses')
    parser.add_argument('--end_num', type=int, required=True, help='End index for seed addresses')
    parser.add_argument('--api_controller', type=int, default=0, help='API controller index')
    return parser.parse_args()

def setup_logging(start_num, end_num, api_controller):
    # Create log directory
    log_dir = "./expand_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename
    log_filename = f"log_{start_num}-{end_num}_API{api_controller}.txt"
    log_path = os.path.join(log_dir, log_filename)
    
    # Redirect stdout and stderr to log file
    class Logger:
        def __init__(self, filename):
            self.terminal = sys.stdout
            self.logfile = open(filename, 'w', encoding='utf-8')
        
        def write(self, message):
            self.terminal.write(message)
            self.logfile.write(message)
            self.logfile.flush()
        
        def flush(self):
            self.terminal.flush()
            self.logfile.flush()
    
    sys.stdout = Logger(log_path)
    sys.stderr = Logger(log_path)

def load_seed_members(file_path):
    """Load seed member addresses (Input Seeds)"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return [key.lower() for key in data.keys()]

def load_seed_members_fromTxt(file_path):
    """Load seed member addresses from TXT"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    return [line.strip().lower() for line in lines if line.strip()]

def filter_tx_list(tx_list: List[Dict], cluster_nodes: Set[str], checked_neighbors: Set[str], current_node: str = None) -> List[Dict]:
    """Filter transaction list, remove transactions with known cluster nodes"""
    filtered_txs = []
    filtered_cnt = 0
    for tx in tx_list:
        source = tx.get('source')
        target = tx.get('target')
        
        opponent = source if target == current_node else target if source == current_node else None
        
        if opponent and (opponent in cluster_nodes or opponent in checked_neighbors):
            filtered_cnt += 1
            continue  # Skip transactions with known cluster nodes or checked neighbors
        
        filtered_txs.append(tx)
    print(f"Filtered out {filtered_cnt} transactions")
    return filtered_txs

def preprocess_tx_list(tx_list: List[Dict]) -> List[Dict]:
    """Preprocess transaction list: Retain only Native transfers and exclude Create operations"""
    return [
        tx for tx in tx_list 
        if tx['type'] == 'native' 
        and float(tx['amount']) != 0 
        and tx['trace_type'] != 'create'
    ]

def find_latest_checkpoint(output_file, total_seeds):
    """Find the latest checkpoint file"""
    import os
    import glob
    
    pattern = f"./real_time_expand/{output_file}_checkpoint_*.json"
    checkpoints = glob.glob(pattern)
    
    if not checkpoints:
        return None, None
    
    # Find checkpoint with the largest number
    max_i = 0
    latest_checkpoint = None
    for cp in checkpoints:
        try:
            i = int(cp.split('_')[-1].replace('.json', ''))
            if i <= total_seeds and i > max_i:
                max_i = i
                latest_checkpoint = cp
        except:
            continue
    
    return latest_checkpoint, max_i

def load_checkpoint(checkpoint_path):
    """Load checkpoint file"""
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        checkpoint_data = json.load(f)
    
    return checkpoint_data