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

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

handler = WebhookHandler(settings.LINE_CHANNEL_SECRET) if settings.LINE_CHANNEL_SECRET else None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    yield

app = FastAPI(title="阿肌師 API", version="1.0.0", lifespan=lifespan)

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "阿肌師"}

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

from src.diet_manager import (
    diet_manager,
    build_exercise_list_flex,
    build_exercise_select_flex,
    build_exercise_duration_flex,
    build_workout_days_select_flex
)

def async_process_event(ev: dict):
    db = SessionLocal()
    try:
        user_id = ev.get("source", {}).get("userId", "default_user")
        reply_token = ev.get("replyToken")
        ev_type = ev.get("type")
        msg = ev.get("message", {})
        msg_type = msg.get("type")

        logger.info(f"[Async Job] Processing event for user {user_id}, ev_type: {ev_type}, msg_type: {msg_type}")

        # 0. Handle Follow (Add Friend) Events
        if ev_type == "follow":
            logger.info(f"[Async Job] User {user_id} followed 阿肌師.")
            diet_manager.get_or_create_user(db, user_id)
            return

        # 1. Handle Postback Events (Exercise list add/remove & exercise select/duration)
        if ev_type == "postback":
            postback_data = ev.get("postback", {}).get("data", "")
            logger.info(f"[Async Job] Postback data for user {user_id}: {postback_data}")
            params = dict(q.split("=") for q in postback_data.split("&") if "=" in q)
            action = params.get("action")
            name = params.get("name", "")

            user = diet_manager.get_or_create_user(db, user_id)

            if action == "add_exercise":
                ok, notice = diet_manager.add_user_preferred_exercise(db, user, name)
                flex_card, alt_text = build_exercise_list_flex(user)
                line_service.reply_text_and_flex(reply_token, notice, alt_text, flex_card)
            elif action == "remove_exercise":
                ok, notice = diet_manager.remove_user_preferred_exercise(db, user, name)
                flex_card, alt_text = build_exercise_list_flex(user)
                line_service.reply_text_and_flex(reply_token, notice, alt_text, flex_card)
            elif action == "custom_exercise_prompt":
                diet_manager.user_pending_actions[user_id] = "awaiting_custom_exercise"
                line_service.reply_text(reply_token, "✍️ 請直接傳送您想新增的自訂運動項目名稱（例如：攀岩、拳擊、皮拉提斯、划船機）：")
            elif action == "select_workout_days":
                flex_card, alt_text = build_workout_days_select_flex(user)
                line_service.reply_text_and_flex(reply_token, "請選擇您每週預計的運動天數：", alt_text, flex_card)
            elif action == "set_workout_days":
                days = int(params.get("days", "3"))
                user.workout_days = days
                db.commit()
                flex_card, alt_text = build_exercise_list_flex(user)
                line_service.reply_text_and_flex(reply_token, f"✅ 已成功將每週運動天數更新為【{days} 天】！", alt_text, flex_card)
            elif action == "select_exercise":
                flex_card, alt_text = build_exercise_duration_flex(name)
                line_service.reply_text_and_flex(reply_token, f"您選擇了【{name}】！請問進行了多久時間呢？", alt_text, flex_card)
            elif action == "select_duration":
                duration = params.get("min", "30")
                res = diet_manager.process_exercise_message(db, user_id, None, f"{name} {duration} 分鐘")
                line_service.reply_text(reply_token, res)
            return

        # 2. Handle Message Events (Text & Image)
        if msg_type in ["text", "image"]:
            line_service.show_loading_animation(user_id, loading_seconds=30)

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
                # Try food recognition first
                food_res = diet_manager.process_image_message(db, user_id, img_bytes)
                
                # If food analysis determined it's NOT food, fallback to test if it's an exercise photo
                if isinstance(food_res, str) and "未能在此照片中辨識出明確的食物" in food_res:
                    ex_res = diet_manager.process_exercise_message(db, user_id, img_bytes)
                    if isinstance(ex_res, str) and "未能在此照片/訊息中辨識出明確的運動紀錄" not in ex_res:
                        line_service.reply_text(reply_token, ex_res)
                        return

                if isinstance(food_res, tuple):
                    reply_text_msg, flex_dict, alt_text = food_res
                    line_service.reply_text_and_flex(reply_token, reply_text_msg, alt_text, flex_dict)
                else:
                    line_service.reply_text(reply_token, food_res)
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
