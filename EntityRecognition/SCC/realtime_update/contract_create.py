import requests
import os
import multiprocessing

################################
# 0. Block range configuration
################################
start_block = 19000001
end_block = 20000000

################################
# 1. File paths
################################
CONF_PATH = "../../env.conf"
OUTPUT_FILE = "output.txt"
RECORD_FILE = "record.txt"

proxies = {
    "http": "http://127.0.0.1:10809", 
    "https": "http://127.0.0.1:10809",
}

################################
# 2. Load configuration
################################
def load_conf(conf_path):
    """
    Load python-style config file.
    Example:
        chainnode_url = "..."
    """
    conf = {}
    with open(conf_path, "r") as f:
        exec(f.read(), conf)
    return conf

conf = load_conf(CONF_PATH)
URL = conf["chainnode_url"]

################################
# 3. Load processed blocks (checkpoint)
################################
def load_record(record_file):
    """
    Load already processed block numbers from record file.
    """
    processed = set()

    if not os.path.exists(record_file):
        return processed

    with open(record_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                processed.add(int(line))

    return processed

################################
# 4. Extract create traces
################################
def extract_create_traces(trace_list):
    """
    Extract (creator, contract_address) from trace_block result.
    """
    creates = []

    for trace in trace_list:
        if not isinstance(trace, dict):
            continue

        if trace.get("type") != "create":
            continue

        action = trace.get("action", {})
        result = trace.get("result", {})

        creator = action.get("from")
        contract = result.get("address")

        if creator and contract:
            creates.append((creator, contract))

    return creates

################################
# 5. trace_block worker
################################
def trace_block(args):
    block_number, output_lock, record_lock = args

    payload = {
        "jsonrpc": "2.0",
        "method": "trace_block",
        "params": [hex(block_number)],
        "id": block_number
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(URL, json=payload, headers=headers, timeout=30, proxies=proxies)
        response.raise_for_status()
        data = response.json()

        trace_list = data.get("result", [])
        creates = extract_create_traces(trace_list)

        # Write create results
        if creates:
            with output_lock:
                with open(OUTPUT_FILE, "a") as f:
                    for creator, contract in creates:
                        f.write(f"{creator},{contract}\n")
                    f.flush()

        # Record processed block (checkpoint)
        with record_lock:
            with open(RECORD_FILE, "a") as f:
                f.write(f"{block_number}\n")
                f.flush()

        print(f"[OK] block {block_number}, create traces: {len(creates)}")
        return True

    except Exception as e:
        print(f"[ERROR] block {block_number}: {e}")
        return False

################################
# 6. Main entry (multiprocessing)
################################
if __name__ == "__main__":

    manager = multiprocessing.Manager()
    output_lock = manager.Lock()
    record_lock = manager.Lock()

    # Load checkpoint
    processed_blocks = load_record(RECORD_FILE)
    print(f"Loaded {len(processed_blocks)} processed blocks from record.txt")

    # Build task list (skip processed blocks)
    tasks = [
        (i, output_lock, record_lock)
        for i in range(start_block, end_block + 1)
        if i not in processed_blocks
    ]

    cpu_count = os.cpu_count()
    process_num = 8

    print(f"Total CPU cores: {cpu_count}, using processes: {process_num}")
    print(f"Blocks to process: {len(tasks)}")

    with multiprocessing.Pool(processes=process_num) as pool:
        results = pool.map(trace_block, tasks)

    success_count = sum(results)
    print(f"Finished. Success blocks: {success_count}/{len(tasks)}")
