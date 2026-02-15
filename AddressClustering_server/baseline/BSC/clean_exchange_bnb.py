import re
import csv

def process_csv(input_file, output_file):
    address_pattern = re.compile(r'\b[0-9a-fA-F]{40}\b')
    
    processed_data = []
    
    with open(input_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
                
            for cell in row:
                for match in address_pattern.finditer(cell):
                    address = match.group().lower()
                    
                    if not any(address in item for item in processed_data):

                        processed_data.append([
                            address,
                            '',
                            'eoa',
                            'Exchange'
                        ])
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(processed_data)
    


input_file = 'exchange_bnb.csv'
output_file = 'exchanges_bnb.csv'
process_csv(input_file, output_file)
