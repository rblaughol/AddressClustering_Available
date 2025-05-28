# 打开输入文件和输出文件
with open('merged_result.txt', 'r') as infile, open('final_result.txt', 'w') as outfile:
    # 逐行读取输入文件
    for line in infile:
        # 检查行中是否包含逗号
        if ',' in line:
            # 如果包含逗号，则写入输出文件
            outfile.write(line)