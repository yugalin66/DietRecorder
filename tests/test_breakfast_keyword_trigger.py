from tests.conftest import get_text_from_reply
from src.diet_manager import diet_manager

def test_breakfast_keyword_trigger(db_session):
    user_id = "user_breakfast_kw"
    # Send "早餐" when breakfast not completed
    reply = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "早餐"))
    assert "早餐建議" in reply
    log = diet_manager.get_or_create_daily_log(db_session, user_id)
    # Ensure breakfast was NOT falsely marked as completed with 0 calories
    assert log.breakfast_completed is False
    assert len(log.meals) == 0

    # Record breakfast properly
    diet_manager.process_text_message(db_session, user_id, "我早餐吃了鮪魚蛋吐司")
    assert log.breakfast_completed is True

    # Send "早餐" again after breakfast is completed
    reply_after = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "早餐"))
    assert "已紀錄完成" in reply_after
