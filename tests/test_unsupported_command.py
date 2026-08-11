from src.diet_manager import diet_manager

def test_unsupported_command_and_help(db_session):
    user_id = "user_help_test"
    # 1. /help command
    reply_help = diet_manager.process_text_message(db_session, user_id, "/help")
    assert "使用說明" in reply_help
    assert "個人目標與體重設定" in reply_help

    # 2. Unsupported slash command like /unknown
    reply_unsupported = diet_manager.process_text_message(db_session, user_id, "/unknown")
    assert "使用說明" in reply_unsupported
