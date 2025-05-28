import requests
import json

# Ollama 的聊天完成 API 地址
API_URL = "http://192.168.31.95:11434/api/chat"

# 初始化对话历史
conversation_history = []

# 定义存储对话历史的文件路径，可根据需要修改
HISTORY_FILE_PATH = "C:/Users/rbppsuc403proMax/Desktop/de_ex/multi-agent/conversation/interviewee-LL.txt"


def read_conversation_history():
    """
    从文件中读取已有的对话历史
    """
    global conversation_history
    try:
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            i = 0
            while i < len(lines):
                if lines[i].startswith("You: "):
                    # 提取用户消息，去除开头的 "You: "
                    user_msg_lines = [lines[i].replace("You: ", "").strip()]
                    i += 1
                    # 持续收集后续行，直到遇到下一个消息标识
                    while i < len(lines) and not lines[i].startswith(("You: ", "Ollama: ")):
                        user_msg_lines.append(lines[i].strip())
                        i += 1
                    user_msg = '\n'.join(user_msg_lines)

                    if i < len(lines) and lines[i].startswith("Ollama: "):
                        # 提取机器人消息，去除开头的 "Ollama: "
                        bot_msg_lines = [lines[i].replace("Ollama: ", "").strip()]
                        i += 1
                        # 持续收集后续行，直到遇到下一个消息标识
                        while i < len(lines) and not lines[i].startswith(("You: ", "Ollama: ")):
                            bot_msg_lines.append(lines[i].strip())
                            i += 1
                        bot_msg = '\n'.join(bot_msg_lines)
                        conversation_history.append((user_msg, bot_msg))
                    else:
                        # 如果没有找到对应的 Ollama 回复，继续下一行
                        continue
                else:
                    # 如果当前行不是以 "You: " 开头，继续下一行
                    i += 1
        # print(conversation_history)
    except FileNotFoundError:
        print(f"文件 {HISTORY_FILE_PATH} 未找到。")
    except UnicodeDecodeError:
        print(f"读取文件 {HISTORY_FILE_PATH} 时发生编码错误。")
    except Exception as e:
        print(f"读取文件 {HISTORY_FILE_PATH} 时发生未知错误: {e}")


def generate_chat_response(prompt, model="llama3.3:latest"):
    """
    向 Ollama 的聊天完成 API 发送请求，获取聊天回复
    :param prompt: 用户输入的最新提示信息
    :param model: 使用的模型名称
    :return: Ollama 的回复内容
    """
    global conversation_history
    # 构造消息列表，将之前的对话历史和新的用户输入加入其中
    messages = []
    for entry in conversation_history:
        messages.append({"role": "user", "content": entry[0]})
        messages.append({"role": "assistant", "content": entry[1]})
    messages.append({"role": "user", "content": prompt})

    # 构建请求数据
    data = {
        "model": model,
        "messages": messages
    }

    try:
        # 发送 POST 请求
        response = requests.post(API_URL, json=data, stream=True)
        response.raise_for_status()

        full_response = ""
        # 逐行处理流式响应
        for line in response.iter_lines():
            if line:
                try:
                    json_data = json.loads(line)
                    if 'message' in json_data and 'content' in json_data['message']:
                        full_response += json_data['message']['content']
                except json.JSONDecodeError as e:
                    print(f"解析 JSON 数据时出错: {e}")

        # 更新对话历史
        conversation_history.append((prompt, full_response))
        return full_response
    except requests.RequestException as e:
        print(f"请求发生错误: {e}")
    return None


def write_conversation_history():
    """
    将对话历史写入文件
    """
    with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as file:
        for user_msg, bot_msg in conversation_history:
            file.write(f"You: {user_msg}\n")
            file.write(f"Ollama: {bot_msg}\n")

def read_file_to_string(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到。")
    except UnicodeDecodeError:
        print(f"读取文件 {file_path} 时发生编码错误。")
    except Exception as e:
        print(f"读取文件 {file_path} 时发生未知错误: {e}")

# 使用示例
file_path = 'C:/Users/rbppsuc403proMax/Desktop/de_ex/multi-agent/dep_name.txt'
result = read_file_to_string(file_path)

# 读取已有对话历史
read_conversation_history()
# user_input = "**Given Data:**\n"
# user_input = user_input + result
user_input = """
**Role Setting:**  
You are an interviewer and need to give an implementation based on the given data and the question from intervierer.

---

**Question From Interviewer:**

Given the list of Ethereum entity names provided, can you group them into entities where each entity consists of related or associated names? Please use only the names from the data and do not introduce new groups. Provide your response in JSON format with entity names as keys and their corresponding names as values.

```json
{
  "Entity1": ["name1", "name2"],
  "EntityB": ["name3"]
}
```

List of Names:
- Ambisafe Operations
- MEV Builder: 0x1B...2Ca
- Augur: Wallet
- MiningPoolHub: Old Address 2
- Bittrex 2
- Null: 0x123...890
- Bitfinex: Deployer 4
- Bitfinex: MultiSig 1
- Digix: Token Sale
- DigixDAO: DGD Token
- Ethpool 2
- FoundationTipJar
- Unicorns ()
- Null Address: 0x000...000
- Ethpool
- ShapeShift 1
- DwarfPool: Donate
- QuadrigaCX 3
- DwarfPool 2
- ShapeShift: Bittrex Deposit
- Suprnova 2
- Etherdice.io
- Suprnova
- AlphaPool
- MiningPoolHub: Old Address 3
- Coinone
- WHG: Jordi Baylina
- Kraken: Deployer 1
- Kraken 5
- Kraken 3
- Fee Recipient: 0x04...186
- Kraken
- Yunbi 2
- Etheropt: Old Contract
- EthereumPyramid.com
- EthereumPool
- Augur: Token Sale
- MyEtherWallet: Old Address
- Digix: Old Contract
- Freewallet
- QuadrigaCX 1
- Yunbi 3
- HitBTC 1
- Coinotron 2
- Bittrex
- Ether.Camp: Price Feed
- Coinotron 1
- CoinMine.pl
- Bitfinex: Old Address 1
- MiningPoolHub: Old Address
- Ethermine
- ShapeShift 2
- Kraken 2
- Gemini: Deployer 1
- Gemini: Old Contract 1
- Gemini 3
- Gemini 2
- BitClubPool
- Nanopool
- Eth.pp.ua
- Weipool
- DwarfPool
- Etheroll: Old Contract 1
- Kraken 6
- MiningPoolHub: Old Address 4
- Kraken 4
- Bitfinex: Deployer 2
- Ethernodes: Donate
- Poloniex
- EthDev
- Poloniex 3
- F2Pool 2
- Bitfinex: Old Address 2
- Gemini
- Genesis Mining
- Yunbi 1

---

**Input Example:**  

The input data has been given. I have send to you.

**Expected Output:**  
```json
{
  "Entity1": ["name1", "name2"],
  "EntityB": ["name3"]
}
```

---

**Instruction for You:**
Now, tell me, what message would you send to answer the interviewer?

Message Format:
- Role: Interviewee
- Message: (Your message here)

Give me directly the message you would send. **No unneccesary outputs.**

"""
response = generate_chat_response(user_input)
if response:
    # print(f"Ollama: {response}")
    # 显示完整的对话历史
    print("\n完整对话历史:")
    for user_msg, bot_msg in conversation_history:
        print(f"You: {user_msg}")
        print(f"Ollama: {bot_msg}")
    print()

# 对话结束后写入对话历史到文件
write_conversation_history()