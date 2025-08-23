import re, asyncio
from langchain_ollama import ChatOllama
from langchain.schema import HumanMessage
chat_model = ChatOllama(model="gemma3")

async def translate_to_japanese(text: str, role_style: str = "可愛、撒嬌語氣") -> str:
    if not text.strip():
        return ""
    
    prompt = f"""
請將以下中文翻譯成日文，並保持角色語氣：{role_style}。
中文：
「{text}」
請只輸出日文翻譯，不要加入任何解釋
"""
    def _invoke():
        return chat_model.invoke([HumanMessage(content=prompt)])
    
    result = await asyncio.to_thread(_invoke)
    return re.sub(r"^\s+|\s+$", "", result.content)