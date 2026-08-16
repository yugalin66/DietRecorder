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

    def analyze_exercise(self, image_bytes: bytes | None = None, text_description: str | None = None) -> dict:
        """Analyze exercise photo (watch screenshot/gym screen) and/or text description."""
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
                logger.error(f"Failed to process/compress exercise image bytes: {e}")

        prompt = f"""
你是一個頂尖AI運動教練與臨床體能評估師。請評估照片與/或文字描述中的運動打卡內容。

重要規則：
1. 請先判斷此照片/描述是否屬於「運動、健身、訓練、跑步、散步、運動手錶/App螢幕截圖或健身器材」（is_exercise）。
   - 若非運動相關，將 is_exercise 設為 false！
   - 若包含任何運動或訓練紀錄，將 is_exercise 設為 true！

2. 若 is_exercise 為 true：
   - 識別運動名稱 exercise_name (例如 "慢跑", "重量訓練", "槓鈴臥推", "游泳", "散步", "腳踏車")
   - 運動種類 category: "aerobic" (有氧) 或 "anaerobic" (無氧/重訓)
   - 估算運動時間 duration_minutes (分鐘數字，若無法確定給予 30)
   - 估算消耗熱量 calories_burned (kcal數字，若文字/照片有明確標示熱量請優先採用標示數字)
   - 給予一句專業短評 summary (例如: "槓鈴臥推能強化胸大肌與上肢力量，做得好！")

用戶描述："{text_description or '請分析這張運動照片'}"

請嚴格輸出合法 JSON 格式：
{{
  "is_exercise": true,
  "exercise_name": "慢跑",
  "category": "aerobic",
  "duration_minutes": 30,
  "calories_burned": 220,
  "summary": "慢跑是非常棒的有氧心肺訓練，有助於脂肪燃燒與維護心血管健康！"
}}
"""
        try:
            raw_res = self._call_gemini(prompt, image=pil_image)
            cleaned = re.sub(r"^```json\s*", "", raw_res, flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Failed to analyze exercise with Gemini: {e}")
            return {
                "is_exercise": True,
                "exercise_name": text_description or "體能訓練",
                "category": "aerobic",
                "duration_minutes": 30,
                "calories_burned": 150.0,
                "summary": "已為您記錄運動項目，持之以恆有助於提高代謝與體能！"
            }

    def generate_day_summary(
        self,
        user_name: str,
        user_info: dict,
        total_consumed: dict,
        meal_records: list[dict],
        exercise_records: list[dict] | None = None,
        preferred_exercises: list[str] | None = None
    ) -> str:
        """Generate final end-of-day summary and advice including exercise assessment."""
        daily_target = user_info.get("daily_calorie_target", 1800)
        cals_in = total_consumed.get("calories", 0)
        ex_burned = total_consumed.get("exercise_calories", 0)
        net_cals = max(0, cals_in - ex_burned)
        cal_pct = round((net_cals / daily_target) * 100) if daily_target else 0
        workout_days = user_info.get("workout_days", 3)
        curr_w = user_info.get("current_weight", 70.0)
        targ_w = user_info.get("target_weight", 65.0)

        # Weight goal classification
        if targ_w < curr_w:
            weight_goal_desc = f"減重燃脂 (當前 {curr_w}kg -> 目標 {targ_w}kg)"
        elif targ_w > curr_w:
            weight_goal_desc = f"增肌重訓 (當前 {curr_w}kg -> 目標 {targ_w}kg)"
        else:
            weight_goal_desc = f"體能維持 (當前與目標均為 {curr_w}kg)"

        meals_text = "\n".join([
            f"- [{m.get('meal_type', '').upper()}] {m.get('food_description')}: {m.get('calories')} kcal"
            for m in meal_records
        ]) or "無"

        exercises_text = "\n".join([
            f"- {e.get('exercise_type')}: {e.get('duration_minutes', 0)} min (-{e.get('calories_burned')} kcal)"
            for e in (exercise_records or [])
        ]) if exercise_records else "今日尚未記錄運動"

        # Sanitize preferred exercises list (filter out old "重量訓練")
        filtered_prefs = [p for p in (preferred_exercises or ["慢跑", "游泳", "散步", "腳踏車"]) if p != "重量訓練"]
        pref_str = ", ".join(filtered_prefs) if filtered_prefs else "慢跑, 游泳, 散步, 腳踏車"

        prompt = f"""
你是一位專業且熱情的個人健身教練 (Personal Fitness Coach) 與營養師。請為學員「{user_name}」撰寫【極精簡的一日飲食與運動教練評估】。

教練指導與硬性要求：
1. 必須直接稱呼「{user_name}」，絕對禁止出現 [用戶姓名] 等括號填空字眼！
2. 絕對禁止使用 Markdown 粗體語法 (如 **文字**)。
3. 請考量學員的體重目標（{weight_goal_desc}）與每週預計運動天數（每週 {workout_days} 天），結合今日飲食熱量狀況進行整體評估。
4. 運動推薦硬性格式：從學員偏好運動清單 ({pref_str}) 中挑選 1 項推薦。推薦時【除了運動項目之外，必須同時建議具體的時間或幾下幾組】！
   - 例如有氧/跑步類：建議格式為「跑步 30分鐘」或「散步 40分鐘」或「腳踏車 45分鐘」。
   - 例如重訓/力量類：建議格式為「臥推 10下3組」或「深蹲 15下3組」或「二頭肌彎舉 12下3組」。
5. 避免重複：參考學員今日已做運動 ({exercises_text})，請推薦不同於今日已做項目的運動，保持運動多樣性與輪替。

學員數據：
- 體重目標：{curr_w}kg -> {targ_w}kg ({weight_goal_desc})
- 每週運動天數設定：每週 {workout_days} 天
- 飲食攝取：{cals_in} kcal / 運動消耗：-{ex_burned} kcal / 淨熱量：{net_cals} kcal ({cal_pct}% 目標)
- 今日飲食：{meals_text}
- 今日運動：{exercises_text}

請精簡輸出以下 4 行（每行 1~2 句話）：
🌟 達標亮點：(1句精簡鼓勵)
📊 營養評估：(1句熱量與營養素狀況)
🏃 運動教練推薦：(結合每週 {workout_days} 天運動規劃與體重目標，推薦 1 項具體運動，務必包含時間或幾下幾組，例如「臥推 10下3組」或「慢跑 30分鐘」)
💡 明日建議：(1句極簡綜合改善建議)
"""
        try:
            raw_res = self._call_gemini(prompt)
            cleaned = raw_res.replace("**", "").strip()
            return cleaned
        except Exception as e:
            logger.error(f"Failed to generate day summary: {e}")
            default_pref = filtered_prefs[0] if filtered_prefs else "慢跑"
            default_rec = f"{default_pref} 30分鐘" if default_pref in ["慢跑", "散步", "游泳", "腳踏車"] else f"{default_pref} 10下3組"
            return (
                f"🌟 達標亮點：感謝您今日持續記錄飲食與運動！\n"
                f"📊 營養評估：淨熱量攝取為 {net_cals:.0f} kcal。\n"
                f"🏃 運動教練推薦：教練建議您考量每週 {workout_days} 天運動計畫，可進行【{default_rec}】保持鍛鍊強度與體能。\n"
                f"💡 明日建議：維持均衡飲食與補充電解質水份！"
            )

    def suggest_workout_recommendation(
        self,
        user_name: str,
        user_info: dict,
        today_exercises: list[dict],
        preferred_exercises: list[str]
    ) -> str:
        """Generate direct exercise recommendation from AI Personal Fitness Coach."""
        workout_days = user_info.get("workout_days", 3)
        curr_w = user_info.get("current_weight", 70.0)
        targ_w = user_info.get("target_weight", 65.0)

        if targ_w < curr_w:
            weight_goal_desc = f"減重燃脂 (當前 {curr_w}kg -> 目標 {targ_w}kg)"
        elif targ_w > curr_w:
            weight_goal_desc = f"增肌重訓 (當前 {curr_w}kg -> 目標 {targ_w}kg)"
        else:
            weight_goal_desc = f"體能維持 (當前與目標均為 {curr_w}kg)"

        filtered_prefs = [p for p in (preferred_exercises or ["慢跑", "游泳", "散步", "腳踏車"]) if p != "重量訓練"]
        pref_str = ", ".join(filtered_prefs) if filtered_prefs else "慢跑, 游泳, 散步, 腳踏車"
        done_ex_str = ", ".join([e.get("exercise_type", "") for e in today_exercises]) if today_exercises else "無"

        prompt = f"""
你是一位講求科學訓練排程與計畫性的專業個人健身教練「阿肌師」。請為學員「{user_name}」進行【有計畫性、週期結構化】的運動推薦與規劃。

教練指導與硬性要求：
1. 必須直接稱呼「{user_name}」，絕對禁止出現 [用戶姓名] 等括號填空字眼！
2. 絕對禁止使用 Markdown 粗體語法 (如 **文字**)。
3. 【計畫性與週期排程】：絕對不可隨機或單純輪替挑選！必須根據學員的【每週預計運動天數 ({workout_days} 天/週)】與【體重目標 ({weight_goal_desc})】，排定符合科學週期的訓練計畫焦點（例如：3 天計畫可排定「上肢推拉/下肢核心/有氧心肺」；5 天計畫可分拆「胸、背、腿、肩、心肺」；減重著重高熱量消耗搭配大肌群，增肌著重漸進負荷強度）。
4. 【項目精準選用】：從學員的偏好運動清單 ({pref_str}) 中，評估並精確挑選出最符合【今日計劃焦點】的 1 個項目。
5. 【具體數據規格】：推薦的項目必須標示【具體時間】或【幾下幾組與強度規格】！
   - 例如：「臥推 10下3組」、「慢跑 30分鐘 (保持配速與微喘強度)」、「深蹲 12下3組」、「腳踏車 40分鐘」。
6. 【說明計畫邏輯】：極簡說明（字數嚴格限制在 10~20 字以內，精準指出訓練好處，絕對不要長篇大論）。

學員當前規劃數據：
- 體重目標與需求：{weight_goal_desc}
- 每週運動天數設定：每週 {workout_days} 天
- 偏好運動選單庫：{pref_str}
- 今日已記錄運動：{done_ex_str}

請嚴格格式化輸出以下內容：
🏋️‍♂️【阿肌師週計畫運動推薦】
----------------------------
🎯 今日計劃訓練：【項目名稱與時間/組數強度】
📋 週計畫定位：(說明在每週 {workout_days} 天計劃中的訓練重點與分類)
💪 教練計畫說明：(極簡10~20字說明，例如：有助於增強核心力量與大肌群肌耐力)
"""
        try:
            raw_res = self._call_gemini(prompt)
            return raw_res.replace("**", "").strip()
        except Exception as e:
            logger.error(f"Failed to generate workout recommendation: {e}")
            default_pref = filtered_prefs[0] if filtered_prefs else "慢跑"
            default_rec = f"{default_pref} 30分鐘" if default_pref in ["慢跑", "散步", "游泳", "腳踏車"] else f"{default_pref} 10下3組"
            return (
                f"🏋️‍♂️【阿肌師週計畫運動推薦】\n"
                f"----------------------------\n"
                f"🎯 今日計劃訓練：【{default_rec}】\n"
                f"📋 週計畫定位：每週 {workout_days} 天週期訓練計畫排程\n"
                f"💪 教練計畫說明：有效提升心肺耐力與全身基礎代謝！"
            )

gemini_service = GeminiService()

