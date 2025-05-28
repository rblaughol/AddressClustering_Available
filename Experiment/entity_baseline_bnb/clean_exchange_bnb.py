import re
import csv

def process_csv(input_file, output_file):
    # 正则表达式匹配40字符的十六进制地址
    address_pattern = re.compile(r'\b[0-9a-fA-F]{40}\b')
    
    # 存储处理后的数据
    processed_data = []
    
    with open(input_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            # 跳过空行
            if not row:
                continue
                
            # 在每一行中查找所有40位地址
            for cell in row:
                for match in address_pattern.finditer(cell):
                    address = match.group().lower()  # 转换为小写
                    
                    # 检查地址是否已经处理过
                    if not any(address in item for item in processed_data):
                        # 创建新记录，其他字段留空
                        processed_data.append([
                            address,  # 地址
                            '',       # 名称标签（留空）
                            'eoa',    # 固定值
                            'Exchange' # 固定值
                        ])
    
    # 写入输出文件
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(processed_data)
    
    print(f"处理完成，共找到 {len(processed_data)} 个地址，已保存到 {output_file}")

# 使用示例
input_file = 'exchange_bnb.csv'  # 替换为你的输入文件路径
output_file = 'exchanges_bnb.csv'  # 输出文件路径
process_csv(input_file, output_file)