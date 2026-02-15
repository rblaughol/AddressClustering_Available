import pandas as pd
import random

def sample_addresses_from_top_entities(input_file, output_file, top_k=20):
    """
    This function identifies the top-K largest entities based on the number of
    associated addresses (group_size). For each selected entity, it randomly
    samples one address from the corresponding address set.

    Parameters:
        input_file (str): Path to the input CSV file containing entity clusters.
                          The file is expected to contain two columns:
                          (1) merged_group: comma-separated address hashes
                          (2) group_size: number of addresses in the entity
        output_file (str): Path to the output file for saving sampled addresses.
        top_k (int): Number of largest entities to consider.
    """

    print(f"Reading input file: {input_file}")

    try:
        df = pd.read_csv(input_file, header=0,
                         names=["merged_group", "group_size"])
    except Exception as e:
        print(f"Failed to read input file: {str(e)}")
        return

    # Sort entities by size in descending order and select top-K
    top_entities = df.sort_values(
        by="group_size", ascending=False
    ).head(top_k)

    sampled_results = []

    for idx, row in top_entities.iterrows():
        merged_group = row["merged_group"]
        group_size = int(row["group_size"])

        # Split the entity into individual addresses
        addresses = merged_group.split(",")

        # Randomly sample one address from the entity
        sampled_address = random.choice(addresses)

        sampled_results.append({
            "entity_size": group_size,
            "sampled_address": sampled_address
        })

        print(
            f"Entity size = {group_size}, "
            f"Sampled address = {sampled_address}"
        )

    # Save results
    with open(output_file, "w") as f:
        f.write("entity_rank,entity_size,sampled_address\n")
        for rank, item in enumerate(sampled_results, start=1):
            f.write(
                f"{rank},{item['entity_size']},{item['sampled_address']}\n"
            )

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    input_file = (
        "/public/home/blockchain_2/slave2/deanonymization/"
        "EntityRecognition/SCC/analysis/entity_cc.csv"
    )
    output_file = (
        "/public/home/blockchain_2/slave2/deanonymization/"
        "EntityRecognition/SCC/analysis/"
        "random_addresses_from_top10_entities.csv"
    )

    sample_addresses_from_top_entities(
        input_file=input_file,
        output_file=output_file,
        top_k=20
    )

    print("\nDone.")
