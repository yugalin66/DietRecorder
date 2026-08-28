from tests.conftest import get_text_from_reply
from src.diet_manager import diet_manager

def test_full_meal_sequence(db_session):
    user_id = "user_test_seq"
    diet_manager.process_text_message(db_session, user_id, "設定體重 70kg -> 65kg")

    # 1. Ask for breakfast recommendation or send first message
    reply_bk_ask = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "早安，請問早餐吃什麼？"))
    assert "早餐建議" in reply_bk_ask

    # 2. Record Breakfast
    reply_bk = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "我早餐吃了一份鮪魚蛋吐司和一杯無糖拿鐵"))
    assert "早餐紀錄成功" in reply_bk
    assert "【今日熱量與三大營養素進度】" in reply_bk
    assert "午餐建議" in reply_bk

    # 3. Record Lunch
    reply_ln = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "我午餐吃了雞腿便當加一份炒青菜"))
    assert "午餐紀錄成功" in reply_ln
    assert "【今日熱量與三大營養素進度】" in reply_ln
    assert "晚餐建議" in reply_ln

    # 4. Record Dinner
    reply_dn = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "晚餐吃煎鮭魚、地瓜跟沙拉"))
    assert "晚餐紀錄成功" in reply_dn
    assert "總結與明日建議" in reply_dn

    # 5. Check daily status command
    reply_status = get_text_from_reply(diet_manager.process_text_message(db_session, user_id, "今日紀錄"))
    assert "熱量" in reply_status or "營養評估" in reply_status

