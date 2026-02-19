import time
from typing import List, Optional, Tuple, Dict
from multiprocessing import Pool
from web3 import Web3

# =========================
# 4 RPC endpoints (4 processes per RPC, total 16 processes)
# Keep the same RPC layout as your current code
# =========================
RPCS = [
    ("Account2", "..."),
    ("Account3", "..."),
    ("Account4", "..."),
    ("Account5", "..."),
]

PROCS_PER_RPC = 4
TOTAL_PROCS = PROCS_PER_RPC * len(RPCS)  # 16

# Retry and timeout settings
REQUEST_TIMEOUT = 20
MAX_RETRIES = 10
BASE_BACKOFF_SEC = 0.3

# Global variables for worker processes (set via initializer)
_G_RPC_NAME = None
_G_RPC_URL = None


def _init_worker(rpc_name: str, rpc_url: str):
    """Initialize each worker process with a fixed RPC endpoint."""
    global _G_RPC_NAME, _G_RPC_URL
    _G_RPC_NAME = rpc_name
    _G_RPC_URL = rpc_url
    print(f"[WORKER INIT] Process started for RPC: {_G_RPC_NAME}")


def _create_w3_instance() -> Web3:
    """Create a Web3 instance inside each worker process."""
    return Web3(Web3.HTTPProvider(_G_RPC_URL, request_kwargs={"timeout": REQUEST_TIMEOUT}))


def normalize_ens(name: str) -> str:
    """Normalize token to ENS name (append .eth if missing)."""
    n = name.strip()
    if not n:
        return n
    if "." not in n:
        n = f"{n}.eth"
    return n


def is_eth_address(x: str) -> bool:
    """Check whether x looks like an Ethereum address (0x + 40 hex)."""
    s = x.strip()
    if not (s.startswith("0x") and len(s) == 42):
        return False
    try:
        int(s[2:], 16)
        return True
    except Exception:
        return False


def ens_to_address(token: str) -> Optional[str]:
    """Resolve ENS name to Ethereum address using the worker's assigned RPC."""
    ens_name = normalize_ens(token)
    if not ens_name:
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            w3 = _create_w3_instance()
            addr = w3.ens.address(ens_name)  # returns checksum address or None
            if addr:
                print(f"[SUCCESS] {_G_RPC_NAME} resolved {ens_name} -> {addr}")
                return Web3.to_checksum_address(addr)
            print(f"[MISS] {_G_RPC_NAME} no record for {ens_name}")
            return None
        except Exception as e:
            wait = BASE_BACKOFF_SEC * (2 ** (attempt - 1))
            print(
                f"[WARN] {_G_RPC_NAME} failed to resolve {ens_name} "
                f"(attempt {attempt}/{MAX_RETRIES}), error={e}, retrying in {wait:.1f}s"
            )
            time.sleep(wait)

    print(f"[ERROR] {_G_RPC_NAME} exhausted retries for {ens_name}")
    return None


def retry_one_line(task: Tuple[int, str]) -> Tuple[int, str, int, int]:
    """
    Worker function: retry tokens in ONE line from ens_entity.txt.
    Rule:
    - If token is already a valid 0x address: keep it
    - Otherwise: try ENS resolution again; if resolved -> replace, else keep original token
    Returns: (line_no, new_line_str, replaced_count, total_to_retry)
    """
    line_no, raw_line = task
    print(f"[WORKER] {_G_RPC_NAME} retrying line {line_no}")

    raw = raw_line.strip()
    if not raw:
        return line_no, "", 0, 0

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    new_tokens: List[str] = []

    replaced = 0
    to_retry = 0

    for tok in tokens:
        if is_eth_address(tok):
            new_tokens.append(tok)
            continue

        # Not an address -> retry
        to_retry += 1
        addr = ens_to_address(tok)
        if addr:
            new_tokens.append(addr)
            replaced += 1
        else:
            new_tokens.append(tok)

    new_line = ",".join(new_tokens)
    print(f"[WORKER] {_G_RPC_NAME} finished line {line_no} (replaced {replaced}/{to_retry})")
    return line_no, new_line, replaced, to_retry


