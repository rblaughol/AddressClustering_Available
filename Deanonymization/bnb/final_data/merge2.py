import json

# 读取 merged_data.txt 文件
with open('merged_data.txt', 'r') as f:
    merged_lines = [line.strip().split(',') for line in f.readlines()]
    # 为 merged_data.txt 中的地址添加 0x 前缀
    merged_lines = [['0x' + addr if not addr.startswith('0x') else addr for addr in line] for line in merged_lines]

# 读取 eth_bak.json 文件
with open('bnb.json', 'r') as f:
    eth_bak = json.load(f)

# 读取 result3.txt 文件
with open('result3.txt', 'r') as f:
    result3 = json.load(f)

# 创建一个映射，将 name 映射到地址
name_to_address = {info["name"]: address for address, info in eth_bak.items() if info["name"]}

# 遍历 result3 中的每个标签和对应的 name 列表
for name_list in result3.values():
    # 找到每个 name 对应的地址
    addresses = []
    for name in name_list:
        if name in name_to_address:
            addresses.append(name_to_address[name])

    if not addresses:
        continue

    # 用于标记哪些行需要合并
    rows_to_merge = []
    for i, line in enumerate(merged_lines):
        for addr in addresses:
            if addr in line:
                rows_to_merge.append(i)
                break

    print(f"当前处理的地址列表: {addresses}")
    print(f"需要合并的行索引: {rows_to_merge}")

    if len(rows_to_merge) > 1:
        # 合并这些行
        merged_line = []
        for row_index in rows_to_merge:
            merged_line.extend(merged_lines[row_index])

        # 去重
        merged_line = list(set(merged_line))

        # 移除原来的行，从后往前删，避免索引混乱
        for row_index in sorted(rows_to_merge, reverse=True):
            del merged_lines[row_index]

        # 添加合并后的行
        merged_lines.append(merged_line)

# 将合并后的结果写入新文件，去除地址的 0x 前缀（如果需要）
with open('merged_result.txt', 'w') as f:
    for line in merged_lines:
        line_without_0x = [addr[2:] if addr.startswith('0x') else addr for addr in line]
        f.write(','.join(line_without_0x) + '\n')