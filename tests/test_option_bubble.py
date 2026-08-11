from src.diet_manager import build_option_bubble

def test_option_bubble_footer_removed():
    bubble = build_option_bubble("lunch", {"title": "測試餐點", "calories": "500 kcal"})
    assert "footer" not in bubble
