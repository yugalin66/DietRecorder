import json
import logging
import re
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from src.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.keys = settings.get_gemini_keys()
        self.models = settings.get_gemini_models()

    def _call_gemini(self, prompt: str, image: Image.Image | None = None) -> str:
        """Call Gemini API with automatic key and model fallback."""
        if not self.keys:
            raise ValueError("No Gemini API keys found in settings!")

        last_exception = None
        for model in self.models:
            for api_key in self.keys:
                try:
                    client = genai.Client(api_key=api_key)
                    contents = []
                    if image:
                        contents.append(image)
                    contents.append(prompt)

                    response = client.models.generate_content(
                        model=model,
                        contents=contents
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception as e:
                    logger.warning(f"Gemini call failed with key {api_key[:8]}... and model {model}: {e}")
                    last_exception = e
                    continue

        raise RuntimeError(f"All Gemini API keys and models failed. Last error: {last_exception}")

    def parse_user_weight_goal(self, text: str) -> dict:
        """Parse natural language user weight & target setting."""
        prompt = f"""
你是一個專業的營養師與健康數據解析助手。請分析用戶輸入的文字內容，萃取出以下數據：
- 當前體重 current_weight (kg)
- 目標體重 target_weight (kg)
- 身高 height (cm，若未提及請設為 170.0)
- 年齡 age (歲，若未提及請設為 30)
- 性別 gender ('male' / 'female' / 'unknown')

根據以上數值計算：
- BMR (基礎代謝率) 與 TDEE (每日總熱量消耗)
- 若目標體重 < 當前體重（減重），每日目標熱量為 TDEE - 400 ~ 500 kcal
- 若目標體重 > 當前體重（增重），每日目標熱量為 TDEE + 300 kcal
- 若無明確增減重，設為 TDEE
- 蛋白質 target_protein (g): 目標熱量的 25% (4 kcal/g)
- 碳水化合物 target_carbs (g): 目標熱量的 50% (4 kcal/g)
- 脂肪 target_fat (g): 目標熱量的 25% (9 kcal/g)

用戶輸入："{text}"

請嚴格輸出 JSON 格式，格式如下：
{{
  "current_weight": 75.0,
  "target_weight": 68.0,
  "height": 170.0,
  "age": 30,
  "gender": "male",
  "daily_calorie_target": 1850,
  "target_protein": 115.6,
  "target_carbs": 231.25,
  "target_fat": 51.4
}}
"""
        raw_res = self._call_gemini(prompt)
        cleaned = re.sub(r"^```json\s*", "", raw_res, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to parse JSON from Gemini response: {raw_res}, error: {e}")
            return {
                "current_weight": 70.0,
                "target_weight": 65.0,
                "height": 170.0,
                "age": 30,
                "gender": "unknown",
                "daily_calorie_target": 1800,
                "target_protein": 112.5,
                "target_carbs": 225.0,
                "target_fat": 50.0
            }

    def analyze_food(self, image_bytes: bytes | None = None, text_description: str | None = None) -> dict:
        """Analyze food photo and/or text description for calories & macros."""
        pil_image = None
        if image_bytes:
            try:
                img = Image.open(BytesIO(image_bytes))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                buf.seek(0)
                pil_image = Image.open(buf)
            except Exception as e:
                logger.error(f"Failed to process/compress image bytes: {e}")

        prompt = f"""
你是一個頂尖AI臨床營養師。請評估照片與/或文字描述中的內容。

重要規則：
1. 請先判斷此照片/描述是否屬於「食物、飲料、餐點或食材」（is_food）。
   - 若非食物（例如：風景、寵物、自拍、文字文件、傢俱、非食用物品），請將 is_food 設為 false！
   - 若包含任何食物或飲料，請將 is_food 設為 true！

2. 若 is_food 為 true，請仔細辨識食物種類、預估總熱量與三大營養素。

用戶描述："{text_description or '請分析這張食物照片'}"

請嚴格輸出合法 JSON 格式，包含以下欄位：
- is_food: true 或 false (布林值)
- food_name: 食物有名簡短名稱 (例如 "香煎雞腿排便當加紅茶")
- calories: 預估總熱量 (kcal, 數字)
- protein: 蛋白質 (g, 數字)
- carbs: 碳水化合物 (g, 數字)
- fat: 脂肪 (g, 數字)
- summary: 一句營養師短評與提醒 (例如: "蛋白質豐富，但油脂較多，建議多補充水分")
- items: 包含的食物品項明細列表 (格式: [{{"name": "飯", "calories": 250}}, ...])

JSON範例：
{{
  "is_food": true,
  "food_name": "烤雞胸肉沙拉與拿鐵",
  "calories": 480,
  "protein": 38.0,
  "carbs": 35.0,
  "fat": 18.0,
  "summary": "這餐高蛋白低碳水，非常符合您的減重目標！",
  "items": [
    {{"name": "烤雞胸肉 150g", "calories": 240}},
    {{"name": "綜合生菜沙拉", "calories": 90}},
    {{"name": "無糖拿鐵", "calories": 150}}
  ]
}}
"""
        try:
            raw_res = self._call_gemini(prompt, image=pil_image)
            cleaned = re.sub(r"^```json\s*", "", raw_res, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to analyze food image/text with Gemini: {e}")
            return {
                "is_food": True,
                "food_name": text_description or "綜合餐點",
                "calories": 450.0,
                "protein": 25.0,
                "carbs": 50.0,
                "fat": 15.0,
                "summary": "AI 暫時無法辨識詳細內容，已為您記錄預設熱量與營養。",
                "items": []
            }

    def suggest_next_meal(
        self,
        meal_to_suggest: str,  # 'breakfast', 'lunch', 'dinner'
        user_info: dict,
        total_consumed: dict,
        consumed_meals_summary: list[str]
    ) -> dict:
        """Generate tailored 3 meal options in structured JSON for LINE Flex Carousel cards."""
        daily_target = user_info.get("daily_calorie_target", 1800)
        rem_cal = max(0, daily_target - total_consumed.get("calories", 0))
        rem_protein = max(0, user_info.get("target_protein", 110) - total_consumed.get("protein", 0))
        rem_carbs = max(0, user_info.get("target_carbs", 220) - total_consumed.get("carbs", 0))
        rem_fat = max(0, user_info.get("target_fat", 50) - total_consumed.get("fat", 0))

        meal_name_tw = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(meal_to_suggest, "下一餐")

        prompt = f"""
你是一個專屬健康營養師。請根據用戶目標與今日剩餘熱量預算，提供【3 個具體{meal_name_tw}選項提案】。

用戶數據：
- 當前體重：{user_info.get('current_weight')} kg -> 目標體重：{user_info.get('target_weight')} kg
- 剩餘熱量預算：{rem_cal:.0f} kcal
- 剩餘蛋白質預算：{rem_protein:.1f} g
- 今日已吃：{", ".join(consumed_meals_summary) if consumed_meals_summary else "無"}

請嚴格輸出合法 JSON 格式，包含以下欄位：
- intro_summary: 總結說明的文字訊息 (如: "早上好！根據您今日剩餘的預算，為您準備了 3 個方便又均衡的早餐提案：")
- options: 3個選項的陣列，每個選項包含 (option_num, title, tag, description, calories, reason)

JSON範例：
{{
  "intro_summary": "早上好！根據您今日剩餘的熱量與蛋白質目標，為您準備了 3 個方便又均衡的早餐提案：",
  "options": [
    {{
      "option_num": "選項一",
      "title": "超商高蛋白輕食組",
      "tag": "超商族首選",
      "description": "嫩雞胸肉100g + 茶葉蛋1顆 + 無糖高纖豆漿400ml + 小番茄10顆",
      "calories": "約 380 kcal",
      "reason": "富含 45g 優質蛋白質，能帶來持久飽足感並穩定血糖。"
    }},
    {{
      "option_num": "選項二",
      "title": "外食全麥鮪魚吐司組合",
      "tag": "外食族推薦",
      "description": "全麥鮪魚蛋吐司 (不加美乃滋) + 無糖豆漿或脫脂牛奶",
      "calories": "約 400 kcal",
      "reason": "複合碳水化合物與蛋白質均衡搭配，提供充足活力。"
    }},
    {{
      "option_num": "選項三",
      "title": "居家高纖優格組合",
      "tag": "居家/辦公室",
      "description": "無糖希臘優格150g + 乳清蛋白粉1匙 + 綜合堅果10顆 + 半顆奇異果",
      "calories": "約 390 kcal",
      "reason": "高蛋白低GI，極佳的腸胃負擔與優質脂肪來源。"
    }}
  ]
}}
"""
        try:
            raw_res = self._call_gemini(prompt)
            cleaned = re.sub(r"^```json\s*", "", raw_res, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to generate or parse next meal: {e}")
            return {
                "intro_summary": f"為您提供今日【{meal_name_tw}建議】：",
                "options": [
                    {
                        "option_num": "選項一",
                        "title": f"輕盈均衡{meal_name_tw}",
                        "tag": "健康推薦",
                        "description": "高蛋白主餐 + 複合碳水 + 無糖飲料",
                        "calories": f"約 {rem_cal * 0.3:.0f} kcal",
                        "reason": "穩定血糖，補充優質蛋白質。"
                    }
                ]
            }

    def generate_day_summary(
        self,
        user_name: str,
        user_info: dict,
        total_consumed: dict,
        meal_records: list[dict]
    ) -> str:
        """Generate final end-of-day summary and advice."""
        daily_target = user_info.get("daily_calorie_target", 1800)
        cal_pct = round((total_consumed.get("calories", 0) / daily_target) * 100) if daily_target else 0

        meals_text = "\n".join([
            f"- [{m.get('meal_type', '').upper()}] {m.get('food_description')}: {m.get('calories')} kcal (P:{m.get('protein')}g, C:{m.get('carbs')}g, F:{m.get('fat')}g)"
            for m in meal_records
        ])

        prompt = f"""
你是一個極簡高效的專業營養師。請為用戶「{user_name}」撰寫一份【極精簡的一日飲食總結】。

字數與格式硬性要求：
1. 全文字數必須控制在 60~90 字內！絕對不要長篇大論！
2. 必須直接稱呼「{user_name}」，絕對禁止出現 [用戶姓名]、[你的名字]、[姓名] 等括號填空字眼！
3. 絕對禁止使用 Markdown 粗體語法 (如 **文字**)，LINE 不支援粗體，請直接寫出純文字！
4. 「明日建議」僅需【一句話極簡建議】，絕對不要分餐點建議！

用戶數據：
- 用戶：{user_name} (目標：{user_info.get('current_weight')}kg -> {user_info.get('target_weight')}kg)
- 總熱量：{total_consumed.get('calories', 0)} / {daily_target} kcal ({cal_pct}%)
- 今日已吃：{meals_text}

請精簡輸出以下 3 行（每行僅需 1 句話）：
🌟 達標亮點：(1句精簡鼓勵)
📊 營養評估：(1句營養素狀況)
💡 明日建議：(1句極簡改善建議)
"""
        try:
            raw_res = self._call_gemini(prompt)
            cleaned = raw_res.replace("**", "").strip()
            return cleaned
        except Exception as e:
            logger.error(f"Failed to generate day summary: {e}")
            return f"🌟 達標亮點：感謝您今日持續記錄飲食！\n📊 營養評估：今日熱量總攝取為 {total_consumed.get('calories', 0):.0f} kcal。\n💡 明日建議：維持均衡飲食與規律運動！"

gemini_service = GeminiService()
