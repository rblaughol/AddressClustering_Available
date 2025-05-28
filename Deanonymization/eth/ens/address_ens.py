import requests
from web3 import Web3
from concurrent.futures import ProcessPoolExecutor, Future
import time

# Cloudflare 的公共以太坊节点 URL
URL = 'https://cloudflare-eth.com'

def create_w3_instance():
    """在每个进程中创建独立的 Web3 实例"""
    return Web3(Web3.HTTPProvider(URL))

def get_ens_name(address):
    """查询以太坊地址对应的 ENS 域名"""
    while True:
        try:
            # 创建 Web3 实例
            w3 = create_w3_instance()
            # 使用 Web3 查询 ENS
            ens_name = w3.ens.name(address)
            if ens_name:
                return ens_name
            else:
                return None
        except Exception as e:
            print(f"查询 ENS 时发生错误: {e}")

def process_single_address(address):
    """处理单个地址并返回 ENS 结果"""
    address = address.strip()
    ens_name = get_ens_name("0x" + address)
    if ens_name:
        return ens_name
    return None

def process_addresses(input_file, output_file):
    """处理地址文件并实时写入 ENS 解析结果"""
    with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
        lines = infile.readlines()

        # 使用 ProcessPoolExecutor 并行处理
        max_workers = 10  # 限制最大进程数为3
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = []  # 存储任务的 Future 对象
            resolved_ens = []

            for line_number, line in enumerate(lines, start=1):  # 这里修改了 index 为 line_number
                addresses = line.strip().split(',')
                print(f"处理第 {line_number} 行: {addresses}")
                
                # 为每个地址创建任务，并记录行号
                for address in addresses:
                    # 提交任务，同时将行号也传入 future
                    future = executor.submit(process_single_address, address)
                    futures.append((line_number, address, future))

                # 等待并处理完成的任务
                while len(futures) >= max_workers:  # 如果有3个进程在内存中
                    for i, (line_number, address, future) in enumerate(futures):
                        if future.done():  # 检查任务是否完成
                            try:
                                ens_name = future.result()
                                if ens_name:
                                    resolved_ens.append(ens_name)
                                # 从 futures 中移除已完成的任务
                                futures.pop(i)
                                # 每次处理已完成的 ENS
                                if resolved_ens:
                                    # 修改这里，确保第一列是行号
                                    outfile.write(f"{line_number},{','.join(resolved_ens)}\n")
                                    outfile.flush()  # 实时刷新输出文件
                                    resolved_ens.clear()
                            except Exception as e:
                                print(f"错误: {e}")
                    time.sleep(0.1)  # 每次等待0.1秒，避免CPU占用过高


if __name__ == '__main__':  # 确保多进程代码只在主模块中执行
    process_addresses("add.txt", "ens.txt")
