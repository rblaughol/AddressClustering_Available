import math
import time
from typing import List, Optional, Tuple, Dict
from multiprocessing import Pool
from web3 import Web3

# =========================
# 4 RPC endpoints (4 processes per RPC, total 16 processes)
# =========================
RPCS = [
    ("zzy Account2", "https://mainnet.chainnodes.org/dfcb4040-9ac1-49cf-8557-94016a639bd1"),
    ("De1 Account3", "https://mainnet.chainnodes.org/57c9aae1-4f27-4b3f-83d6-f851493c11e0"),
    ("yrb Account4", "https://mainnet.chainnodes.org/35b59fa9-5f5f-47a3-91e9-67c2852aed25"),
    ("De2 Account5", "https://mainnet.chainnodes.org/cede21a1-0e54-4ea8-bb51-042dfbd8ff7c"),
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


def process_one_line(task: Tuple[int, str]) -> Tuple[int, str]:
    """
    Worker function: process ONE line.
    - Replace tokens with addresses if resolved
    - Keep original token if resolution fails
    Returns: (line_no, resolved_line_str)
    """
    line_no, raw_line = task
    print(f"[WORKER] {_G_RPC_NAME} processing line {line_no}")

    raw = raw_line.strip()
    if not raw:
        print(f"[WORKER] {_G_RPC_NAME} empty line {line_no}")
        return line_no, ""

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    resolved: List[str] = []

    for tok in tokens:
        addr = ens_to_address(tok)
        resolved.append(addr if addr else tok)

    result_line = ",".join(resolved)
    print(f"[WORKER] {_G_RPC_NAME} finished line {line_no}")
    return line_no, result_line


def count_lines(path: str) -> int:
    """Count total number of lines in the input file."""
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for _ in f:
            n += 1
    return n


def quarter_range(total_lines: int) -> Tuple[int, int]:
    """
    Define processing range from 1/4 to 2/4 of the file (1-indexed, inclusive):
    start = floor(total/4) + 1
    end   = floor(total/2)
    """
    start = total_lines // 4 + 1
    end = total_lines // 2
    if end < start:
        end = start
    return start, end


def pick_pool_index(line_no: int) -> int:
    """Distribute lines evenly across 4 pools."""
    return (line_no - 1) % 4


def process_quarter_segment_multproc(input_path: str, output_path: str):
    """Main controller: distribute lines to 4 pools and write results in order."""
    total = count_lines(input_path)
    start, end = quarter_range(total)

    print("=================================================")
    print(f"[INFO] Total lines in file: {total}")
    print(f"[INFO] Processing range: lines {start} to {end} (1/4 to 2/4)")
    print(f"[INFO] Total processes: {TOTAL_PROCS} ({PROCS_PER_RPC} per RPC)")
    print("=================================================")

    # Read only the target segment into tasks
    tasks: List[Tuple[int, str]] = []
    with open(input_path, "r", encoding="utf-8") as fin:
        for line_no, line in enumerate(fin, start=1):
            if line_no < start:
                continue
            if line_no > end:
                break
            tasks.append((line_no, line))

    print(f"[INFO] Total tasks to process: {len(tasks)}")

    # Create 4 pools (one per RPC)
    pools: List[Pool] = []
    for rpc_name, rpc_url in RPCS:
        print(f"[INFO] Starting pool for {rpc_name}")
        p = Pool(processes=PROCS_PER_RPC,
                 initializer=_init_worker,
                 initargs=(rpc_name, rpc_url))
        pools.append(p)

    pending: Dict[int, str] = {}
    next_to_write = start
    submitted = 0
    completed = 0

    def _on_result(res: Tuple[int, str]):
        nonlocal next_to_write, completed
        line_no, resolved_line = res
        pending[line_no] = resolved_line
        completed += 1

        print(f"[MAIN] Line {line_no} completed ({completed}/{len(tasks)})")

        # Write results in order if possible
        while next_to_write in pending:
            fout.write(pending.pop(next_to_write) + "\n")
            fout.flush()
            print(f"[MAIN] Line {next_to_write} written to file")
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
                print(f"[MAIN] Submitting line {line_no} to Pool#{idx} ({rpc_name}) "
                      f"[{submitted}/{len(tasks)}]")

                pools[idx].apply_async(
                    process_one_line,
                    args=((line_no, line),),
                    callback=_on_result,
                    error_callback=_on_error,
                )

            # Close submission and wait
            for p in pools:
                p.close()
            for p in pools:
                p.join()

            # Defensive write for any remaining pending lines
            for ln in range(next_to_write, end + 1):
                if ln in pending:
                    fout.write(pending[ln] + "\n")
                    fout.flush()

        print("=================================================")
        print(f"[DONE] Processing finished.")
        print(f"[DONE] Output written to: {output_path}")
        print("=================================================")

    finally:
        for p in pools:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    INPUT_FILE = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/ENS/Entity-LLM/final_entities_reviewed.txt"
    OUTPUT_FILE = "ens_entity.txt"
    process_quarter_segment_multproc(INPUT_FILE, OUTPUT_FILE)
