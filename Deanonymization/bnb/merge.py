# 读取add.txt中的哈希值并保持顺序
with open('add.txt', 'r') as f:
    add_hashes = [line.strip() for line in f]

# 创建哈希集合用于快速查找，并初始化字典存储目标节点
add_set = set(add_hashes)
edges = {hash: [] for hash in add_hashes}

# 处理edge.txt文件
with open('edge.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        source, target = line.split(',', 1)  # 只分割一次
        if source in add_set:
            edges[source].append(target)

# 写入合并后的结果（保持add.txt原有顺序）
with open('merged.txt', 'w') as out:
    for hash in add_hashes:
        targets = edges[hash]
        if targets:
            out.write(f"{hash},{','.join(targets)}\n")
        else:
            out.write(f"{hash}\n")