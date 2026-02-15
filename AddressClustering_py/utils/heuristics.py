from .config import *
from datetime import datetime

# ==========================================
# SG1: Multi-Sender Heuristic
# ==========================================

def apply_sg1_heuristic(node, tx_list, provider, processed_nodes):
    """Apply SG1 heuristic (Deposit Address Clustering) - Combining two perspectives"""
    all_groups = set()

    # Detect from initial address perspective
    init_groups = apply_sg1_heuristic_init(node, tx_list, provider, processed_nodes)
    all_groups.update(init_groups)

    # Detect from deposit address perspective
    deposit_groups = apply_sg1_heuristic_deposit(node, tx_list, provider, processed_nodes)
    all_groups.update(deposit_groups)

    return all_groups


def apply_sg1_heuristic_deposit(node, tx_list, provider, processed_nodes):
    """Apply SG1 heuristic - Deposit address perspective (Current node is intermediary/Deposit)"""
    groups = set()
    in_txs = [tx for tx in tx_list if tx['target'] == node]
    out_txs = [tx for tx in tx_list if tx['source'] == node]

    in_txs.sort(key=lambda x: int(x['block']))
    out_txs.sort(key=lambda x: int(x['block']))

    in_block_map = {}
    for tx in in_txs:
        if provider.timeout_controller.is_timeout(): break
        in_block_map.setdefault(int(tx['block']), []).append(tx)

    for i in range(len(out_txs) - 1):
        if provider.timeout_controller.is_timeout(): break
        out_tx = out_txs[i]
        out_amount = float(out_tx['amount'])
        block_num = int(out_tx['block'])

        prev_in_txs = [tx for blk, txs in in_block_map.items() if blk < block_num for tx in txs]
        in_amount = sum(float(tx['amount']) for tx in prev_in_txs)
        in_sources = {tx['source'] for tx in prev_in_txs}

        # Adopt directly if conditions are met, no prediction needed
        if len(in_sources) >= MIN_GROUP_SIZE and meets_sg1_condition(in_amount, out_amount):
            groups.update(in_sources)
            
    return groups


def apply_sg1_heuristic_init(node, tx_list, provider, processed_nodes):
    """Apply SG1 heuristic - Initial address perspective (Current node is source/Seed)"""
    groups = set()
    deposit_addresses = {tx['target'] for tx in tx_list if tx['source'] == node and tx['amount'] != '0'}

    for deposit in deposit_addresses:
        if provider.timeout_controller.is_timeout(): break

        try:
            deposit_txs_all = provider.get_addr_tx_list(deposit, get_create=False)
            in_txs = [tx for tx in deposit_txs_all if tx['target'] == deposit and tx['amount'] != '0']
            out_txs = [tx for tx in deposit_txs_all if tx['source'] == deposit and tx['amount'] != '0']
        except:
            continue

        in_txs.sort(key=lambda x: int(x['block']))
        out_txs.sort(key=lambda x: int(x['block']))

        in_block_map = {}
        for tx in in_txs:
            in_block_map.setdefault(int(tx['block']), []).append(tx)

        balance = 0.0
        for out_tx in out_txs:
            if provider.timeout_controller.is_timeout(): break
            current_upper = int(out_tx['block'])
            out_amount = float(out_tx['amount'])

            relevant_in_txs = []
            for block_num, txs in in_block_map.items():
                if block_num < current_upper:
                    relevant_in_txs.extend(txs)

            in_amount = 0.0
            in_sources = set()
            for tx in relevant_in_txs:
                in_amount += float(tx['amount'])
                in_sources.add(tx['source'])

            balance_before = balance
            balance = max(0, balance_before + in_amount - out_amount)

            if node in in_sources:
                if meets_sg1_condition(in_amount, out_amount) or meets_sg1_condition(in_amount + balance_before, out_amount):
                    # Adopt directly if conditions are met
                    if len(in_sources) >= MIN_GROUP_SIZE:
                        groups.update(in_sources)
    return groups


def meets_sg1_condition(in_amount: float, out_amount: float) -> bool:
    diff = abs(in_amount - out_amount)
    min_val = min(in_amount, out_amount)
    if diff == 0: return True
    return min_val >= diff * DYNAMIC_THRESHOLD


# ==========================================
# SG2: Multi-Deposit Heuristic
# ==========================================

def apply_sg2_heuristic(node, tx_list, provider, processed_nodes):
    """
    Corresponds to Multi-Deposit Heuristic
    Goal: Identify Deposit address clusters acting as intermediaries
    """
    groups = set()

    # Perspective 1: Sender perspective
    groups.update(apply_multi_deposit_as_sender(node, tx_list, provider, processed_nodes))

    # Perspective 2: Deposit address perspective
    groups.update(apply_multi_deposit_as_deposit(node, tx_list, provider, processed_nodes))

    return groups


