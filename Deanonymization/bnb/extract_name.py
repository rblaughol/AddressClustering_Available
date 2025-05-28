import json
import os

# 读取eth_bak.json文件
with open('bnb.json', 'r') as f:
    data = json.load(f)

# 读取add.txt文件并处理每一行
with open('merged.txt', 'r') as f:
    addresses = f.readlines()

# 准备一个输出文件来存储找到的名称
with open('dep_name.txt', 'w') as f_output:
    total_lines = len(addresses)  # 总行数
    processed_count = 0  # 已处理的行数

    # 遍历每行地址
    for line in addresses:
        # 每行的地址通过逗号分隔
        addr_list = line.strip().split(',')

        # 遍历每个地址，检查它是否在JSON的key中
        for address in addr_list:
            address = "0x" + address
            # 如果地址在JSON中，获取对应的name并写入文件
            if address in data:
                f_output.write(data[address]["name"] + '\n')

        # 更新进度
        processed_count += 1
        progress = (processed_count / total_lines) * 100
        print(f"Processing... {processed_count}/{total_lines} lines processed. Progress: {progress:.2f}%")
    
print("处理完成，结果已实时写入 dep_name.txt")
