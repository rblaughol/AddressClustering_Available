import os
import json

all_unique_ids = set()  # 用集合自动去重

for filename in os.listdir('./Randomadd_proposed'):
    if os.path.isfile(os.path.join('./Randomadd_proposed', filename)):
        with open(os.path.join('./Randomadd_proposed', filename), 'r') as f:
            for line in f:
                if line.strip():  # 跳过空行
                    try:
                        ids = json.loads(line) # 解析每行的JSON列表
                        # print(map(str, ids))
                        # print(ids[0])
                        # print(type(ids))
                        for i in ids:
                            j = str(i)
                            all_unique_ids.add(j)  # 转为字符串并添加到集合
                    except json.JSONDecodeError:
                        print(f"Warning: 文件 {filename} 中存在格式错误的行: {line}")
print(all_unique_ids)

print(f"全局唯一ID总数（跨文件去重）: {len(all_unique_ids)}")




import os

all_unique_ids = set()

for filename in os.listdir('./Randomadd_airdrop'):
    if os.path.isfile(os.path.join('./Randomadd_airdrop', filename)):
        with open(os.path.join('./Randomadd_airdrop', filename), 'r') as f:
            for line in f:
                line = line.strip()  # 去除首尾空格和换行符
                if line:  # 跳过空行
                    # print(line)
                    all_unique_ids.add(line)

print(f"全局唯一ID总数: {len(all_unique_ids)}")





import os
import json

def count_unique_ids_across_folders(folders):
    all_unique_ids = set()
    
    for folder in folders:
        for root, _, files in os.walk(folder):  # 递归遍历子文件夹
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:  # 跳过空行
                                # print(line)
                                ids = json.loads(line)
                                all_unique_ids.update(map(str, ids))
                except (IOError, UnicodeDecodeError):
                    print(f"警告：跳过无法读取的文件 {filepath}")
    
    return len(all_unique_ids)

# 示例：统计多个文件夹的唯一ID总数
folders_to_scan = ["./Randomadd_sg1", "./Randomadd_sg2"]  # 替换为你的实际文件夹路径
total_unique_ids = count_unique_ids_across_folders(folders_to_scan)
print(f"跨文件夹全局唯一ID总数: {total_unique_ids}")

import os
from pathlib import Path

def count_non_empty_files(main_dir, backup_dir):
    """
    统计主目录中非空文件的数量，如果主目录中文件为空，
    则检查备份目录中是否有同名的非空文件
    """
    main_dir = Path(main_dir)
    backup_dir = Path(backup_dir)
    
    non_empty_count = 0
    
    # 遍历主目录中的所有文件
    for main_file in main_dir.rglob('*'):
        if main_file.is_file():
            # 检查主目录中的文件是否为空
            if main_file.stat().st_size > 0:
                non_empty_count += 1
            else:
                # 如果主目录文件为空，检查备份目录中的同名文件
                backup_file = backup_dir / main_file.relative_to(main_dir)
                if backup_file.exists() and backup_file.stat().st_size > 0:
                    non_empty_count += 1
    
    return non_empty_count

# 使用示例
if __name__ == "__main__":
    main_folder = "./Randomadd_sg1"  # 主文件夹路径
    backup_folder = "./Randomadd_sg1"  # 备用文件夹路径
    
    count = count_non_empty_files(main_folder, backup_folder)
    print(f"有效非空文件总数: {count}")