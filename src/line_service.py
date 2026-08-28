import logging
import requests
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    ShowLoadingAnimationRequest
)
from src.config import settings

logger = logging.getLogger(__name__)

class LineService:
    def __init__(self):
        self.access_token = settings.LINE_CHANNEL_ACCESS_TOKEN
        self.channel_secret = settings.LINE_CHANNEL_SECRET
        self.configuration = Configuration(access_token=self.access_token)
        self.handler = WebhookHandler(self.channel_secret) if self.channel_secret else None

    def show_loading_animation(self, user_id: str, loading_seconds: int = 60):
        """Show loading animation in user's LINE chat UI while AI processes message."""
        if not user_id or user_id.startswith("test") or user_id in ["default_user", "dummy_user"]:
            return
        
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.show_loading_animation(
                    ShowLoadingAnimationRequest(
                        chat_id=user_id,
                        loading_seconds=loading_seconds
                    )
                )
            logger.info(f"Showed loading animation ({loading_seconds}s) for user {user_id}")
        except Exception as e:
            logger.warning(f"Could not show loading animation for {user_id}: {e}")

    def reply_text(self, reply_token: str, text: str):
        """Reply text message to LINE user."""
        if not reply_token or reply_token.startswith("dummy"):
            logger.info(f"[LINE Reply Mock] ReplyToken: {reply_token}\nText: {text}")
            return
        
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=text)]
                    )
                )
            logger.info(f"Successfully sent reply to reply_token {reply_token[:10]}...")
        except Exception as e:
            logger.error(f"Failed to reply LINE message: {e}", exc_info=True)

    def reply_text_and_flex(self, reply_token: str, text: str, alt_text: str, flex_dict: dict):
        """Reply both text and Flex Message card to LINE user."""
        if not reply_token or reply_token.startswith("dummy"):
            logger.info(f"[LINE Mock Reply] ReplyToken: {reply_token}\nText: {text}\nFlex AltText: {alt_text}")
            return
        
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                flex_msg = FlexMessage(
                    alt_text=alt_text,
                    contents=FlexContainer.from_dict(flex_dict)
                )
                messages = []
                if text and text.strip():
                    messages.append(TextMessage(text=text.strip()))
                messages.append(flex_msg)

                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages
                    )
                )
            logger.info(f"Successfully sent text & Flex Message reply to {reply_token[:10]}...")
        except Exception as e:
            logger.error(f"Failed to send Flex Message reply: {e}", exc_info=True)
            fallback_text = f"{text}\n\n【{alt_text}】" if text else alt_text
            self.reply_text(reply_token, fallback_text)

    def push_text(self, user_id: str, text: str):
        """Push text message to LINE user."""
        if not user_id:
            logger.warning("push_text called without user_id")
            return
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=text)]
                    )
                )
            logger.info(f"Successfully pushed message to {user_id}")
        except Exception as e:
            logger.error(f"Failed to push LINE message to {user_id}: {e}", exc_info=True)

    def push_text_and_flex(self, user_id: str, text: str, alt_text: str, flex_dict: dict):
        """Push both text and Flex Message card to LINE user."""
        if not user_id:
            logger.warning("push_text_and_flex called without user_id")
            return
        
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                flex_msg = FlexMessage(
                    alt_text=alt_text,
                    contents=FlexContainer.from_dict(flex_dict)
                )
                messages = []
                if text and text.strip():
                    messages.append(TextMessage(text=text.strip()))
                messages.append(flex_msg)

                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=messages
                    )
                )
            logger.info(f"Successfully pushed text & Flex Message to {user_id}")
        except Exception as e:
            logger.error(f"Failed to push Flex Message: {e}", exc_info=True)
            fallback_text = f"{text}\n\n【{alt_text}】" if text else alt_text
            self.push_text(user_id, fallback_text)

    def get_user_profile(self, user_id: str) -> str:
        """Fetch LINE user display name."""
        if not user_id or user_id.startswith("test") or user_id in ["default_user", "dummy_user"]:
            return "夥伴"
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                profile = line_bot_api.get_profile(user_id)
                if profile and profile.display_name:
                    return profile.display_name
        except Exception as e:
            logger.warning(f"Could not fetch LINE profile for {user_id}: {e}")
        return "夥伴"

    def get_message_content(self, message_id: str) -> bytes | None:
        """Download binary content (photo) of a LINE message directly."""
        if not message_id or message_id.startswith("test"):
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                logger.info(f"Successfully downloaded image content for message_id {message_id} ({len(res.content)} bytes)")
                return res.content
            logger.error(f"Failed to download message_id {message_id}, status: {res.status_code}, response: {res.text}")
            return None
        except Exception as e:
            logger.error(f"Error fetching content for message_id {message_id}: {e}", exc_info=True)
            return None

line_service = LineService()
