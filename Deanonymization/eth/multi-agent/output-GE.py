import requests
import json

# Ollama 的聊天完成 API 地址
API_URL = "http://192.168.31.95:11434/api/chat"

# 初始化对话历史
conversation_history = []

# 定义存储对话历史的文件路径，可根据需要修改
HISTORY_FILE_PATH = "C:/Users/rbppsuc403proMax/Desktop/de_ex/multi-agent/conversation/result-GE.txt"


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


def generate_chat_response(prompt, model="gemma2:27b"):
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
user_input = "**Given Data:**\n"
user_input = user_input + result
user_input += """

Above are all the names in the blockchain.

---

**Task Objective:**  
The task is to deanonymize Ethereum entities based on the names of addresses. An entity may have multiple addresses with multiple names.
According to the "Given Strategies", give me the output.

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
**Given Strategies:**  
Grouping Ethereum Address Names

1. **Data Preparation**:
   - Extract all unique names from the provided data set.
   - Identify common patterns, keywords, and structures that may indicate associations.

2. **Pattern Identification**:
   - Use similarity heuristics to recognize common prefixes, suffixes, or repeated keywords (e.g., "Bitfinex: Deployer", "Kraken").
   - Apply pattern recognition techniques like regular expressions or string matching to group similar names.

3. **Grouping Based on Patterns**:
   - Create initial groups by pairing names with clear similarities.
   - Expand these groups iteratively by incorporating additional names that share common elements.

4. **Contextual Analysis**:
   - Examine the context of each name to identify roles (e.g., "Old Address", "Deployer") or services, aiding in accurate grouping.
   - Use any available external data sources for validation if possible.

5. **Iterative Refinement**:
   - Continuously refine groups by re-evaluating and updating based on new insights or discovered patterns.
   - Consider edge cases where names might belong to multiple entities due to partnerships or shared services.

6. **Manual Review and Curation**:
   - Conduct manual reviews for ambiguous groupings, using known information about Ethereum operations to aid decision-making.

7. **Final Mapping**:
   - Assign a unique identifier to each cluster, ensuring each name is assigned to the most appropriate entity.
   - Prepare a final mapping of entities to their associated names.

8. **Output Generation**:
   - Format the results into a structured JSON output where each key represents an entity and the value is a list of its associated names.

This strategy combines systematic pattern recognition with iterative refinement and manual oversight, ensuring accurate and comprehensive grouping of Ethereum address names under their respective entities.

---

**Instruction for You:**
Generate the output.
Please give me the complete de-anonymised results. There should be 76 names present in the results.
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