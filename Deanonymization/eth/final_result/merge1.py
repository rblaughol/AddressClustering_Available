try:
    # 读取 ens.txt 文件，提取需要合并的行号
    with open('ens.txt', 'r') as ens_file:
        line_numbers = []
        for line in ens_file:
            parts = line.strip().split(',')
            line_num = int(parts[0]) - 1
            line_numbers.append(line_num)

    # 打开 data.txt 读取内容，打开 merged_data.txt 写入合并后的内容
    with open('add.txt', 'r') as data_file, open('merged_data.txt', 'w') as output_file:
        all_lines = data_file.readlines()
        merged_content = []
        for line_num in sorted(line_numbers):
            if 0 <= line_num < len(all_lines):
                parts = all_lines[line_num].strip().split(',')
                merged_content.extend(parts)

        # 去除合并内容中的重复项
        unique_merged_content = list(dict.fromkeys(merged_content))
        merged_line = ','.join(unique_merged_content)

        # 标记已经处理过的行
        processed_lines = set(line_numbers)

        for i, line in enumerate(all_lines):
            if i in processed_lines:
                if i == min(line_numbers):
                    # 在最小行号处写入合并后的行
                    output_file.write(merged_line + '\n')
            else:
                # 其他行直接写入
                output_file.write(line)

except FileNotFoundError as e:
    print(f"未找到文件: {e.filename}")