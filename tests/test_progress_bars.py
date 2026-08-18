from src.models import User, DailyLog
from src.diet_manager import build_4_progress_bars

def test_progress_bars_remaining():
    user = User(
        user_id="u_rem",
        daily_calorie_target=2000,
        target_carbs=250.0,
        target_protein=125.0,
        target_fat=55.0
    )
    log = DailyLog(
        user_id="u_rem",
        total_calories=1500.0,
        total_carbs=200.0,
        total_protein=100.0,
        total_fat=40.0
    )
    res = build_4_progress_bars(log, user)
    assert "剩餘 500 kcal" in res
    assert "剩餘 50.0 g" in res
    assert "剩餘 25.0 g" in res
    assert "剩餘 15.0 g" in res
    assert "(75%)" in res

def test_progress_bars_exceeded():
    user = User(
        user_id="u_exceeded",
        daily_calorie_target=1800,
        target_carbs=200.0,
        target_protein=100.0,
        target_fat=50.0
    )
    log = DailyLog(
        user_id="u_exceeded",
        total_calories=1825.0,
        total_carbs=205.0,
        total_protein=110.0,
        total_fat=52.5
    )
    res = build_4_progress_bars(log, user)
    assert "超過 25 kcal" in res
    assert "超過 5.0 g" in res
    assert "超過 10.0 g" in res
    assert "超過 2.5 g" in res
    assert "(101%)" in res
