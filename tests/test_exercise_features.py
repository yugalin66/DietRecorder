from src.diet_manager import diet_manager
from tests.conftest import get_text_from_reply

def test_exercise_list_command(db_session):
    user_id = "u_ex_list"
    user = diet_manager.get_or_create_user(db_session, user_id)
    res = diet_manager.process_text_message(db_session, user_id, "運動清單")
    assert isinstance(res, tuple)
    text_msg, flex_dict, alt_text = res
    assert "運動偏好與天數管理" in text_msg or "運動清單" in alt_text
    assert flex_dict.get("type") == "bubble"

def test_exercise_recommendation_command(db_session, monkeypatch):
    from src.gemini_service import gemini_service
    monkeypatch.setattr(gemini_service, "suggest_workout_recommendation", lambda *args, **kwargs: "🏋️‍♂️【阿肌師週計畫運動推薦】\n今日訓練：深蹲 12下3組")

    user_id = "u_ex_rec"
    user = diet_manager.get_or_create_user(db_session, user_id)
    res = diet_manager.process_text_message(db_session, user_id, "運動")
    text_msg = res[0] if isinstance(res, tuple) else res
    assert "運動推薦" in text_msg
    assert "深蹲" in text_msg

def test_single_exercise_duration_prompt(db_session):
    user_id = "u_ex_dur"
    res = diet_manager.process_text_message(db_session, user_id, "慢跑")
    assert isinstance(res, tuple)
    text_msg, flex_dict, alt_text = res
    assert "慢跑" in text_msg
    assert "多久時間" in text_msg

def test_exercise_recording_text(db_session, monkeypatch):
    from src.gemini_service import gemini_service
    monkeypatch.setattr(gemini_service, "analyze_exercise", lambda *args, **kwargs: {
        "is_exercise": True,
        "exercise_name": "慢跑",
        "duration_minutes": 30,
        "calories_burned": 220,
        "summary": "很棒的慢跑！"
    })

    user_id = "u_ex_log"
    res = diet_manager.process_text_message(db_session, user_id, "慢跑 30分鐘")
    text_msg = res[0] if isinstance(res, tuple) else res
    assert "運動打卡成功" in text_msg
    assert "慢跑" in text_msg
    assert "220" in text_msg

    log = diet_manager.get_or_create_daily_log(db_session, user_id)
    assert log.total_exercise_calories == 220.0
    assert len(log.exercises) == 1

def test_add_remove_exercise_preference(db_session):
    user_id = "u_ex_pref"
    user = diet_manager.get_or_create_user(db_session, user_id)

    ok, msg = diet_manager.add_user_preferred_exercise(db_session, user, "羽毛球")
    assert ok is True
    prefs = diet_manager.get_user_preferred_exercises(user)
    assert "羽毛球" in prefs

    ok2, msg2 = diet_manager.remove_user_preferred_exercise(db_session, user, "羽毛球")
    assert ok2 is True
    prefs2 = diet_manager.get_user_preferred_exercises(user)
    assert "羽毛球" not in prefs2

def test_meal_summary_includes_workout_recommendation_if_no_exercise(db_session, monkeypatch):
    from src.gemini_service import gemini_service
    monkeypatch.setattr(gemini_service, "suggest_next_meal", lambda *args, **kwargs: {"intro_summary": "午餐建議", "options": []})
    monkeypatch.setattr(gemini_service, "suggest_workout_recommendation", lambda *args, **kwargs: "🏋️‍♂️【阿肌師週計畫運動推薦】\n今日計劃訓練：【深蹲 12下3組】")

    user_id = "u_meal_no_ex"
    user = diet_manager.get_or_create_user(db_session, user_id)
    log = diet_manager.get_or_create_daily_log(db_session, user_id)
    analysis = {"food_name": "蛋餅", "calories": 300, "protein": 15, "carbs": 30, "fat": 10, "summary": "好吃"}

    res = diet_manager._record_meal_and_respond(db_session, user, log, analysis)
    text_msg = res[0] if isinstance(res, tuple) else res
    assert "【阿肌師週計畫運動推薦】" in text_msg
    assert "深蹲 12下3組" in text_msg

def test_meal_summary_omits_workout_recommendation_if_already_exercised(db_session, monkeypatch):
    from src.gemini_service import gemini_service
    from src.models import ExerciseRecord
    monkeypatch.setattr(gemini_service, "suggest_next_meal", lambda *args, **kwargs: {"intro_summary": "午餐建議", "options": []})

    user_id = "u_meal_has_ex"
    user = diet_manager.get_or_create_user(db_session, user_id)
    log = diet_manager.get_or_create_daily_log(db_session, user_id)

    # Add an exercise record first
    ex = ExerciseRecord(daily_log_id=log.id, user_id=user_id, exercise_type="慢跑", duration_minutes=30, calories_burned=200)
    db_session.add(ex)
    db_session.commit()
    db_session.refresh(log)

    analysis = {"food_name": "蛋餅", "calories": 300, "protein": 15, "carbs": 30, "fat": 10, "summary": "好吃"}
    res = diet_manager._record_meal_and_respond(db_session, user, log, analysis)
    text_msg = res[0] if isinstance(res, tuple) else res
    assert "【阿肌師週計畫運動推薦】" not in text_msg
