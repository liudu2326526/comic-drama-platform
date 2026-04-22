import json
import re
import logging

logger = logging.getLogger(__name__)

def extract_json(text: str) -> any:
    """
    从字符串中提取 JSON。处理 Markdown 代码块包裹的情况。
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取第一个 { 或 [ 到最后一个 } 或 ] 之间的内容
    match = re.search(r'([\{\[][\s\S]*[\}\]])', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to extract JSON from text: {text[:200]}...")
    raise ValueError("无法从 AI 响应中解析有效的 JSON 内容")
