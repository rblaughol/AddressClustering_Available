import requests
import json

# Ollama 的聊天完成 API 地址
API_URL = "http://192.168.31.95:11434/api/chat"

# 初始化对话历史
conversation_history = []

# 定义存储对话历史的文件路径，可根据需要修改
HISTORY_FILE_PATH = "C:/Users/rbppsuc403proMax/Desktop/de_ex/multi-agent/conversation/strategy-PH.txt"


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


def generate_chat_response(prompt, model="phi4:latest"):
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

user_input = """
---
**Attention**
Two another strategies thought up by the other two GPTs are as follows.

**Strategy from GEMME**
Here's a strategy to group Ethereum entity names based on the provided data:

1. **Similarity Heuristics:** Group names that share common prefixes, suffixes, or keywords. For example, "Bitfinex: Deployer 4" and "Bitfinex: MultiSig 1" likely belong to the same entity ("Bitfinex").  
2. **Address Matching:** If we had access to the underlying Ethereum addresses associated with these names, direct address matching would be the most reliable method. However, this information is not provided in your input.
3. **Contextual Clues:** Analyze the context of each name. For instance, "MiningPoolHub: Old Address" and "MiningPoolHub: Old Address 3" suggest a connection to the same entity ("MiningPoolHub").
4. **Iterative Grouping:** Start by identifying clear pairings based on the heuristics above. Then iteratively expand groups by looking for names that share common elements with existing groups.
5. **Manual Review:** Due to the ambiguity of some names, manual review and judgment may be necessary for final entity consolidation. 


**Strategy from QWEN**
To deanonymize Ethereum entities based on the names provided in the data, we can employ a strategic grouping approach that leverages common naming conventions and contextual clues present within the given data. Here’s a summarized strategy:

1. **Identify Common Prefixes/Suffixes**: Names often share prefixes or suffixes indicating they belong to the same entity (e.g., "Bitfinex: Deployer 4", "Bitfinex: MultiSig 1" both start with "Bitfinex").

2. **Contextual Grouping**: Analyze names for contextual relationships, such as common operations or roles within a larger entity (e.g., all mentions of "Kraken X" likely belong to the Kraken exchange).

3. **Pattern Matching**: Utilize pattern matching techniques to group names that share similar patterns but may have slight variations in naming conventions.

4. **Manual Curation**: Identify entities where automatic methods might be less clear and manually curate these based on known information about Ethereum operations, exchanges, or services.

5. **Consolidation**: Combine the above steps iteratively to consolidate all names into entity groups with a high degree of confidence.

This strategy aims at systematically categorizing the provided names into distinct entities by leveraging both automated techniques for common naming conventions and manual insights where necessary.

---

**Instruction for You:**
Modify your strategy by combining the ideas from the other two GPTs. Summarise to tell me your new strategy.

---

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