def pick_pool_index(line_no: int) -> int:
    """Distribute lines evenly across 4 pools."""
    return (line_no - 1) % 4


def retry_from_existing_file(input_path: str, output_path: str):
    """
    Main controller:
    - Read existing ens_entity.txt
    - Find tokens that are NOT 0x addresses, retry resolving them
    - Write updated file in order (flush per line)
    Note:
    - Output file will contain the same number of lines as input file
    """
    # Load all lines
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    print("=================================================")
    print(f"[INFO] Input file: {input_path}")
    print(f"[INFO] Total lines: {total_lines}")
    print(f"[INFO] Total processes: {TOTAL_PROCS} ({PROCS_PER_RPC} per RPC)")
    print("=================================================")

    # Create tasks for all lines (you can change to partial segment if needed)
    tasks: List[Tuple[int, str]] = [(i + 1, lines[i]) for i in range(total_lines)]

    # Create 4 pools (one per RPC)
    pools: List[Pool] = []
    for rpc_name, rpc_url in RPCS:
        print(f"[INFO] Starting pool for {rpc_name}")
        p = Pool(processes=PROCS_PER_RPC, initializer=_init_worker, initargs=(rpc_name, rpc_url))
        pools.append(p)

    pending: Dict[int, Tuple[str, int, int]] = {}  # line_no -> (line_str, replaced, to_retry)
    next_to_write = 1
    submitted = 0
    completed = 0
    total_replaced = 0
    total_to_retry = 0

    def _on_result(res: Tuple[int, str, int, int]):
        nonlocal next_to_write, completed, total_replaced, total_to_retry
        line_no, new_line, replaced, to_retry = res
        pending[line_no] = (new_line, replaced, to_retry)
        completed += 1
        total_replaced += replaced
        total_to_retry += to_retry

        print(
            f"[MAIN] Line {line_no} completed ({completed}/{total_lines}) | "
            f"line_replaced={replaced}/{to_retry} | total_replaced={total_replaced}/{total_to_retry}"
        )

        # Write in order
        while next_to_write in pending:
            out_line, rep, tr = pending.pop(next_to_write)
            fout.write(out_line + "\n")
            fout.flush()
            print(f"[MAIN] Line {next_to_write} written to output")
            next_to_write += 1

    def _on_error(err: BaseException):
        print(f"[ERROR] Worker task failed: {err}")

    try:
        with open(output_path, "w", encoding="utf-8") as fout:
            # Dispatch tasks
            for (line_no, line) in tasks:
                idx = pick_pool_index(line_no)
                rpc_name = RPCS[idx][0]
                submitted += 1
                if submitted % 200 == 0 or submitted == 1:
                    print(f"[MAIN] Submitted {submitted}/{total_lines} tasks...")

                pools[idx].apply_async(
                    retry_one_line,
                    args=((line_no, line),),
                    callback=_on_result,
                    error_callback=_on_error,
                )

            # Close and wait
            for p in pools:
                p.close()
            for p in pools:
                p.join()

            # Defensive write for remaining
            for ln in range(next_to_write, total_lines + 1):
                if ln in pending:
                    out_line, _, _ = pending[ln]
                    fout.write(out_line + "\n")
                    fout.flush()

        print("=================================================")
        print("[DONE] Retry pass finished.")
        print(f"[DONE] Output written to: {output_path}")
        print(f"[DONE] Total replaced this pass: {total_replaced}/{total_to_retry}")
        print("=================================================")

    finally:
        for p in pools:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    # Existing file you already generated
    INPUT_FILE = "ens_entity.txt"

    # Write a new file after retry (safer than overwriting)
    OUTPUT_FILE = "ens_entity_retry.txt"

    retry_from_existing_file(INPUT_FILE, OUTPUT_FILE)
