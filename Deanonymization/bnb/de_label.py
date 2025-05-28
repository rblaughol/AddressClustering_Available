import requests

# 目标地址
address = "0x167275438059617E3b259e5cE96681760C82a3DE"

# API URL
api_url = f"https://api.prd.space.id/v1/getName?tld=bnb&address={address}"

# 发起 GET 请求
response = requests.get(api_url)

# 检查响应状态
if response.status_code == 200:
    # 如果请求成功，解析 JSON 响应
    data = response.json()
    
    # 如果查询成功，显示域名
    if data.get('name'):
        print(f"The .bnb domain for address {address} is: {data['name']}")
    else:
        print(f"No .bnb domain found for address {address}.")
else:
    print("Failed to fetch domain data. HTTP Status Code:", response.status_code)
