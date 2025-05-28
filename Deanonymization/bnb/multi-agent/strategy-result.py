import requests
import json

# Ollama 的聊天完成 API 地址
API_URL = "http://192.168.31.95:11434/api/chat"

# 初始化对话历史
conversation_history = []

# 定义存储对话历史的文件路径，可根据需要修改
HISTORY_FILE_PATH = "C:/Users/rbppsuc403proMax/Desktop/de_ex/multi-agent/conversation/strategy-result.txt"


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


def generate_chat_response(prompt, model="deepseek-r1:70b"):
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
But I've been given strategies by other intelligences. The task is to summarise their strategies. Remember there is no other external information.

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
(1)Here's a refined strategy, incorporating the strengths of the other GPTs:

**Combined Strategy for Ethereum Entity Deanonymization**

1. **Data Preparation:** Extract unique names and identify potential patterns (prefixes, suffixes, keywords) indicating entity relationships. 

2. **Pattern-Based Grouping:** Use regular expressions or string matching to cluster names based on shared patterns (e.g., "Bitfinex: Deployer", "Kraken").

3. **Contextual Analysis:** Analyze the context of each name and group them according to their roles, operations, or associations (e.g., "ShapeShift: Bittrex Deposit" suggests a connection between ShapeShift and Bittrex).

4. **Iterative Refinement:**  Continuously refine groupings through iterative analysis:
    - Identify ambiguous cases requiring manual review.
    - Cross-reference with external data sources (if available) to validate groupings.
    - Adjust clusters based on new insights or discovered patterns.

5. **Entity Identification and Mapping:** Assign unique identifiers to each refined cluster, representing distinct entities. Create a final mapping of these identifiers to their associated names. 

6. **Output Generation:** Format the results into a JSON structure for easy interpretation.



This combined approach leverages both automated pattern recognition and contextual analysis, leading to more accurate entity identification. The iterative refinement process ensures ongoing improvement in the grouping accuracy.

(2)To create a comprehensive strategy for grouping Ethereum entity names, we can integrate elements from both alternative strategies. Here is an enhanced approach:

1. **Common Prefixes/Suffixes and Keywords**:
   - Begin by identifying common prefixes or suffixes in the names (e.g., "Bitfinex:", "Kraken", "MiningPoolHub: Old Address"). This initial step helps in forming preliminary clusters of related entities.

2. **Contextual Clues and Contextual Grouping**:
   - Analyze contextual relationships between names to further refine groupings. Consider operations, roles, or services implied by the names (e.g., addresses labeled with "Old Contract" or specific numbers like "Deployer 1" might belong to a single entity).

3. **Pattern Matching and Similarity Heuristics**:
   - Use pattern matching techniques to identify names that share similar structures but may have variations in naming conventions. This step helps in capturing slight differences within the same entity (e.g., "Bitfinex: Deployer 4" vs. "Bitfinex: MultiSig 1").

4. **Iterative Grouping**:
   - Start with clear pairings based on identified prefixes, suffixes, and contextual clues. Iteratively expand these groups by looking for additional names that share common elements with existing clusters.

5. **Manual Review and Curation**:
   - For ambiguous or unclear groupings, apply manual review to make final decisions. Use known information about Ethereum operations, exchanges, or services to aid in this process where automated methods may fall short.

6. **Consolidation**:
   - Combine all findings iteratively to consolidate names into distinct entity groups with a high degree of confidence. Ensure that each group is internally consistent and represents a single entity as accurately as possible.

This strategy leverages both automated techniques for detecting common naming conventions and manual insights where necessary, providing a robust framework for grouping Ethereum entity names effectively.

(3)Here is a combined and refined strategy that integrates elements from both GEMME's and PHI's approaches:

1. **Data Preparation**:
   - Extract all unique names from the provided data.
   - Identify patterns or keywords in the names indicating they belong to the same entity (e.g., "Bitfinex: Deployer", "Kraken").

2. **Similarity Heuristics**:
   - Group names that share common prefixes, suffixes, or keywords using pattern recognition techniques such as regular expressions or string matching.
   - Examples include grouping "MiningPoolHub: Old Address" and "MiningPoolHub: Old Address 3" under the same entity ("MiningPoolHub").

3. **Contextual Clues**:
   - Analyze the context of each name to identify clear pairings based on common elements (e.g., names associated with old addresses or specific roles).
   
4. **Pattern Recognition**:
   - Use regular expressions or string matching to identify and group names by common patterns.
   - Examples include "Old Address", "Deployer", etc.

5. **Entity Identification**:
   - Assign a unique entity identifier to each cluster based on shared characteristics or repeated occurrences across different addresses.
   
6. **Cross-Referencing**:
   - Cross-reference with external data sources (if available) such as blockchain explorers or transaction histories to validate groupings.
   - Adjust clusters if new information suggests different associations.

7. **Iterative Refinement**:
   - Continuously refine the grouping by iterating over the data and updating clusters based on additional insights or discovered patterns.
   - Consider edge cases where names might belong to multiple entities due to shared services or partnerships.

8. **Final Mapping**:
   - Create a final mapping of entity identifiers to their associated names, ensuring each name is assigned to only one entity unless there’s compelling evidence for dual associations.

9. **Manual Review**:
   - Due to the ambiguity of some names, conduct a manual review and judgment for final consolidation.
   
10. **Output Generation**:
    - Format the results into a JSON structure where each key represents an entity, and the value is a list of associated names.

Here’s how the expected output might look:

```json
{
  "Bitfinex": ["Bitfinex: Deployer 4", "Bitfinex: MultiSig 1", "Bitfinex: Old Address 1"],
  "Kraken": ["Kraken: Deployer 1", "Kraken 5", "Kraken 3", "Kraken 6", "Kraken 4", "Kraken 2", "Kraken"],
  "Bittrex": ["ShapeShift: Bittrex Deposit", "Yunbi 3", "Bittrex"],
  "DwarfPool": ["DwarfPool: Donate", "DwarfPool", "MiningPoolHub: Old Address 4"],
  "OldAddresses": ["MiningPoolHub: Old Address 2", "MiningPoolHub: Old Address 3", "MiningPoolHub: Old Address"],
  "Etheropt": ["Etheropt: Old Contract"],
  "Gemini": ["Gemini: Deployer 1", "Gemini: Old Contract 1", "Gemini 3", "Gemini 2", "Gemini"],
  "Unicorns": [""],
  "NullAddress": ["0x123...890", "0x000...000"]
}
```

By combining these elements, the strategy ensures a systematic and thorough approach to grouping Ethereum address names under their respective entities. This provides a clearer picture of the underlying organizational structures.

---

**Instruction for You:**
Help me summarise a strategy in conjunction with the above.

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