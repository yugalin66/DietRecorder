from src.diet_manager import diet_manager

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
