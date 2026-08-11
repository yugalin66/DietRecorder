from src.diet_manager import diet_manager

def test_user_creation(db_session):
    user = diet_manager.get_or_create_user(db_session, "user_123")
    assert user.user_id == "user_123"
    assert user.current_weight == 70.0
    assert user.target_weight == 65.0
