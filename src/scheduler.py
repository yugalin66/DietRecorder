import logging
from apscheduler.schedulers.background import BackgroundScheduler
from src.database import SessionLocal
from src.models import User, DailyLog
from src.line_service import line_service
from src.gemini_service import gemini_service

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def send_morning_breakfast_recommendations():
    """Job to push morning breakfast recommendations to active users."""
    logger.info("Running scheduled job: send_morning_breakfast_recommendations")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            today_log = db.query(DailyLog).filter(
                DailyLog.user_id == user.user_id,
                DailyLog.log_date == DailyLog.log_date
            ).first()

            if not today_log or not today_log.breakfast_completed:
                user_profile = {
                    "current_weight": user.current_weight,
                    "target_weight": user.target_weight,
                    "daily_calorie_target": user.daily_calorie_target,
                    "target_protein": user.target_protein,
                    "target_carbs": user.target_carbs,
                    "target_fat": user.target_fat
                }
                rec = gemini_service.suggest_next_meal("breakfast", user_profile, {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}, [])
                msg = f"🌅 早上好！這是為您準備的今日【早餐建議】：\n\n{rec}\n\n吃完後記得拍照或傳文字記錄喔！"
                line_service.push_text(user.user_id, msg)
    except Exception as e:
        logger.error(f"Error in morning push job: {e}")
    finally:
        db.close()

def start_scheduler():
    # Schedule job at 07:30 AM every day
    scheduler.add_job(send_morning_breakfast_recommendations, 'cron', hour=7, minute=30, id='morning_breakfast_job')
    scheduler.start()
    logger.info("APScheduler started successfully.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped.")