def apply_multi_deposit_as_sender(sender_node, tx_list, provider, processed_nodes):
    """Perspective 1: Current node is Sender. Look for downstream Deposit sets and common Receiver."""
    groups = set()

    # Get all potential Deposit addresses (transfer targets of current node)
    potential_deposits = set()
    for tx in tx_list:
        if tx['source'] == sender_node and float(tx['amount']) > 0 and tx['trace_type'] != 'create':
            potential_deposits.add(tx['target'])

    # receiver -> list of [deposit_address]
    receiver_map = {}

    for deposit_addr in potential_deposits:
        if provider.timeout_controller.is_timeout(): break
        if deposit_addr in processed_nodes: continue

        try:
            deposit_txs = provider.get_addr_tx_list(deposit_addr, get_create=False)
            # Check: Sender(Me) -> Deposit -> Some_Receiver
            forward_info = find_forwarding_path(deposit_addr, deposit_txs, specific_sender=sender_node)

            if forward_info:
                receiver = forward_info['receiver']
                if receiver not in receiver_map:
                    receiver_map[receiver] = []
                receiver_map[receiver].append(deposit_addr)
        except Exception as e:
            continue

    # Clustering determination
    for receiver, deposits in receiver_map.items():
        # Adopt all deposits if count is sufficient
        if len(deposits) >= MIN_GROUP_SIZE:
            print(f"[SG2-Sender] Found Sender({sender_node}) -> Deposits({len(deposits)}) -> Receiver({receiver})")
            groups.update(deposits)

    return groups


def apply_multi_deposit_as_deposit(deposit_node, tx_list, provider, processed_nodes):
    """
    Perspective 2: Current node is Deposit.
    """
    groups = set()

    # Find all (Sender, Receiver) forwarding pairs in own transactions
    forwarding_pairs = find_all_forwarding_pairs(deposit_node, tx_list)

    for sender, receiver in forwarding_pairs:
        if provider.timeout_controller.is_timeout(): break

        # Get Sender's transaction list (look for potential siblings)
        try:
            sender_txs = provider.get_addr_tx_list(sender, get_create=False)
        except:
            continue

        # Find all transfer targets of Sender (excluding self)
        potential_siblings = set()
        for tx in sender_txs:
            if tx['source'] == sender and tx['target'] != deposit_node and float(tx['amount']) > 0:
                potential_siblings.add(tx['target'])

        # Verify if potential siblings also transferred to the same Receiver
        verified_siblings = set()

        for sibling in potential_siblings:
            if provider.timeout_controller.is_timeout(): break
            if sibling in processed_nodes: continue

            try:
                # Check sibling's ledger to confirm Sibling -> R
                sibling_txs = provider.get_addr_tx_list(sibling, get_create=False)

                # Check: S -> Sibling -> R
                forward_info = find_forwarding_path(sibling, sibling_txs, specific_sender=sender,
                                                    specific_receiver=receiver)

                if forward_info:
                    # Adopt as cluster member if path exists
                    verified_siblings.add(sibling)

            except:
                continue

        # If found siblings plus self meet minimum cluster size
        if len(verified_siblings) + 1 >= MIN_GROUP_SIZE:
            print(f"[SG2-Deposit] Found from Deposit({deposit_node}) Siblings -> Sender({sender}) -> Siblings({len(verified_siblings)}) -> Receiver({receiver})")
            groups.update(verified_siblings)

    return groups


def find_forwarding_path(deposit_addr, tx_list, specific_sender=None, specific_receiver=None):
    """Find the first forwarding path meeting conditions"""
    tx_list_sorted = sorted(tx_list, key=lambda x: int(x['block']))

    for i in range(len(tx_list_sorted) - 1):
        tx1 = tx_list_sorted[i]
        tx2 = tx_list_sorted[i + 1]

        # Structure and target constraints
        if tx1['target'] != deposit_addr or tx2['source'] != deposit_addr: continue
        if specific_sender and tx1['source'] != specific_sender: continue
        if specific_receiver and tx2['target'] != specific_receiver: continue

        # Time and amount constraints
        if int(tx1['block']) > int(tx2['block']): continue
        if meets_sg2_condition(float(tx1['amount']), float(tx2['amount'])):
            return {'sender': tx1['source'], 'receiver': tx2['target']}
    return None


def find_all_forwarding_pairs(deposit_addr, tx_list):
    """Find all valid (Sender, Receiver) pairs"""
    pairs = set()
    tx_list_sorted = sorted(tx_list, key=lambda x: int(x['block']))

    for i in range(len(tx_list_sorted) - 1):
        tx1 = tx_list_sorted[i]
        tx2 = tx_list_sorted[i + 1]

        if tx1['target'] != deposit_addr or tx2['source'] != deposit_addr: continue
        if int(tx1['block']) > int(tx2['block']): continue

        if meets_sg2_condition(float(tx1['amount']), float(tx2['amount'])):
            pairs.add((tx1['source'], tx2['target']))

    return list(pairs)


def meets_sg2_condition(in_amount: float, out_amount: float) -> bool:
    """Verify Multi-Deposit amount conditions"""
    diff = abs(in_amount - out_amount)
    min_val = min(in_amount, out_amount)
    if diff == 0: return True
    return min_val >= diff * DYNAMIC_THRESHOLD