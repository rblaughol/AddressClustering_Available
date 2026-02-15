from web3 import HTTPProvider
import csv
import os
import requests
from datetime import datetime
import threading
import time
# from aiohttp import ClientTimeout
csv.field_size_limit(1 * 1024 * 1024 * 1024) # 1G

# Configuration parameters
# [Note] Ensure directory name on server is synchronized to AddressClustering, otherwise revert to original path
output_dir = "/public/home/blockchain_2/slave1/janus-eth-tools/experiment/experiment_GY/AddressClustering/tmp"
default_base_path = "/public/home/blockchain_2/slave1/janus-eth-tools/experiment/experiment_GY/AddressClustering/eth"
local_tmp_dir = "./tmp"

ADDR_BLACKLIST = [
    "0x0000000000000000000000000000000000000000",
]

DEFAULT_PROXIES = {
    "http": "http://127.0.0.1:10809",
    "https": "http://127.0.0.1:10809",
}

class TimeoutController:
    def __init__(self, total_timeout_seconds=600):  # Default 10 minutes
        self.total_timeout = total_timeout_seconds
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def is_timeout(self):
        with self.lock:
            return (time.time() - self.start_time) > self.total_timeout
    
    def remaining_time(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            return max(0, self.total_timeout - elapsed)
    
    def reset(self):
        with self.lock:
            self.start_time = time.time()

class ThreadSafeHTTPProvider:
    def __init__(self, proxies=None, endpoint=None, max_retries=5, timeout_controller=None):
        self._proxies = proxies
        self._provider = None
        self._endpoint = endpoint
        self._max_retries = max_retries
        self._timeout_controller = timeout_controller
        self._init_provider()
    
    def _init_provider(self):
        # timeout = ClientTimeout(total=20)  # Set total timeout to 20 seconds
        self._provider = HTTPProvider(self._endpoint, request_kwargs={
                "proxies": self._proxies, 
                'timeout': 20, 
                # 'timeout': timeout, 
                'headers': {'Connection': 'close'},
                'stream': True
            })
    
    def make_request(self, method, params):
        for attempt in range(1, self._max_retries + 1):

            # Check overall timeout
            if self._timeout_controller and self._timeout_controller.is_timeout():
                print(f"Overall timeout: Seed processing exceeded {self._timeout_controller.total_timeout} seconds, stop fetching new data")
                return []
            
            try:
                return self._provider.make_request(method, params)

            except Exception as e:
                print(
                    f"[RPC retry {attempt}/{self._max_retries}] "
                    f"{method} failed: {str(e)[:200]}"
                )

                # Rebuild provider to avoid semi-dead connections
                self._init_provider()
                time.sleep(0.2 * attempt)

        # All retries failed
        return []

class TxListProvider:
    def __init__(self, api_key=None, endpoint=None, proxy=None, max_cache_size=10, timeout_controller=None):
        """
        Initialize transaction list provider
        """
        self.api_key = api_key or "RV3JTECVNSHXUKXRPWG3CA6VIC2CDDHHRK"
        self.endpoint = endpoint or "https://mainnet.chainnodes.org/cf52bb18-fce2-4d57-ae82-9b458012b8a8  "
        self.proxy = proxy or DEFAULT_PROXIES
        self.max_cache_size = max_cache_size
        self.timeout_controller = timeout_controller  # Inject timeout controller
        
        # Create independent HTTPProvider for this instance
        self.http_provider = ThreadSafeHTTPProvider(
            proxies=self.proxy,
            endpoint=self.endpoint,
            timeout_controller=self.timeout_controller
        )
        
        # Subgraph cache: Store acquired address transaction lists
        self.subgraph_cache = {}  # {address: tx_list}
        # LRU queue for managing cache size
        self._cache_access_order = []  # Record access order
    
    def _update_cache_access(self, address):
        """Update cache access order"""
        address_lower = address.lower()
        if address_lower in self._cache_access_order:
            self._cache_access_order.remove(address_lower)
        self._cache_access_order.append(address_lower)
        
        # Remove least recently used item if cache exceeds max size
        if len(self._cache_access_order) > self.max_cache_size:
            oldest_addr = self._cache_access_order.pop(0)
            if oldest_addr in self.subgraph_cache:
                del self.subgraph_cache[oldest_addr]
    
    def get_addr_tx_list(self, target_address, get_create=True, get_local=True):
        """
        Get transaction list for specified address (Main method)
        Prioritize cache; if miss, fetch from RPC and cache
        """
        address_lower = target_address.lower()

        # Check overall timeout
        if self.timeout_controller and self.timeout_controller.is_timeout():
            print(f"Overall timeout: Seed processing exceeded {self.timeout_controller.total_timeout} seconds, stop fetching new data")
            return []
        
        # Check cache first
        if address_lower in self.subgraph_cache:
            self._update_cache_access(target_address)
            print(f"Get transaction data for address {target_address} from cache")
            return self.subgraph_cache[address_lower]
        
        # Cache miss, execute actual query
        try:
            output_csv = os.path.join(output_dir, f"{target_address}.csv")
            local_csv = os.path.join(local_tmp_dir, f"{target_address}.csv")

            # Control whether to check local data here
            if get_local:
                # Check tmp first
                if os.path.exists(output_csv):
                    tx_list = self.get_local_tx_list(target_address, output_dir, get_create)
                    # Cache result
                    self.subgraph_cache[address_lower] = tx_list
                    self._update_cache_access(target_address)
                    return tx_list
                
                # If not in tmp, check eth
                default_csv = os.path.join(default_base_path, f"{target_address}.csv")
                if os.path.exists(default_csv):
                    tx_list = self.get_local_tx_list(target_address, default_base_path, get_create)
                    # Cache result
                    self.subgraph_cache[address_lower] = tx_list
                    self._update_cache_access(target_address)
                    return tx_list
                
                # If found nowhere, check local tmp
                if os.path.exists(local_csv):
                    tx_list = self.get_local_tx_list(target_address, local_tmp_dir, get_create)
                    # Cache result
                    self.subgraph_cache[address_lower] = tx_list
                    self._update_cache_access(target_address)
                    return tx_list

            if target_address in ADDR_BLACKLIST:
                empty_list = []
                # Cache empty result
                self.subgraph_cache[address_lower] = empty_list
                self._update_cache_access(target_address)
                return empty_list
            
            print(f"Querying transaction data for address {target_address}...")
            
            # Get normal transaction trace
            result_in = self.http_provider.make_request('trace_filter', [{
                "fromBlock": "0x0",
                "toBlock": "0x1c9c380",
                "toAddress": [target_address]
            }])

            result_out = self.http_provider.make_request('trace_filter', [{
                "fromBlock": "0x0",
                "toBlock": "0x1c9c380",
                "fromAddress": [target_address]
            }])

            # Get ERC20 token transfer records
            token_transfers = self.get_erc20_transfers(target_address)
            print(f"Address {target_address} got {len(token_transfers)} ERC20 token transfer records")

            # Check if data was successfully acquired
            traces = []
            if 'result' in result_in and 'result' in result_out:
                traces = result_in['result'] + result_out['result']
                print(f"Address {target_address} got {len(traces)} normal transaction records")
            else:
                print(f"Address {target_address} API returned error")
            
            # Process and merge all data
            if traces or token_transfers:
                graph_data = self.process_traces_to_graph(traces, token_transfers, get_create)
                self.save_to_csv(graph_data, local_csv)
                
                # Cache result
                self.subgraph_cache[address_lower] = graph_data
                self._update_cache_access(target_address)
                return graph_data
            else:
                print(f"No related transaction records found for address {target_address}")
                empty_list = []
                self.save_to_csv([], local_csv)
                
                # Cache empty result
                self.subgraph_cache[address_lower] = empty_list
                self._update_cache_access(target_address)
                return empty_list
                
        except Exception as e:
            print(f"Error processing address {target_address}: {str(e)[:100]}") 
            error_empty_list = []
            # Cache error result (empty list)
            self.subgraph_cache[address_lower] = error_empty_list
            self._update_cache_access(target_address)
            return error_empty_list
    
    def clear_subgraph_cache(self):
        """Clear subgraph cache"""
        self.subgraph_cache.clear()
        self._cache_access_order.clear()
        print("Subgraph cache cleared")
    
    def get_cache_stats(self):
        """Get cache statistics"""
        return {
            'cache_size': len(self.subgraph_cache),
            'max_cache_size': self.max_cache_size,
            'cached_addresses': list(self.subgraph_cache.keys())[:10],  # Show only first 10
            'access_order_length': len(self._cache_access_order)
        }
    
    def get_erc20_transfers(self, address, start_block=0, end_block=27025780):
        """
        Get ERC20 token transfer records for specified address using Etherscan API
        """
        url = f"https://api.etherscan.io/v2/api?chainid=1&module=account&action=tokentx&address={address}&page=1&offset=10000&startblock={start_block}&endblock={end_block}&sort=asc&apikey={self.api_key}"
        
        max_retries = 5  # Max retries
        retry_delay = 1  # Initial retry delay (seconds)
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, proxies=self.proxy)
                data = response.json()
                
                if data['status'] == '1':
                    return data['result']
                elif data.get('message') == 'NOTOK' and 'Max calls per sec rate limit reached' in data.get('result', ''):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"API rate limit reached, wait {wait_time} seconds to retry (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Failed to get data after max retries: {data}")
                        return []
                else:
                    print(f"Etherscan API returned error: {data}")
                    return []
            except Exception as e:
                print(f"Error getting ERC20 transfer records: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return []
        
        return []

    def get_create_pairs(self, tx_hash):
        """
        Trace transaction execution using callTracer and parse created contract addresses
        """
        # Check overall timeout
        if self.timeout_controller and self.timeout_controller.is_timeout():
            print(f"Overall timeout: Seed processing exceeded {self.timeout_controller.total_timeout} seconds, stop fetching new data")
            return []
        
        try:
            # Build tracer parameters
            tracer_params = {
                "tracer": "callTracer"
            }

            # Call debug_traceTransaction using RPC
            result = self.http_provider.make_request('debug_traceTransaction', [tx_hash, tracer_params])
            
            if 'result' in result:
                trace_data = result['result']
                
                # Parse trace data, extract created contract address pairs
                create_pairs = self._extract_created_contracts(trace_data)
                return create_pairs
            else:
                print(f"Trace transaction {tx_hash} failed: {result}")
                return []
                
        except Exception as e:
            print(f"Trace transaction {tx_hash} error: {str(e)}")
            return []

    def _extract_created_contracts(self, trace_data):
        """
        Recursively parse trace data to extract all contract address pairs created via CREATE/CREATE2
        """
        create_pairs = []
        
        def traverse_calls(calls_list):
            if not calls_list:
                return
            
            for call in calls_list:
                # Check if current call is CREATE or CREATE2
                call_type = call.get('type', '').upper()
                if call_type in ['CREATE', 'CREATE2']:
                    from_address = call.get('from')
                    to_address = call.get('to')
                    if from_address and to_address:
                        create_pairs.append((from_address.lower(), to_address.lower()))
                
                # Recursively check sub-calls
                sub_calls = call.get('calls', [])
                if sub_calls:
                    traverse_calls(sub_calls)
        
        # Check root level call first
        root_type = trace_data.get('type', '').upper()
        if root_type in ['CREATE', 'CREATE2']:
            from_address = trace_data.get('from')
            to_address = trace_data.get('to')
            if from_address and to_address:
                create_pairs.append((from_address.lower(), to_address.lower()))
        
        # Check root level sub-calls
        root_calls = trace_data.get('calls', [])
        traverse_calls(root_calls)
        
        return create_pairs

    def process_traces_to_graph(self, traces, token_transfers=None, get_create=True):
        """Convert raw trace data and token transfer data to graph structure"""
        graph_data = []
        create_txs = set()
        
        # Process normal transaction trace
        for trace in traces:
            action = trace.get('action', {})
            source = action.get('from', '')
            target = action.get('to', '')
            value_hex = action.get('value', '0x0')
            callType = action.get('callType', '')
            gas = action.get('gas', '')
            tx_input = action.get('input', '')
            block = trace.get('blockNumber', '0')
            trace_type = trace.get('type', '')
            tx_hash = trace.get('transactionHash', '')
            
            try:
                amount = int(value_hex, 16) / 1e18 if value_hex != '0x' else 0
                block = int(block)
            except Exception as e:
                print(f"{tx_hash} Processing exception: {str(e)}")
            
            # Process contract creation transactions
            if trace_type == 'create' and get_create:
                create_txs.add(tx_hash)
            
            graph_data.append({
                "source": source,
                "target": target,
                "amount": amount,
                "block": block,
                "tx_hash": tx_hash,
                "type": "native",   # Mark as native ETH transaction
                "callType": callType,
                "gas": gas,
                "tx_input": tx_input,
                "trace_type": trace_type
            })

        for tx_hash in create_txs:

            # Check overall timeout
            if self.timeout_controller and self.timeout_controller.is_timeout():
                print(f"Overall timeout: Seed processing exceeded {self.timeout_controller.total_timeout} seconds, stop fetching new data")
                break
        
            createPairs = self.get_create_pairs(tx_hash)
            
            for i, trace_item in enumerate(graph_data):
                matching_deployed_address = None
                for deployer_addr, deployed_addr in createPairs:
                    if (not trace_item["target"] or trace_item["target"] == "") \
                        and trace_item["tx_hash"].lower() == tx_hash    \
                        and trace_item["source"].lower() == deployer_addr.lower():
                        matching_deployed_address = deployed_addr
                        break
                
                # Update target address
                if matching_deployed_address:
                    graph_data[i]["target"] = matching_deployed_address
                    print(f"Found contract creation transaction {tx_hash}, updated target to contract address: {matching_deployed_address}")
        
        # Process token transfer data
        if token_transfers:
            for transfer in token_transfers:
                try:
                    # Parse token transfer data
                    source = transfer.get('from', '')
                    target = transfer.get('to', '')
                    value = float(transfer.get('value', 0))
                    decimals = int(transfer.get('tokenDecimal', 18))
                    
                    # Adjust amount precision
                    adjusted_amount = value / (10 ** decimals)
                    
                    # Get block and time information
                    block = int(transfer.get('blockNumber', 0))
                    timestamp = transfer.get('timeStamp', '')
                    if timestamp:
                        timestamp = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                    
                    graph_data.append({
                        "source": source,
                        "target": target,
                        "amount": adjusted_amount,
                        "block": block,
                        "tx_hash": transfer.get('hash', ''),
                        "type": "erc20",  # Mark as token transaction
                        "token_address": transfer.get('contractAddress', ''),
                        "token_symbol": transfer.get('tokenSymbol', 'UNKNOWN'),
                        "token_name": transfer.get('tokenName', ''),
                        "timestamp": timestamp,
                        "decimals": decimals
                    })
                except Exception as e:
                    print(f"Error processing token transfer: {str(e)}")
                    continue
        
        return graph_data

    def save_to_csv(self, data, output_csv):
        """Save graph data to CSV"""
        fieldnames = ["source", "target", "amount", "block", "tx_hash", "type", "callType", "gas", "tx_input", "trace_type"]
        
        if any('token_address' in item for item in data):
            fieldnames.extend(["token_address", "token_symbol", "token_name", "timestamp", "decimals"])
        
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f"Saved {len(data)} transaction records to {output_csv}")

    def get_local_tx_list(self, address, base_path=default_base_path, get_create=True):
        """
        Read transaction data from local CSV file and parse into graph_data format
        """
        # Build file path
        file_path = os.path.join(base_path, f"{address}.csv")
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return []
        
        tx_list = []
        create_txs = set()
        create_changed = False
        
        print(f"Reading {file_path} ...")
        
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Check overall timeout
                if self.timeout_controller and self.timeout_controller.is_timeout():
                    print(f"Overall timeout: Seed processing exceeded {self.timeout_controller.total_timeout} seconds, stop fetching new data")
                    break
            
                tx = {
                    'source': row.get('source', ''),
                    'target': row.get('target', ''),
                    'amount': float(row.get('amount', 0)),
                    'block': row.get('block', '0'),
                    'tx_hash': row.get('tx_hash', ''),
                    'type': row.get('type', 'native'),
                    'callType': row.get('callType', ''),
                    'gas': row.get('gas', '0x0'),
                    'tx_input': row.get('tx_input', '0x'),
                    'trace_type': row.get('trace_type', 'call'),
                    'token_address': row.get('token_address', ''),
                    'token_symbol': row.get('token_symbol', ''),
                    'token_name': row.get('token_name', ''),
                    'timestamp': row.get('timestamp', ''),
                    'decimals': int(row.get('decimals', 18)) if row.get('decimals') else 18
                }

                if tx['trace_type'] == 'create' and tx['target'] == '' and get_create:
                    create_txs.add(tx["tx_hash"])
                    
                tx_list.append(tx)

            for tx_hash in create_txs:
                createPairs = self.get_create_pairs(tx_hash)
                
                for i, trace_item in enumerate(tx_list):
                    matching_deployed_address = None
                    for deployer_addr, deployed_addr in createPairs:
                        if not trace_item["target"] or trace_item["target"] == "" \
                            and trace_item["tx_hash"].lower() == tx_hash    \
                            and trace_item["source"].lower() == deployer_addr.lower():
                            matching_deployed_address = deployed_addr
                            break
                    
                    if matching_deployed_address:
                        tx_list[i]["target"] = matching_deployed_address
                        print(f"Found contract creation transaction {tx_hash}, updated target to contract address: {matching_deployed_address}")
                        create_changed = True

        print(f"Read {len(tx_list)} transaction records from {file_path}")
        
        if create_changed:
            output_csv = os.path.join(local_tmp_dir, f"{address}.csv")
            self.save_to_csv(tx_list, output_csv)

        return tx_list

DEFAULT_PROVIDER = TxListProvider()

def get_addr_tx_list(target_address, ETHERSCAN_API_KEY=None, client=None, get_create=True):
    return DEFAULT_PROVIDER.get_addr_tx_list(target_address, get_create)