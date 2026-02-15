import pandas as pd
import os
import csv
import concurrent.futures
import math  # Added for total batch calculation
from rich.console import Console

# Import modules
from blocking import run_blocking
from selecting import Selecting
from filtering import ENSFilter, LabelFilter

# ================= Core Configuration =================
TASK_TYPE = "LABEL"
MODEL_NAME = "gpt-5-mini"
COST_LIMIT = 10000.0

# Path Settings
DIR_TMP = "./tmp_result"
DIR_HISTORY = "./llm_history"
DIR_RESULT = "./result"

# Algorithm Parameters
BLOCKING_MIN_SCORE = 6.0
BLOCKING_TOP_K = 20
ENS_FILTER_THRESH = 85
LABEL_FILTER_THRESH = 0.85

# LLM Batch Size
LLM_BATCH_SIZE = 100
FILTER_WORKERS = 10
# ====================================================

console = Console()


def setup_directories():
    for d in [DIR_TMP, DIR_HISTORY, DIR_RESULT]:
        if not os.path.exists(d): os.makedirs(d)


def run_filtering_single(args):
    """
    Run Filtering step only
    """
    instance, local_filter, filter_thresh = args
    anchor = instance['anchor']

    # Step 2: Filtering (Refined selection)
    filtered_candidates = local_filter.filter(
        instance, top_k=5, threshold=filter_thresh
    )

    if filtered_candidates:
        return {
            "anchor": anchor,
            "candidates": filtered_candidates,
            "original_candidates": instance["candidates"]
        }
    return None


def main():
    setup_directories()

    # Load Data
    if TASK_TYPE == "ENS":
        data_file = "clean_ens.csv"
        blocking_index = "ens_bm25_index"
    else:
        data_file = "clean_labels.csv"
        blocking_index = "label_bm25_index"

    try:
        df = pd.read_csv(data_file)
        df = df.dropna(subset=['clean_text'])
        all_unique_texts = df['clean_text'].unique().tolist()
        console.print(f"[green]Data loaded successfully: {len(df)} records[/]")
    except FileNotFoundError:
        console.print(f"[red]File not found {data_file}[/]")
        return

    # Initialize Filter
    console.print("[dim]Initializing Filter...[/]")
    # if TASK_TYPE == "ENS":
    #     local_filter = ENSFilter()
    #     filter_thresh = ENS_FILTER_THRESH
    # else:
    #     local_filter = LabelFilter(all_texts=all_unique_texts)
    #     filter_thresh = LABEL_FILTER_THRESH

    local_filter = LabelFilter(all_texts=all_unique_texts)
    filter_thresh = LABEL_FILTER_THRESH

    # Blocking
    console.print("[dim]Executing Blocking...[/]")
    blocked_data = run_blocking(
        df, top_k=BLOCKING_TOP_K, min_score=BLOCKING_MIN_SCORE, index_name=blocking_index
    )

    # Initialize LLM Selector
    llm_selector = Selecting(
        model_name=MODEL_NAME,
        log_file=os.path.join(DIR_HISTORY, f"llm_history_{TASK_TYPE}.jsonl"),
        task_type=TASK_TYPE
    )

    # Prepare Logs
    f_filter_log = open(os.path.join(DIR_TMP, f"filtering_passed_{TASK_TYPE}.csv"), 'w', newline='', encoding='utf-8')
    filter_writer = csv.writer(f_filter_log)
    filter_writer.writerow(["anchor", "candidates_after_filtering"])

    processed_entities = set()
    final_clusters = []

    total_items = len(blocked_data)
    # Calculate total batches (ceiling)
    total_batches = math.ceil(total_items / LLM_BATCH_SIZE)

    console.print(f"[yellow]Starting full pipeline processing[/]")
    console.print(f"Total Tasks: {total_items} | Batch Size: {LLM_BATCH_SIZE} | Total Batches: {total_batches}")
    console.print("=" * 50)

    # ================= Core Loop =================

    # Iterate with step size of LLM_BATCH_SIZE
    for i in range(0, total_items, LLM_BATCH_SIZE):

        # Progress printing logic
        current_batch_idx = (i // LLM_BATCH_SIZE) + 1
        progress_pct = (i / total_items) * 100
        remaining_items = total_items - i

        # Use rule to draw a divider
        console.rule(f"[bold blue]Batch {current_batch_idx}/{total_batches} ({progress_pct:.1f}%)")
        console.print(f"[dim]Scanned: {i} | Remaining: {remaining_items}[/]")
        # ---------------------------

        # A. Slice a batch of raw data
        batch_raw = blocked_data[i: i + LLM_BATCH_SIZE]

        # B. Preprocessing: Deduplication
        batch_to_filter = []
        for item in batch_raw:
            if item['anchor'] not in processed_entities:
                batch_to_filter.append(item)

        # Skip if all entities in this batch have been processed
        if not batch_to_filter:
            console.print("[dim]All entities in this batch processed, skipping...[/]")
            continue

        console.print(f"Step 1: Parallel Filtering ({len(batch_to_filter)} items)...")

        # C. Parallel Filtering
        llm_input_batch = []
        filter_args = [(item, local_filter, filter_thresh) for item in batch_to_filter]

        with concurrent.futures.ThreadPoolExecutor(max_workers=FILTER_WORKERS) as executor:
            results = executor.map(run_filtering_single, filter_args)

            for res in results:
                if res:  # If not filtered out
                    filter_writer.writerow([res['anchor'], " | ".join(res['candidates'])])
                    llm_input_batch.append({
                        "anchor": res['anchor'],
                        "candidates": res['candidates']
                    })

        # D. Batch LLM Call (Step 2)
        if llm_input_batch:
            console.print(f"[bold cyan]Step 2: Sending {len(llm_input_batch)} items to LLM...[/]")

            # Synchronous send of large batch
            batch_results = llm_selector.process_batch(llm_input_batch)

            # E. Process Results
            for res in batch_results:
                anchor = res['anchor']
                matches = res['matches']

                if matches:
                    cluster = list(dict.fromkeys([anchor] + matches))
                    final_clusters.append(cluster)

                    # Update processed set
                    processed_entities.add(anchor)
                    for m in matches:
                        processed_entities.add(m)

                    console.print(f"[green]Cluster Found:[/green] {cluster}")
        else:
            console.print("[dim]Step 2: No valid candidates, skipping LLM call[/]")

        # F. Flush logs & Check Budget
        f_filter_log.flush()
        if llm_selector.cost > COST_LIMIT:
            console.print(f"[red bold]Budget limit reached (${COST_LIMIT}), stopping![/]")
            break

    # ==============================================

    f_filter_log.close()

    # Save Results
    output_file = os.path.join(DIR_RESULT, f"results_{TASK_TYPE}.csv")
    pd.DataFrame({"cluster": [" | ".join(c) for c in final_clusters]}).to_csv(output_file, index=False)

    console.rule("[bold green]Task Complete[/]")
    console.print(f"Total Entities Processed: {len(processed_entities)}")
    console.print(f"Clusters Found: {len(final_clusters)}")
    console.print(f"Results saved: {output_file}")


if __name__ == "__main__":
    main()