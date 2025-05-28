import requests
from concurrent.futures import ProcessPoolExecutor, Future
import time

def get_bnb_name(address):
    """查询 BNB 地址对应的 .bnb 域名"""
    try:
        # API URL
        api_url = f"https://api.prd.space.id/v1/getName?tld=bnb&address={address}"
        # 发起 GET 请求
        response = requests.get(api_url)
        # 检查响应状态
        if response.status_code == 200:
            # 如果请求成功，解析 JSON 响应
            data = response.json()
            # 如果查询成功，返回域名
            if data.get('name'):
                return data['name']
            else:
                return None
        else:
            print(f"Failed to fetch domain data. HTTP Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"查询 BNB 域名时发生错误: {e}")
        return None

def process_single_address(address):
    """处理单个地址并返回 BNB 域名结果"""
    address = address.strip()
    bnb_name = get_bnb_name("0x" + address)
    if bnb_name:
        return bnb_name
    return None

def process_addresses(input_file, output_file):
    """处理地址文件并实时写入 BNB 解析结果"""
    with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
        lines = infile.readlines()

        # 使用 ProcessPoolExecutor 并行处理
        max_workers = 30  # 限制最大进程数为10
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = []  # 存储任务的 Future 对象
            resolved_bnb = []

            for line_number, line in enumerate(lines, start=1):
                addresses = line.strip().split(',')
                print(f"处理第 {line_number} 行: {addresses}")

                # 为每个地址创建任务，并记录行号
                for address in addresses:
                    # 提交任务，同时将行号也传入 future
                    future = executor.submit(process_single_address, address)
                    futures.append((line_number, address, future))

                # 等待并处理完成的任务
                while len(futures) >= max_workers:  # 如果有10个进程在内存中
                    for i, (line_number, address, future) in enumerate(futures):
                        if future.done():  # 检查任务是否完成
                            try:
                                bnb_name = future.result()
                                if bnb_name:
                                    resolved_bnb.append(bnb_name)
                                # 从 futures 中移除已完成的任务
                                futures.pop(i)
                                # 每次处理已完成的 BNB 域名
                                if resolved_bnb:
                                    # 修改这里，确保第一列是行号
                                    outfile.write(f"{line_number},{','.join(resolved_bnb)}\n")
                                    outfile.flush()  # 实时刷新输出文件
                                    resolved_bnb.clear()
                            except Exception as e:
                                print(f"错误: {e}")
                    time.sleep(0.1)  # 每次等待0.1秒，避免CPU占用过高

    # 处理剩余的任务
    for line_number, address, future in futures:
        try:
            bnb_name = future.result()
            if bnb_name:
                resolved_bnb.append(bnb_name)
            # 每次处理已完成的 BNB 域名
            if resolved_bnb:
                # 修改这里，确保第一列是行号
                outfile.write(f"{line_number},{','.join(resolved_bnb)}\n")
                outfile.flush()  # 实时刷新输出文件
                resolved_bnb.clear()
        except Exception as e:
            print(f"错误: {e}")

if __name__ == '__main__':  # 确保多进程代码只在主模块中执行
    process_addresses("merged.txt", "bnb_ens.txt")