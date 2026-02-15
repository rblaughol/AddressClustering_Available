# selecting.py (Modified Version)

import re
import json
import time
from jinja2 import Template
from diskcache import Cache
from utils import APICostCalculator, chainnode_chat_complete

# ==========================================
# Define Batch Processing Prompt
# ==========================================

# This is a generic batch template for both ENS and LABEL
# We fine-tune rules using the task_type variable
BATCH_PROMPT_TEMPLATE = """
You are an expert in Entity Resolution and Data Linking for {{ task_type }}.
You will be provided with multiple independent tasks.

### YOUR OBJECTIVE:
For each task, you are given an **"Anchor"** (the reference entity) and a list of **"Candidates"**.
You must identify **ALL** Candidates that belong to the **SAME real-world entity** as the Anchor.

**CRITICAL INSTRUCTION:** - **Select ALL matching candidates.** Do NOT stop at the first match.
- There may be **multiple matches**, **one match**, or **no matches** for a single Anchor.

### MATCHING LOGIC:
{% if task_type == 'ENS' %}
**Context: ENS Domains (Ethereum Name Service)**
- **True Positive (Match):**
  - Numbering: 'fund1.eth', 'fund2.eth' (Same entity/wallet group).
  - Defensive: 'brand.eth', 'brand-official.eth'.
  - Subdomains: 'pay.bob.eth' matches 'bob.eth'.
- **False Positive (Do NOT Match):**
  - Typos/Phishing: 'google.eth' != 'gooogle.eth'.
  - Distinct Names: 'alice.eth' != 'bob.eth'.
{% else %}
**Context: Etherscan Labels**
- **True Positive (Match):**
  - Variations: 'Binance 2', 'Binance', 'Binance: Hot Wallet'.
  - Abbreviations: 'JPM' matches 'JPMorgan Chase'.
- **False Positive (Do NOT Match):**
  - Different Entities: 'Binance' != 'Coinbase'.
  - Distinct Subsidiaries: 'Alameda' != 'FTX' (unless treated as one group).
{% endif %}

### OUTPUT FORMAT (Strict JSON):
1. Return a single valid **JSON Object**.
2. Keys must be the `"Task_ID"` (string).
3. Values must be a **List of Integers** representing the indices of **ALL** matching candidates.
4. If **NO** candidates match, return `[0]`.

**Example Output:**
{
  "0": [1, 3, 4],    // Multiple matches found (Indices 1, 3, and 4)
  "1": [0],          // No match found
  "2": [2]           // Single match found
}

### BATCH TASKS:
{% for item in batch_items %}
---
Task_ID: "{{ loop.index0 }}"
**Anchor**: "{{ item.anchor }}"
**Candidates**:
{% for candidate in item.candidates %}
({{ loop.index }}) {{ candidate }}
{% endfor %}
{% endfor %}

---
**FINAL INSTRUCTION:**
Review all {{ batch_items|length }} tasks. Return ONLY the JSON object.
"""


class Selecting:
    def __init__(self, model_name: str = "gpt-5-mini", log_file: str = "llm_history.jsonl", task_type: str = "ENS"):
        self.model = model_name
        self.log_file = log_file
        self.task_type = task_type
        self.api_cost_decorator = APICostCalculator(model_name=model_name)

        # Cache Configuration
        cache = Cache(f"diskcache_selecting_{model_name}")
        self.chat_complete = self.api_cost_decorator(
            cache.memoize(name="chat_complete")(chainnode_chat_complete)
        )

        # Only one template needed
        self.template = Template(BATCH_PROMPT_TEMPLATE)

    def process_batch(self, batch_items: list) -> list:
        """
        Process a batch of data
        """
        if not batch_items:
            return []

        # Render Prompt
        prompt_content = self.template.render(
            task_type=self.task_type,
            batch_items=batch_items
        )

        messages = [{"role": "user", "content": prompt_content}]

        # Call API
        response = self.chat_complete(
            messages=messages,
            model=self.model,
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        try:
            raw_content = response["choices"][0]["message"]["content"].strip()
            clean_content = re.sub(r"^```json\s*|\s*```$", "", raw_content, flags=re.MULTILINE)
            result_json = json.loads(clean_content)
        except Exception as e:
            print(f"[Error] Failed to parse batch JSON: {e}")
            result_json = {}

        # Backfill results
        final_results = []
        for i, item in enumerate(batch_items):
            task_key = str(i)
            match_indices = result_json.get(task_key, [0])

            if not isinstance(match_indices, list):
                match_indices = [0]

            matched_strings = []
            candidates = item["candidates"]

            for idx in match_indices:
                if isinstance(idx, int) and 1 <= idx <= len(candidates):
                    matched_strings.append(candidates[idx - 1])

            final_results.append({
                "anchor": item["anchor"],
                "matches": matched_strings
            })

        # Batch logging
        # [Modification]: Passed prompt_content here
        self._log_batch(batch_items, raw_content, final_results, prompt_content)

        return final_results

    def _log_batch(self, inputs, raw_response, outputs, prompt_text):
        """
        Helper function: Batch logging
        [Modification]: Added prompt_text parameter
        """
        try:
            log_entry = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "task_type": self.task_type,
                "batch_size": len(inputs),
                "full_prompt_text": prompt_text,
                "raw_llm_response": raw_response,
                "parsed_outputs": outputs
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    @property
    def cost(self):
        return self.api_cost_decorator.cost