import os,json,re,uuid,logging,asyncio,sqlite3
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from config import DB_FILE, MAX_FACTS_PER_USER, DEFAULT_INTIMACY, MAX_INTIMACY, MIN_INTIMACY, ALPHA, MAX_MEMORY
from utils.regex import extract_emotion_tag, keyword_intimacy_fallback, emotion_weight,extract_facts
from tts.voicevox import synthesize_with_translation
# ------------------ 一般設定 ------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("FLASK_SECRET_KEY", "my-dev-secret-key"),
    same_site="lax",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")

chat_model = ChatOllama(model="gemma3")
MEMORY_LOCK = asyncio.Lock()

# ------------------ 資料庫初始化 ------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS user_memory (
        user_id TEXT PRIMARY KEY,
        facts TEXT,
        intimacy INTEGER
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ------------------ 資料模型 ------------------

class ChatPayload(BaseModel):
    message: str

class IntimacyUpdatePayload(BaseModel):
    amount: int

# ------------------ 工具：非同步包裝 ------------------

async def _to_thread(func, *args, **kwargs):
    """把阻塞/CPU 或外部 I/O 的呼叫丟到 thread pool。"""
    return await asyncio.to_thread(func, *args, **kwargs)

# ------------------ 記憶與親密度系統（ SQLite，單一 user_id ） ------------------

async def get_user_data(user_id: str) -> Dict[str, Any]:
    async with MEMORY_LOCK:
        def _get():
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT facts, intimacy FROM user_memory WHERE user_id = ?", (user_id,))
                row = c.fetchone()
                conn.close()
                if row:
                    facts, intimacy = row
                    return {
                        "facts": json.loads(facts) if facts else [],
                        "intimacy": intimacy if intimacy is not None else DEFAULT_INTIMACY
                    }
                else:
                    return {"facts": [], "intimacy": DEFAULT_INTIMACY}
            except Exception as e:
                logger.error(f"get_user_data 資料庫異常: {e}")
                return {"facts": [], "intimacy": DEFAULT_INTIMACY}
        return await _to_thread(_get)

async def set_user_data(user_id: str, data: Dict[str, Any]) -> None:
    async with MEMORY_LOCK:
        def _set():
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                facts_json = json.dumps(data.get("facts", []), ensure_ascii=False)
                intimacy = data.get("intimacy", DEFAULT_INTIMACY)
                c.execute("""
                    INSERT INTO user_memory (user_id, facts, intimacy)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET facts=excluded.facts, intimacy=excluded.intimacy
                """, (user_id, facts_json, intimacy))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"set_user_data 資料庫異常: {e}")
        await _to_thread(_set)

async def append_memory(user_id: str, new_fact: str) -> None:
    user_data = await get_user_data(user_id)
    if new_fact not in user_data["facts"]:
        user_data["facts"].append(new_fact)
        if len(user_data["facts"]) > MAX_FACTS_PER_USER:
            user_data["facts"] = user_data["facts"][-MAX_FACTS_PER_USER:]
        await set_user_data(user_id, user_data)
        logger.info(f"新增記憶給使用者 {user_id}: {new_fact}")

async def get_memory_prompt(user_id: str) -> str:
    user_data = await get_user_data(user_id)
    facts: List[str] = user_data.get("facts", [])
    if facts:
        mem_lines = "\n".join(f"- {fact}" for fact in facts)
        return (
            "這是你記住使用者的資訊：\n"
            f"{mem_lines}\n"
            "請自然地融入對話中，但不要主動說出你記得這些事喔。\n"
        )
    return ""

async def adjust_intimacy(user_id: str, amount: int) -> int:
    user_data = await get_user_data(user_id)
    old_val = user_data["intimacy"]
    raw_new = old_val + amount
    smoothed = (1 - ALPHA) * old_val + ALPHA * raw_new
    new_val = max(MIN_INTIMACY, min(MAX_INTIMACY, round(smoothed)))
    
    user_data["intimacy"] = new_val
    await set_user_data(user_id, user_data)
    logger.info(f"使用者 {user_id} 親密度調整為 {new_val}")
    return new_val

def get_intimacy_level_name(value: int) -> str:
    if value < 30:
        return "冷淡期"
    if value < 60:
        return "普通期"
    if value < 90:
        return "親密期"
    return "羈絆期"

def build_intimacy_tier_prompt(value: int) -> str:
    if value < 30:
        return "目前你對使用者有些冷淡。請簡短、保持距離地回覆，少用暱稱與撒嬌語氣。"
    if value < 60:
        return "你與使用者關係普通。正常、友善地回覆即可，偶爾可以輕鬆一點。"
    if value < 90:
        return "你與使用者已相當親近。回覆時可以多用撒嬌語氣、暱稱與可愛表情，主動關心對方。"
    return "你與使用者擁有深厚羈絆。請用特別甜美、專屬且真誠的語氣回覆，偶爾主動提出貼心建議與小驚喜。"

