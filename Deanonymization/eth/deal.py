# 用于存储满足条件的域名分组信息
domain_groups = {}

# 打开文件并逐行读取，指定编码为 utf-8
with open('ens_merge.txt', 'r', encoding='utf-8') as file:
    for line in file:
        # 分割每行数据为编号和域名
        number, domain = line.strip().split(',')
        # 去掉域名的 .bnb 后缀
        domain_without_suffix = domain.replace('.ens', '')

        # 仅处理长度大于 4 的域名
        if len(domain_without_suffix) > 4:
            # 提取域名前面部分（除最后一位）和最后一位
            prefix = domain_without_suffix[:-1]
            last_char = domain_without_suffix[-1]

            # 检查前缀不是纯数字且最后一位是纯数字
            if not prefix.isdigit() and last_char.isdigit():
                if prefix not in domain_groups:
                    domain_groups[prefix] = {}
                if last_char not in domain_groups[prefix]:
                    domain_groups[prefix][last_char] = []
                # 将编号和完整域名添加到对应的分组中
                domain_groups[prefix][last_char].append((number, domain))

# 打开一个新文件用于写入合并后的结果，指定编码为 utf-8
with open('merged_ens.txt', 'w', encoding='utf-8') as output_file:
    for prefix, last_char_dict in domain_groups.items():
        # 检查不同最后一位的数量是否大于等于 2
        if len(last_char_dict) >= 2:
            output_str = ""
            for last_char_items in last_char_dict.values():
                for number, domain in last_char_items:
                    output_str += f"{number},{domain},"
            # 去除最后一个多余的逗号
            output_str = output_str.rstrip(',')
            output_file.write(output_str + '\n')