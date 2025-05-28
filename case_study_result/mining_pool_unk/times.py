from collections import Counter

def count_string_occurrences(filename):
    # 初始化计数器
    counter = Counter()
    
    # 读取文件并统计
    with open(filename, 'r') as file:
        for line in file:
            # 去除换行符和空白，分割字符串
            strings = line.strip().split(',')
            # 过滤空字符串并更新计数器
            counter.update([s for s in strings if s])
    
    # 生成排序后的结果（按出现次数降序，次数相同按字母升序）
    sorted_results = sorted(
        counter.items(),
        key=lambda x: (-x[1], x[0])
    )
    
    # 将结果写入文件
    with open('times.txt', 'w') as f:
        for string, count in sorted_results:
            f.write(f"{string}: {count}\n")
    
    # 同时打印结果到控制台
    print("结果已保存到txt")
    print("统计结果：")
    for string, count in sorted_results:
        print(f"{string}: {count}")

# 使用示例
count_string_occurrences('clustering.txt')