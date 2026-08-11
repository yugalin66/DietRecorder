import pytest
from PIL import Image
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models import User, DailyLog, MealRecord
from src.diet_manager import diet_manager

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def get_text_from_reply(res):
    if isinstance(res, tuple):
        reply_text, flex_dict, alt_text = res
        return f"{reply_text}\n{alt_text}"
    return res

def test_user_creation(db_session):
    user = diet_manager.get_or_create_user(db_session, "user_123")
    assert user.user_id == "user_123"
    assert user.current_weight == 70.0
    assert user.target_weight == 65.0

def test_profile_setup(db_session):
    reply = get_text_from_reply(diet_manager.process_text_message(db_session, "user_123", "我目前 75 公斤，目標想減到 68 公斤"))
    assert "個人飲食目標已更新" in reply
    user = diet_manager.get_or_create_user(db_session, "user_123")
    assert user.current_weight == 75.0
    assert user.target_weight == 68.0
    assert user.daily_calorie_target > 0

def test_full_meal_sequence(db_session):
    user_id = "user_test_seq"
    diet_manager.process_text_message(db_session, user_id, "設定體重 70kg -> 65kg")

    # 1. Ask for breakfast recommendation or send first message
    reply_bk_ask = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "早安，請問早餐吃什麼？"))
    assert "早餐建議" in reply_bk_ask

    # 2. Record Breakfast
    reply_bk = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "我早餐吃了一份鮪魚蛋吐司和一杯無糖拿鐵"))
    assert "早餐紀錄成功" in reply_bk
    assert "午餐建議" in reply_bk

    # 3. Record Lunch
    reply_ln = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "我午餐吃了雞腿便當加一份炒青菜"))
    assert "午餐紀錄成功" in reply_ln
    assert "晚餐建議" in reply_ln

    # 4. Record Dinner
    reply_dn = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "晚餐吃煎鮭魚、地瓜跟沙拉"))
    assert "晚餐紀錄成功" in reply_dn
    assert "總結與明日建議" in reply_dn

    # 5. Check daily status command
    reply_status = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "/status"))
    assert "今日飲食紀錄總覽" in reply_status
    assert "熱量攝取" in reply_status

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

def test_unsupported_command_and_help(db_session):
    user_id = "user_help_test"
    # 1. /help command
    reply_help = diet_manager.process_text_message(db_session, user_id, "/help")
    assert "使用說明" in reply_help
    assert "個人目標與體重設定" in reply_help

    # 2. Unsupported slash command like /unknown
    reply_unsupported = diet_manager.process_text_message(db_session, user_id, "/unknown")
    assert "使用說明" in reply_unsupported

def test_option_bubble_footer_removed():
    from src.diet_manager import build_option_bubble
    bubble = build_option_bubble("lunch", {"title": "測試餐點", "calories": "500 kcal"})
    assert "footer" not in bubble

def test_meal_summary_nutrient_format(db_session, monkeypatch):
    from src.gemini_service import gemini_service
    monkeypatch.setattr(gemini_service, "suggest_next_meal", lambda *args, **kwargs: {"intro_summary": "建議", "options": []})
    
    user_id = "user_nutrient_test"
    user = diet_manager.get_or_create_user(db_session, user_id)
    log = diet_manager.get_or_create_daily_log(db_session, user_id)
    analysis = {
        "food_name": "雞胸肉便當",
        "calories": 500,
        "protein": 40,
        "carbs": 50,
        "fat": 10,
        "summary": "營養均衡"
    }
    res = diet_manager._record_meal_and_respond(db_session, user, log, analysis)
    summary_text = res[0] if isinstance(res, tuple) else res
    assert "📊 營養素：" in summary_text
    assert "• 蛋白質：40.0g (" in summary_text
    assert "• 碳水化合物：50.0g (" in summary_text
    assert "• 脂肪：10.0g (" in summary_text
    assert "%" in summary_text

if __name__ == "__main__":
    pytest.main(["-v", __file__])
