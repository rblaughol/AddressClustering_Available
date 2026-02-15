import os

clustering_path = "/public/home/blockchain_2/slave2/deanonymization/entity/case_Indiv6.txt"
entity_path = '/public/home/blockchain_2/slave2/deanonymization/eth_entity.txt'

def read_addresses(file_path):
    addresses = set()
    with open(file_path, 'r') as file:
        for line in file:
            addrs = line.strip().split(',')
            addresses.update(addrs)
    return addresses

def find_related_addresses(search_addrs, group_file_path):
    related_addrs = set()
    with open(group_file_path, 'r') as file:
        for line in file:
            addrs_in_group = set(line.strip().split(','))
            if search_addrs & addrs_in_group:
                related_addrs.update(addrs_in_group - search_addrs)
    return related_addrs

def main():
    base_name = os.path.splitext(clustering_path)[0]
    output_path = f"{base_name}.final"
    
    search_addresses = read_addresses(clustering_path)
    related_addresses = find_related_addresses(search_addresses, entity_path)
    final_addresses = search_addresses.union(related_addresses)

    with open(output_path, 'w') as file:
        sorted_addresses = sorted(final_addresses)
        file.write(','.join(sorted_addresses))
    

if __name__ == "__main__":
    main()