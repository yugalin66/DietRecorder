import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError

from src.config import settings
from src.database import init_db, get_db, SessionLocal
from src.diet_manager import diet_manager
from src.line_service import line_service
from src.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

handler = WebhookHandler(settings.LINE_CHANNEL_SECRET) if settings.LINE_CHANNEL_SECRET else None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting scheduler...")
    start_scheduler()
    yield
    logger.info("Stopping scheduler...")
    stop_scheduler()

app = FastAPI(title="DietBot API", version="1.0.0", lifespan=lifespan)

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "DietBot"}

class DirectMessageRequest(BaseModel):
    user_id: str = "test_user_1"
    text: str | None = None

@app.post("/api/chat")
def direct_chat(req: DirectMessageRequest, db: Session = Depends(get_db)):
    """REST endpoint to simulate text chat directly for testing."""
    if not req.text:
        raise HTTPException(status_code=400, detail="Text is required")
    res = diet_manager.process_text_message(db, req.user_id, req.text)
    if isinstance(res, tuple):
        reply_text_msg, flex_dict, alt_text = res
        return {"reply": reply_text_msg, "flex_card": flex_dict, "alt_text": alt_text}
    return {"reply": res}

def async_process_event(ev: dict):
    db = SessionLocal()
    try:
        user_id = ev.get("source", {}).get("userId", "default_user")
        reply_token = ev.get("replyToken")
        msg = ev.get("message", {})
        msg_type = msg.get("type")

        logger.info(f"[Async Job] Processing event for user {user_id}, msg_type: {msg_type}")

        if msg_type == "text":
            text = msg.get("text", "")
            res = diet_manager.process_text_message(db, user_id, text)
            if isinstance(res, tuple):
                reply_text_msg, flex_dict, alt_text = res
                line_service.reply_text_and_flex(reply_token, reply_text_msg, alt_text, flex_dict)
            else:
                line_service.reply_text(reply_token, res)
        elif msg_type == "image":
            msg_id = msg.get("id")
            img_bytes = line_service.get_message_content(msg_id)
            if img_bytes:
                res = diet_manager.process_image_message(db, user_id, img_bytes)
                if res is None:
                    logger.info(f"[Async Job] Non-food image detected for {user_id}.")
                    line_service.reply_text(reply_token, "📷 辨識提醒：未能從照片中辨識到食物內容，請嘗試上傳清晰的食物照片，或用文字輸入餐點打卡！")
                elif isinstance(res, tuple):
                    reply_text_msg, flex_dict, alt_text = res
                    line_service.reply_text_and_flex(reply_token, reply_text_msg, alt_text, flex_dict)
                else:
                    line_service.reply_text(reply_token, res)
            else:
                logger.error(f"[Async Job] Failed to retrieve image bytes for msg_id {msg_id}")
                line_service.reply_text(reply_token, "⚠️ 抱歉，照片讀取失敗，請重新上傳一次喔！")
    except Exception as e:
        logger.error(f"[Async Job] Error processing event {ev}: {e}", exc_info=True)
        reply_token = ev.get("replyToken")
        if reply_token:
            try:
                line_service.reply_text(reply_token, "⚠️ 抱歉，系統處理您的訊息時發生暫時性錯誤，請稍後再試一次！")
            except Exception as reply_err:
                logger.error(f"[Async Job] Failed to send error reply: {reply_err}")
    finally:
        db.close()

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    if handler and settings.LINE_CHANNEL_SECRET:
        try:
            handler.parser.parse(body_str, signature)
        except InvalidSignatureError:
            logger.warning("Invalid LINE signature received on webhook.")
        except Exception as e:
            logger.warning(f"Signature check exception: {e}")

    try:
        data = json.loads(body_str)
        events = data.get("events", [])
        for ev in events:
            background_tasks.add_task(async_process_event, ev)
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {e}", exc_info=True)

    return "OK"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
