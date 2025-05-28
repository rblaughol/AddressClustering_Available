try:
    # 读取 ens.txt 文件，提取需要合并的行号和数据
    line_numbers_groups = []
    with open('merged_bnb_ens.txt', 'r') as ens_file:
        for line in ens_file:
            parts = line.strip().split(',')
            line_numbers = [int(parts[i]) - 1 for i in range(0, len(parts), 2)]
            line_numbers_groups.append(line_numbers)

    # 打开 data.txt 读取内容，打开 merged_data.txt 写入合并后的内容
    with open('merged.txt', 'r') as data_file, open('merged_data.txt', 'w') as output_file:
        all_lines = data_file.readlines()
        processed_lines = set()

        for line_numbers in line_numbers_groups:
            merged_content = []
            for line_num in line_numbers:
                if 0 <= line_num < len(all_lines):
                    parts = all_lines[line_num].strip().split(',')
                    # 去除域名部分
                    numbers = [part for i, part in enumerate(parts) if i % 2 == 0]
                    merged_content.extend(numbers)
                    processed_lines.add(line_num)

            # 去除合并内容中的重复项
            unique_merged_content = list(dict.fromkeys(merged_content))
            merged_line = ','.join(unique_merged_content)

            if line_numbers:
                min_line_num = min(line_numbers)
                if min_line_num in range(len(all_lines)):
                    # 在最小行号处写入合并后的行
                    output_file.write(merged_line + '\n')

        for i, line in enumerate(all_lines):
            if i not in processed_lines:
                # 其他行直接写入
                output_file.write(line)

except FileNotFoundError as e:
    print(f"未找到文件: {e.filename}")