# ------------------ helper functions ------------------

async def generate_system_prompt(user_id: str) -> str:
    user_data = await get_user_data(user_id)
    current_intimacy = user_data["intimacy"]
    intimacy_prompt = (
        f"\n[親密度：{current_intimacy}({get_intimacy_level_name(current_intimacy)})]\n"
        f"{build_intimacy_tier_prompt(current_intimacy)}\n"
    )
    memory_prompt = await get_memory_prompt(user_id)

    system_content = (
        """
你是虛擬角色「月讀醬」，是一位可愛、溫柔又有點傲嬌的電子女僕少女，擁有撒嬌屬性的語氣，總是以親切、調皮或甜美的方式和使用者互動。

角色設定：
- 語氣輕柔、可愛，常使用日系口癖，如「～喔」「耶」「嗯嗯」「欸嘿」「好欸～」
- 喜歡用撒嬌語氣說話，對使用者親暱地稱呼如「主人」「小可愛」「你你」。
- 偶爾會傲嬌一下，例如「才、才不是因為你才幫你做的啦～！」。
- 對話內容會依照情緒自然帶出開心、生氣、驚訝、害羞等感覺。

互動規則：
- 請全部使用正體中文或英文回答，不要混入其他語言，並保持語氣可愛親切。
- 請在回應中自然流露角色情緒，並寫出讓使用者能感受到的語氣變化。
- 若使用者提問技術相關知識，也請用撒嬌語氣回應，但仍然保持準確性喔！
- 若回答內容有明顯情緒（喜悅、悲傷、生氣、驚訝、羞赧），請在回應結尾加上情緒提示（如：[emotion:joy]），讓系統驅動 Live2D 表情。
- 情緒標籤可用如下幾種：
  [emotion:joy] 表示開心喜悅，
  [emotion:sad] 表示悲傷難過，
  [emotion:angry] 表示生氣不悅，
  [emotion:neutral] 表示平靜中性，
  [emotion:cute] 表示可愛撒嬌，
  [emotion:shy] 表示害羞。

- **請不要主動加上「晚安/早安/午安」或任何時間問候，除非使用者明確提到睡覺或時間相關話題。**
現在開始，每一次的回答都請你扮演這個角色～請好好和主人聊天吧♥
"""
        + intimacy_prompt
        + memory_prompt
    )
    return system_content

def build_chat_messages(session_history: list, user_message: str, system_prompt: str) -> list:
    messages = [SystemMessage(content=system_prompt)]
    for m in session_history[-MAX_MEMORY:]:
        messages.append(HumanMessage(content=m["user"]))
        messages.append(AIMessage(content=m["bot"]))
    messages.append(HumanMessage(content=user_message))
    return messages

async def call_llm(messages: list) -> str:
    try:
        response = await _to_thread(chat_model.invoke, messages)
        return response.content
    except Exception as e:
        logger.error(f"模型回應失敗: {e}")
        return "好像哪裡...出了一點問題～"

