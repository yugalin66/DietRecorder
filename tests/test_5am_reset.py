from datetime import datetime
from zoneinfo import ZoneInfo
from src.diet_manager import get_current_diet_date, diet_manager
from tests.conftest import get_text_from_reply

def test_get_current_diet_date_5am_rollover():
    # 1. 04:59:59 should count as previous day
    dt_before_5am = datetime(2026, 8, 28, 4, 59, 59, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_before_5am) == "2026-08-27"

    # 2. 05:00:00 should start new day
    dt_at_5am = datetime(2026, 8, 28, 5, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_at_5am) == "2026-08-28"

    # 3. 12:00:00 should be the same day
    dt_noon = datetime(2026, 8, 28, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_noon) == "2026-08-28"

    # 4. 23:59:59 should be the same day
    dt_night = datetime(2026, 8, 28, 23, 59, 59, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_night) == "2026-08-28"

    # 5. Next day 03:00:00 (late night snack) still belongs to 2026-08-28
    dt_next_late = datetime(2026, 8, 29, 3, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_next_late) == "2026-08-28"

    # 6. Next day 05:00:00 rolls over to 2026-08-29
    dt_next_5am = datetime(2026, 8, 29, 5, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert get_current_diet_date(dt_next_5am) == "2026-08-29"

def test_daily_log_5am_starts_fresh_from_breakfast(db_session):
    user_id = "user_5am_test"
    user = diet_manager.get_or_create_user(db_session, user_id)

    # Yesterday's log
    yesterday_log = diet_manager.get_or_create_daily_log(db_session, user_id, date_str="2026-08-27")
    yesterday_log.breakfast_completed = True
    yesterday_log.lunch_completed = True
    yesterday_log.dinner_completed = True
    yesterday_log.total_calories = 1950.0
    db_session.commit()

    # Today's log (at 5:00 AM)
    today_log = diet_manager.get_or_create_daily_log(db_session, user_id, date_str="2026-08-28")
    assert today_log.breakfast_completed is False
    assert today_log.lunch_completed is False
    assert today_log.dinner_completed is False
    assert today_log.total_calories == 0.0
    assert len(today_log.meals) == 0

def test_manual_reset_command(db_session):
    user_id = "user_manual_reset"
    diet_manager.process_text_message(db_session, user_id, "設定體重 70kg -> 65kg")

    # Record breakfast
    diet_manager.process_text_message(db_session, user_id, "我早餐吃了鮪魚蛋吐司")
    log = diet_manager.get_or_create_daily_log(db_session, user_id)
    assert log.breakfast_completed is True
    assert log.total_calories > 0
    assert len(log.meals) > 0

    # Reset
    reply_reset = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "重置今日飲食"))
    assert "今日飲食紀錄已重置" in reply_reset
    assert "早餐" in reply_reset

    # Check that log is reset
    log_after = diet_manager.get_or_create_daily_log(db_session, user_id)
    assert log_after.breakfast_completed is False
    assert log_after.lunch_completed is False
    assert log_after.dinner_completed is False
    assert log_after.total_calories == 0.0
    assert len(log_after.meals) == 0
