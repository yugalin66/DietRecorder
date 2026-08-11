from tests.conftest import get_text_from_reply
from src.diet_manager import diet_manager

def test_profile_setup(db_session):
    reply = get_text_from_reply(diet_manager.process_text_message(db_session, "user_123", "我目前 75 公斤，目標想減到 68 公斤"))
    assert "個人飲食目標已更新" in reply
    user = diet_manager.get_or_create_user(db_session, "user_123")
    assert user.current_weight == 75.0
    assert user.target_weight == 68.0
    assert user.daily_calorie_target > 0
