import time
from datetime import datetime
from collections import deque
from utils.config import *
from utils.rpc_client import TxListProvider, TimeoutController
from utils.heuristics import *
from utils.tools import *

# Load seed address list (Input Source)
ALL_SEED_ADDRESSES = load_seed_members_fromTxt('./sampled_seeds_1000.txt')

def explore_cluster(seed_node, provider, processed_nodes):
    """
    Explore associated cluster of a single seed node
    Integrate heuristic exploration, recording SG1 and SG2 results separately
    Return: (all_cluster_members, sg1_nodes, sg2_nodes)
    """

    timeout_controller = TimeoutController(total_timeout_seconds=600)  # 10 minutes
    provider.timeout_controller = timeout_controller

    working_queue = deque([seed_node])
    cluster_members = set([seed_node])  # Result set: Cluster

    # Record nodes found by different strategies separately (excluding seed itself)
    found_by_sg1 = set()
    found_by_sg2 = set()

    # Local processed set to prevent duplication within single BFS
    local_processed = set()

    while working_queue:
        if timeout_controller.is_timeout():
            print(f"Seed node {seed_node} overall processing timeout, returning current results")
            break

        current_node = working_queue.popleft().lower()

        # Skip if processed globally or locally
        if current_node in local_processed or current_node in processed_nodes:
            continue

        local_processed.add(current_node)

        try:
            # Get complete transaction list for current node
            all_tx_list = provider.get_addr_tx_list(current_node)
            tx_list = preprocess_tx_list(all_tx_list)
        except Exception as e:
            print(f"Error getting transaction list for node {current_node}: {e}")
            continue

        # ==========================
        # Apply SG1 Heuristic (Fund Aggregation)
        # ==========================
        sg1_groups = apply_sg1_heuristic(current_node, tx_list, provider, processed_nodes)
        if sg1_groups:
            found_by_sg1.update(sg1_groups)

        # ==========================
        # Apply SG2 Heuristic (Multi-Deposit)
        # ==========================
        sg2_groups = apply_sg2_heuristic(current_node, tx_list, provider, processed_nodes)
        if sg2_groups:
            found_by_sg2.update(sg2_groups)

        # Merge newly found cluster members and add to queue for continued exploration
        newly_found = (sg1_groups | sg2_groups) - cluster_members

        for addr in newly_found:
            cluster_members.add(addr)
            working_queue.append(addr)

    # Exclude seed itself when returning
    return cluster_members, found_by_sg1, found_by_sg2


def expand_clustering_task(seed_addresses, provider, output_file, save_interval=10000):
    """Expand address clustering on actual dataset"""
    processed_nodes = set()

    # Record mapping relationship: Seed -> Cluster Results
    seed_to_expanded_nodes = {}  # Total union
    seed_to_sg1_nodes = {}  # SG1 only
    seed_to_sg2_nodes = {}  # SG2 only

    total_seeds = len(seed_addresses)
    start_time = time.time()

    print(f"Start processing {total_seeds} seed nodes...")

    for i, seed in enumerate(seed_addresses, 1):
        seed = seed.lower()

        # Progress printing
        elapsed_time = time.time() - start_time
        avg_time_per_node = elapsed_time / i if i > 0 else 0
        remaining_time = avg_time_per_node * (total_seeds - i)
        print(f"Progress: {i}/{total_seeds} | Seed: {seed} | Remaining: {remaining_time / 60:.1f} min")

        # Execute exploration
        cluster_members, sg1_nodes, sg2_nodes = explore_cluster(seed, provider, processed_nodes)

        # Record results (excluding seed itself)
        expanded_total = list(cluster_members - {seed})

        if expanded_total:
            seed_to_expanded_nodes[seed] = expanded_total

        if sg1_nodes:
            seed_to_sg1_nodes[seed] = list(sg1_nodes)

        if sg2_nodes:
            seed_to_sg2_nodes[seed] = list(sg2_nodes)

        # Save periodically
        if i % save_interval == 0:
            checkpoint_data = {
                'seed_to_expanded_nodes': seed_to_expanded_nodes,
                'seed_to_sg1_nodes': seed_to_sg1_nodes,
                'seed_to_sg2_nodes': seed_to_sg2_nodes,
                'current_processed_seeds': i
            }
            save_cluster_nodes(checkpoint_data, f"./real_time_expand/{output_file}_checkpoint_{i}.json")
            print(f"Checkpoint saved")

    # Statistics of total results
    total_cluster_nodes = set()
    total_sg1_nodes = set()
    total_sg2_nodes = set()

    for nodes in seed_to_expanded_nodes.values(): total_cluster_nodes.update(nodes)
    for nodes in seed_to_sg1_nodes.values(): total_sg1_nodes.update(nodes)
    for nodes in seed_to_sg2_nodes.values(): total_sg2_nodes.update(nodes)

    # Final save structure
    final_result = {
        'total_cluster_nodes': len(total_cluster_nodes),
        'total_sg1_nodes_count': len(total_sg1_nodes),
        'total_sg2_nodes_count': len(total_sg2_nodes),

        'seed_to_expanded_nodes': seed_to_expanded_nodes,
        'seed_to_sg1_nodes': seed_to_sg1_nodes,
        'seed_to_sg2_nodes': seed_to_sg2_nodes,

        'all_cluster_nodes': list(total_cluster_nodes),
        'all_sg1_nodes': list(total_sg1_nodes),
        'all_sg2_nodes': list(total_sg2_nodes),

        'final_time': time.time() - start_time
    }

    save_cluster_nodes(final_result, output_file)
    print(f"\nProcessing complete! Total expanded cluster members: {len(total_cluster_nodes)} (SG1: {len(total_sg1_nodes)}, SG2: {len(total_sg2_nodes)})")


if __name__ == "__main__":
    args = parse_args()
    START_NUM, END_NUM = args.start_num, args.end_num
    API_CONTROLLER = args.api_controller

    setup_logging(START_NUM, END_NUM, API_CONTROLLER)
    seed_addresses = ALL_SEED_ADDRESSES[START_NUM:END_NUM]

    Provider = TxListProvider(
        api_key=ETHERSCAN_API_KEYS[API_CONTROLLER % len(ETHERSCAN_API_KEYS)],
        endpoint=ENDPOINTS[API_CONTROLLER % len(ENDPOINTS)]
    )

    expand_clustering_task(
        seed_addresses=seed_addresses,
        provider=Provider,
        output_file=f'expanded_cluster_results_{str(START_NUM)}-{str(END_NUM)}.json',
        save_interval=10
    )