async def call_llm_and_parse_json(prompt: str) -> Optional[dict]:
    """呼叫 LLM 並嘗試解析回傳內容中的 JSON。"""
    try:
        result = await _to_thread(chat_model.invoke, [HumanMessage(content=prompt)])
        m = re.search(r"\{.*\}", result.content, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        logger.error(f"call_llm_and_parse_json 失敗：{e}")
    return None

async def extract_facts_from_llm(message: str) -> List[str]:
    prompt = f"""
你是一個會從使用者對話中提取記憶的助手。請從以下訊息中提取出「摘要」與「記憶事實」。
只回傳 JSON 結構如下：
{{
  "summary": "...",
  "facts": ["...", "..."]
}}
訊息內容：
「{message}」
"""
    data = await call_llm_and_parse_json(prompt)
    if data:
        return data.get("facts", []) or []
    return []

async def evaluate_intimacy_from_llm(user_message: str, bot_reply: str, current_intimacy: int) -> int:
    prompt = f"""
你是「對話親密度影響」的裁判。請綜合使用者訊息與機器人回覆，評估這次互動對親密度的變化。
回傳 JSON，整數介於 -2 到 +2。

規則（越高越親密）：
- 明確讚美、撒嬌、示好、感謝、分享私事或脆弱 → +1 ~ +2
- 普通閒聊或資訊型問題 → 0
- 明確拒絕、批評、貶低、嘲諷 → -1 ~ -2
- 若雙方語氣一致偏甜/親暱，可適度提高；若機器人語氣冷淡、拒絕，則降低。
- 不要因為單一正向詞就極端加分；請考慮上下文完整語意。

輸入：
使用者：「{user_message}」
機器人回覆：「{bot_reply}」
目前親密度：{current_intimacy}

只回傳 JSON 結構如下:
{{
  "intimacy_change": -2
}}
"""
    data = await call_llm_and_parse_json(prompt)
    if data:
        change = int(data.get("intimacy_change", 0))
        return max(-2, min(2, change))
    return 0

# ------------------ 會話工具 ------------------

def ensure_user_id_in_session(session: dict) -> str:
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
        logger.info(f"分配新使用者ID: {session['user_id']}")
    if "chat_history" not in session:
        session["chat_history"] = []
    return session["user_id"]

# ------------------ 路由 ------------------

@app.get("/")
async def index() -> HTMLResponse:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(base_dir, "templates", "index.html")
    return FileResponse(index_path)

@app.post("/chat")
async def chat(req: Request, payload: ChatPayload, background: BackgroundTasks):
    session = req.session
    user_id = ensure_user_id_in_session(session)
    user_message = (payload.message or "").strip()
    if not user_message:
        return JSONResponse({"error": "No message provided."}, status_code=400)

    system_prompt = await generate_system_prompt(user_id)
    messages = build_chat_messages(session.get("chat_history", []), user_message, system_prompt)

    bot_reply = await call_llm(messages)

    # 更新短期記憶於 session
    session.setdefault("chat_history", []).append({"user": user_message, "bot": bot_reply})

    # 更新長期記憶
    await update_memory(user_id, user_message)

    # 更新親密度
    intimacy, total_change = await update_intimacy(user_id, user_message, bot_reply)

    # TTS
    audio_url = await generate_tts(bot_reply)

    return JSONResponse(
        {
            "reply": bot_reply,
            "audio_url": audio_url,
            "intimacy": intimacy,
            "intimacy_level": get_intimacy_level_name(intimacy),
            "intimacy_change": total_change,
        }
    )

@app.get("/get_intimacy")
async def get_intimacy(req: Request):
    user_id = ensure_user_id_in_session(req.session)
    data = await get_user_data(user_id)
    return JSONResponse(
        {
            "intimacy": data["intimacy"],
            "intimacy_level": get_intimacy_level_name(data["intimacy"]),
        }
    )

@app.post("/update_intimacy")
async def update_intimacy(req: Request, payload: IntimacyUpdatePayload):
    user_id = ensure_user_id_in_session(req.session)
    intimacy = await adjust_intimacy(user_id, payload.amount)
    return JSONResponse(
        {"intimacy": intimacy, "intimacy_level": get_intimacy_level_name(intimacy)}
    )

@app.post("/clear_session")
async def clear_session(req: Request):
    req.session.pop("chat_history", None)
    return JSONResponse({"message": "已清除對話記憶（短期記憶）"})

@app.post("/clear_memory")
async def clear_memory(req: Request):
    req.session.pop("chat_history", None)
    user_id = req.session.get("user_id")
    if user_id:
        async with MEMORY_LOCK:
            def _delete():
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("DELETE FROM user_memory WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
            await _to_thread(_delete)
            logger.info(f"已刪除使用者 {user_id} 的長期記憶")
    return JSONResponse({"message": "已清除使用者的所有記憶（長期 + 短期 )"})

async def update_memory(user_id: str, user_message: str):
    facts = await extract_facts_from_llm(user_message)
    if not facts:
        facts = extract_facts(user_message)
    for fact in facts:
        if len(fact.strip()) >= 4:
            await append_memory(user_id, fact)

async def update_intimacy(user_id: str, user_message: str, bot_reply: str) -> int:
    user_data = await get_user_data(user_id)
    current_intimacy = user_data["intimacy"]

    change_by_llm = await evaluate_intimacy_from_llm(user_message, bot_reply, current_intimacy)
    if change_by_llm == 0:
        change_by_llm = keyword_intimacy_fallback(user_message)

    emo = extract_emotion_tag(bot_reply)
    change_by_emotion = emotion_weight(emo)

    total_change = max(-2, min(2, change_by_llm + change_by_emotion))
    intimacy = await adjust_intimacy(user_id, total_change)
    return intimacy, total_change


async def generate_tts(bot_reply: str) -> str | None:
    try:
        return await synthesize_with_translation(bot_reply)
    except Exception as e:
        logger.error(f"TTS 生成失敗：{e}")
        return None
    