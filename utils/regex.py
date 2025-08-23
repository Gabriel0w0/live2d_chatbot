import re
from typing import List

POSITIVE_PAT = re.compile(r"(謝謝|喜歡你|愛你|太棒|好棒|可愛|真貼心|抱抱|想你)")
NEGATIVE_PAT = re.compile(r"(不喜歡你|討厭你|爛|閉嘴|走開|煩|生氣|滾)")
NEUTRAL_PAT  = re.compile(r"(嗯|哦|好|OK|好的)[!！。.\s]*$", re.I)

def keyword_intimacy_fallback(text: str) -> int:
    if POSITIVE_PAT.search(text): return 1
    if NEGATIVE_PAT.search(text): return -1
    if NEUTRAL_PAT.search(text): return 0
    return 0

def extract_emotion_tag(text: str):
    tags = re.findall(r"\[emotion:(\w+)\]", text, flags=re.I)
    return tags[-1].lower() if tags else None

def emotion_weight(emotion: str) -> int:
    table = {"joy":1,"cute":1,"shy":0,"neutral":0,"sad":-1,"angry":-1}
    return table.get(emotion, 0)

def extract_facts(message: str) -> List[str]:
    facts: List[str] = []

    m = re.search(r"(我叫|我的名字是)(\w+)", message)
    if m:
        facts.append(f"他的名字是{m.group(2)}")

    m = re.search(r"我喜歡(\w+)", message)
    if m:
        facts.append(f"他喜歡{m.group(1)}")

    m = re.search(r"我討厭(\w+)", message)
    if m:
        facts.append(f"他討厭{m.group(1)}")

    m = re.search(r"我.*?(\d{1,3})\s*歲", message)
    if m:
        facts.append(f"他{m.group(1)}歲")

    m = re.search(r"我住在(\w+)", message)
    if m:
        facts.append(f"他住在{m.group(1)}")

    if "我是" in message:
        for job in ["老師", "學生", "工程師", "設計師"]:
            if job in message:
                facts.append(f"他是{job}")

    m = re.search(r"我覺得(\w+)", message)
    if m:
        facts.append(f"他覺得{m.group(1)}")

    if "我今天" in message:
        for emo in ["開心", "難過", "累", "生氣", "放鬆"]:
            if emo in message:
                facts.append(f"他今天{emo}")
    return facts