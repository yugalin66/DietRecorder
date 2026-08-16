import logging
from datetime import date, datetime
from sqlalchemy.orm import Session
from src.models import User, DailyLog, MealRecord
from src.gemini_service import gemini_service
from src.line_service import line_service

logger = logging.getLogger(__name__)

def make_progress_bar(current: float, target: float, length: int = 10) -> str:
    if target <= 0:
        return "░" * length
    pct = min(1.0, max(0.0, current / target))
    filled = int(round(pct * length))
    return "█" * filled + "░" * (length - filled)

def build_4_progress_bars(log: DailyLog, user: User) -> str:
    # 1. Calories
    cal_target = user.daily_calorie_target or 1800
    cal_pct = min(100, int((log.total_calories / cal_target) * 100))
    cal_rem = max(0, cal_target - log.total_calories)
    cal_bar = make_progress_bar(log.total_calories, cal_target)

    # 2. Carbs
    c_target = user.target_carbs or 200.0
    c_pct = min(100, int((log.total_carbs / c_target) * 100)) if c_target else 0
    c_rem = max(0, c_target - log.total_carbs)
    c_bar = make_progress_bar(log.total_carbs, c_target)

    # 3. Protein
    p_target = user.target_protein or 100.0
    p_pct = min(100, int((log.total_protein / p_target) * 100)) if p_target else 0
    p_rem = max(0, p_target - log.total_protein)
    p_bar = make_progress_bar(log.total_protein, p_target)

    # 4. Fat
    f_target = user.target_fat or 50.0
    f_pct = min(100, int((log.total_fat / f_target) * 100)) if f_target else 0
    f_rem = max(0, f_target - log.total_fat)
    f_bar = make_progress_bar(log.total_fat, f_target)

    return f"""📊 【今日熱量與三大營養素進度】
----------------------------
🔥 熱量攝取：{log.total_calories:.0f} / {cal_target} kcal ({cal_pct}%)
[{cal_bar}] 剩餘 {cal_rem:.0f} kcal

🍞 碳水化合物：{log.total_carbs:.1f} / {c_target:.1f} g ({c_pct}%)
[{c_bar}] 剩餘 {c_rem:.1f} g

🥩 蛋白質：{log.total_protein:.1f} / {p_target:.1f} g ({p_pct}%)
[{p_bar}] 剩餘 {p_rem:.1f} g

🥑 脂肪：{log.total_fat:.1f} / {f_target:.1f} g ({f_pct}%)
[{f_bar}] 剩餘 {f_rem:.1f} g"""

def build_option_bubble(meal_type: str, opt: dict) -> dict:
    bg_color = {"breakfast": "#16a34a", "lunch": "#0284c7", "dinner": "#7c3aed"}.get(meal_type, "#059669")
    option_num = opt.get("option_num", "選項")
    title = opt.get("title", "餐點提案")
    tag = opt.get("tag", "推薦")
    description = opt.get("description", "")
    calories = opt.get("calories", "")
    reason = opt.get("reason", "")

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": bg_color,
            "paddingAll": "15px",
            "contents": [
                {
                    "type": "text",
                    "text": option_num,
                    "color": "#E5E7EB",
                    "size": "xs",
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "margin": "xs",
                    "wrap": True
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "backgroundColor": "#FFFFFF",
            "contents": [
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🏷️ 標籤：",
                            "size": "xs",
                            "color": "#6B7280",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": tag,
                            "size": "xs",
                            "color": "#059669",
                            "weight": "bold",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "🍱 推薦組合：",
                    "size": "xs",
                    "color": "#9CA3AF",
                    "margin": "md",
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": description,
                    "size": "sm",
                    "color": "#1F2937",
                    "wrap": True,
                    "margin": "xs",
                    "lineSpacing": "3px"
                },
                {
                    "type": "text",
                    "text": f"🔥 預估熱量：{calories}",
                    "size": "xs",
                    "color": "#DC2626",
                    "weight": "bold",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "💡 營養師理由：",
                    "size": "xs",
                    "color": "#9CA3AF",
                    "margin": "md",
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": reason,
                    "size": "xs",
                    "color": "#4B5563",
                    "wrap": True,
                    "margin": "xs",
                    "lineSpacing": "2px"
                }
            ]
        }
    }

def build_option_carousel_card(meal_type: str, options: list[dict]) -> tuple[dict, str]:
    meal_name_tw = {"breakfast": "早餐建議", "lunch": "午餐建議", "dinner": "晚餐建議"}.get(meal_type, "餐點建議")
    bubbles = [build_option_bubble(meal_type, opt) for opt in options]
    
    carousel_dict = {
        "type": "carousel",
        "contents": bubbles
    }
    alt_text = f"【{meal_name_tw}選項卡片】"
    return carousel_dict, alt_text

def build_exercise_list_flex(user: User) -> tuple[dict, str]:
    days = getattr(user, "workout_days", 3)
    flex_card = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#059669",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "🏃‍♂️ 個人運動偏好與天數管理", "weight": "bold", "color": "#FFFFFF", "size": "lg"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": f"每週運動目標天數：{days} 天", "size": "sm", "color": "#1F2937"}
            ]
        }
    }
    return flex_card, "【個人運動清單】"

def build_workout_days_select_flex(user: User) -> tuple[dict, str]:
    flex_card = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#059669",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "設定每週運動天數", "weight": "bold", "color": "#FFFFFF", "size": "lg"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "請選擇您每週預計運動的天數：", "size": "sm", "color": "#1F2937"}
            ]
        }
    }
    return flex_card, "【設定每週運動天數】"

def build_exercise_select_flex() -> tuple[dict, str]:
    flex_card = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#059669",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": "運動項目選擇", "weight": "bold", "color": "#FFFFFF", "size": "lg"}
            ]
        }
    }
    return flex_card, "【選擇運動】"

def build_exercise_duration_flex(name: str) -> tuple[dict, str]:
    flex_card = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#059669",
            "paddingAll": "15px",
            "contents": [
                {"type": "text", "text": f"選擇【{name}】時間", "weight": "bold", "color": "#FFFFFF", "size": "lg"}
            ]
        }
    }
    return flex_card, f"【{name} 時間選擇】"

class DietManager:
    def get_or_create_user(self, db: Session, user_id: str) -> User:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(
                user_id=user_id,
                current_weight=70.0,
                target_weight=65.0,
                height=170.0,
                age=30,
                daily_calorie_target=1800,
                target_protein=112.5,
                target_carbs=225.0,
                target_fat=50.0
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    def get_or_create_daily_log(self, db: Session, user_id: str, date_str: str | None = None) -> DailyLog:
        if not date_str:
            date_str = date.today().isoformat()
        log = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.log_date == date_str).first()
        if not log:
            log = DailyLog(
                user_id=user_id,
                log_date=date_str,
                breakfast_completed=False,
                lunch_completed=False,
                dinner_completed=False,
                total_calories=0.0,
                total_protein=0.0,
                total_carbs=0.0,
                total_fat=0.0
            )
            db.add(log)
            db.commit()
            db.refresh(log)
        return log

    def get_welcome_message(self) -> str:
        return """💪【歡迎加入「阿肌師」！您的飲食與健身 AI 教練】🥗

哈囉！我是「阿肌師」👨‍🍳🏋️‍♂️
精通健康餐點熱量搭配，也是您的個人專屬健身教練！

🎯 【核心功能指引】
1. 🍱 飲食建議：輸入「早餐」、「午餐」或「晚餐」取得 3 種推薦卡片。
2. 📸 食物打卡：傳送餐點照片或文字（如：「早餐吃了蛋餅與豆漿」）。
3. 🏋️‍♂️ 運動推薦與打卡：輸入「運動」獲得專屬訓練；輸入「慢跑30分鐘」或上傳截圖紀錄。
4. 📊 進度與設定：輸入「今日紀錄」看營養進度；輸入「運動清單」設定偏好與每週天數。

🔥 請直接傳送「我目前 75 公斤，目標減到 68 公斤」或上傳您的第一餐照片，一起開始變強壯吧！💪"""

    def get_help_message(self) -> str:
        return """🥗 【阿肌師 飲食與健身助手使用說明】
----------------------------
阿肌師 是您的智慧飲食紀錄與健身教練 AI 助手，支援以下自然語言指令：

1. 🎯 【個人目標與體重設定】
   - 直接傳送自然語言：「我目前 75 公斤，目標減到 68 公斤」

2. 🍱 【取得個人化餐點建議選單】
   - 輸入：「早餐」、「午餐」、「晚餐」或「早安」
   - 系統依您今日剩餘熱量與營養素提供 3 種餐點提案卡片！

3. 📸 【記錄餐點打卡】
   - 照片打卡：直接上傳您的食物照片
   - 文字打卡：例如「我早餐吃了一份鮪魚蛋吐司和無糖豆漿」
   - 點心/宵夜：例如「下午茶喝了一杯無糖珍珠拿鐵」

4. 🏋️‍♂️ 【每日運動推薦】
   - 輸入：「運動」或「今日運動」
   - 系統為您量身打造計畫性運動訓練！

5. 🏃 【運動記錄與打卡】
   - 截圖打卡：傳送運動 App 或手錶螢幕截圖
   - 文字打卡：例如「慢跑 30分鐘」、「臥推 10下3組」

6. 📊 【查看今日紀錄與進度】
   - 輸入：「今日紀錄」或「總覽」
   - 隨時查看熱量與三大營養素進度條！

7. 🏃‍♀️ 【個人運動清單與天數管理】
   - 輸入：「運動清單」查看與設定運動天數與偏好運動

8. ❓ 【使用說明】
   - 輸入：「說明」、「指令」或「幫助」"""

    def process_text_message(self, db: Session, user_id: str, text: str):
        user = self.get_or_create_user(db, user_id)
        today_log = self.get_or_create_daily_log(db, user_id)
        clean_text = text.strip()

        # Check 0: Explicit help query or unsupported slash command
        help_kw = ["/help", "help", "說明", "使用說明", "幫助", "指令", "教我", "/start", "?", "？"]
        if clean_text in help_kw or (clean_text.startswith("/") and clean_text not in ["/status", "/setup", "/help"]):
            return self.get_help_message()

        # Check 1: User weight & profile setup intent
        if any(keyword in clean_text for keyword in ["體重", "目標", "設定", "/setup", "公斤", "kg", "減重", "增重"]):
            parsed = gemini_service.parse_user_weight_goal(clean_text)
            user.current_weight = parsed.get("current_weight", user.current_weight)
            user.target_weight = parsed.get("target_weight", user.target_weight)
            user.height = parsed.get("height", user.height)
            user.age = parsed.get("age", user.age)
            user.gender = parsed.get("gender", user.gender)
            user.daily_calorie_target = parsed.get("daily_calorie_target", user.daily_calorie_target)
            user.target_protein = parsed.get("target_protein", user.target_protein)
            user.target_carbs = parsed.get("target_carbs", user.target_carbs)
            user.target_fat = parsed.get("target_fat", user.target_fat)
            db.commit()

            return f"""🎯 【個人飲食目標已更新】
----------------------------
秤 當前體重：{user.current_weight} kg
🏁 目標體重：{user.target_weight} kg
🔥 每日熱量預算：{user.daily_calorie_target} kcal

💡 每日目標三大營養素：
• 蛋白質：{user.target_protein:.1f} g
• 碳水化合物：{user.target_carbs:.1f} g
• 脂肪：{user.target_fat:.1f} g

每天早上第一條訊息我會給您【早餐建議圖卡】！上傳早餐照片/文字後會自動給您【午餐建議圖卡】，以此類推。讓我們一起達成目標吧！💪"""

        # Check 2: View current daily status / summary without recording anything new
        summary_keywords = [
            "/status", "紀錄", "今日紀錄", "狀態", "進度", "今日熱量",
            "今日整理", "整理", "今日總結", "總結", "飲食總結", "三餐總結",
            "報告", "一日總結", "總覽", "總結報告", "摘要"
        ]
        if any(kw == clean_text or clean_text == f"/{kw}" for kw in summary_keywords):
            user_name = line_service.get_user_profile(user.user_id)
            return self.generate_realtime_day_summary(user, today_log, user_name)

        # Check 3: Meal recommendation / query requests (早餐, 午餐, 晚餐, 早安, 建議...)
        is_reporting_meal = any(kw in clean_text for kw in ["吃了", "喝了", "點了", "便當", "吐司", "漢堡", "飯", "麵", "沙拉", "蛋", "奶", "肉", "魚", "雞", "牛", "豬", "一份", "一杯", "1份", "1杯", "kcal", "卡", "克", "g"])
        
        breakfast_kw = ["早餐", "早餐吃什麼", "早餐建議", "早餐推薦", "早安"]
        lunch_kw = ["午餐", "午餐吃什麼", "午餐建議", "午餐推薦", "午安"]
        dinner_kw = ["晚餐", "晚餐吃什麼", "晚餐建議", "晚餐推薦", "晚安"]
        general_kw = ["建議吃什麼", "吃什麼", "給個建議", "hi", "hello", "你好", "hey"]

        is_bk_query = (clean_text in breakfast_kw or any(k == clean_text for k in breakfast_kw) or clean_text == "早安" or clean_text == "早餐")
        is_ln_query = (clean_text in lunch_kw or any(k == clean_text for k in lunch_kw) or clean_text == "午安" or clean_text == "午餐")
        is_dn_query = (clean_text in dinner_kw or any(k == clean_text for k in dinner_kw) or clean_text == "晚安" or clean_text == "晚餐")
        is_gen_query = (clean_text in general_kw or any(k in clean_text for k in ["吃什麼", "建議"]))

        if not is_reporting_meal:
            if is_bk_query or (is_gen_query and not today_log.breakfast_completed):
                if not today_log.breakfast_completed:
                    user_profile = self._user_to_dict(user)
                    consumed = self._log_to_dict(today_log)
                    rec_dict = gemini_service.suggest_next_meal("breakfast", user_profile, consumed, [])
                    intro_summary = rec_dict.get("intro_summary", "🌅 早上好！為您送上今日的【早餐建議選單】：")
                    options = rec_dict.get("options", [])
                    flex_carousel, alt_text = build_option_carousel_card("breakfast", options)
                    return (intro_summary, flex_carousel, alt_text)
                else:
                    user_name = line_service.get_user_profile(user.user_id)
                    bk_meal = next((m for m in today_log.meals if m.meal_type == "breakfast"), None)
                    bk_detail = f"：{bk_meal.food_description}" if bk_meal else ""
                    if not today_log.lunch_completed:
                        user_profile = self._user_to_dict(user)
                        consumed = self._log_to_dict(today_log)
                        consumed_meals_summary = [f"{m.meal_type}: {m.food_description}" for m in today_log.meals]
                        rec_dict = gemini_service.suggest_next_meal("lunch", user_profile, consumed, consumed_meals_summary)
                        intro_summary = rec_dict.get("intro_summary", "為您提供【午餐建議選單】：")
                        options = rec_dict.get("options", [])
                        flex_carousel, alt_text = build_option_carousel_card("lunch", options)
                        return (f"🍳 您今日的早餐已紀錄完成{bk_detail}囉！\n\n----------------------------\n🥗 {intro_summary}", flex_carousel, alt_text)
                    else:
                        return self.generate_realtime_day_summary(user, today_log, user_name)

            elif is_ln_query or (is_gen_query and today_log.breakfast_completed and not today_log.lunch_completed):
                if not today_log.lunch_completed:
                    user_profile = self._user_to_dict(user)
                    consumed = self._log_to_dict(today_log)
                    consumed_meals_summary = [f"{m.meal_type}: {m.food_description}" for m in today_log.meals]
                    rec_dict = gemini_service.suggest_next_meal("lunch", user_profile, consumed, consumed_meals_summary)
                    intro_summary = rec_dict.get("intro_summary", "🥗 為您送上今日的【午餐建議選單】：")
                    options = rec_dict.get("options", [])
                    flex_carousel, alt_text = build_option_carousel_card("lunch", options)
                    return (intro_summary, flex_carousel, alt_text)
                else:
                    user_name = line_service.get_user_profile(user.user_id)
                    return self.generate_realtime_day_summary(user, today_log, user_name)

            elif is_dn_query or (is_gen_query and today_log.lunch_completed and not today_log.dinner_completed):
                if not today_log.dinner_completed:
                    user_profile = self._user_to_dict(user)
                    consumed = self._log_to_dict(today_log)
                    consumed_meals_summary = [f"{m.meal_type}: {m.food_description}" for m in today_log.meals]
                    rec_dict = gemini_service.suggest_next_meal("dinner", user_profile, consumed, consumed_meals_summary)
                    intro_summary = rec_dict.get("intro_summary", "🍲 為您送上今日的【晚餐建議選單】：")
                    options = rec_dict.get("options", [])
                    flex_carousel, alt_text = build_option_carousel_card("dinner", options)
                    return (intro_summary, flex_carousel, alt_text)
                else:
                    user_name = line_service.get_user_profile(user.user_id)
                    return self.generate_realtime_day_summary(user, today_log, user_name)

        # Check 4: Treat text as food entry
        food_analysis = gemini_service.analyze_food(text_description=clean_text)
        if not food_analysis.get("is_food", True):
            return f"⚠️ 抱歉，DietBot 未在此訊息中識別出食物打卡內容喔！\n\n----------------------------\n{self.get_help_message()}"

        return self._record_meal_and_respond(db, user, today_log, food_analysis, user_text=clean_text)

    def process_image_message(self, db: Session, user_id: str, image_bytes: bytes, caption: str | None = None):
        user = self.get_or_create_user(db, user_id)
        today_log = self.get_or_create_daily_log(db, user_id)

        food_analysis = gemini_service.analyze_food(image_bytes=image_bytes, text_description=caption)
        
        # Non-food detection rule: If photo is not food, return clear notice with help message instead of None
        if not food_analysis.get("is_food", True):
            logger.info(f"Non-food image detected for user {user_id}.")
            return f"📷 【照片辨識提醒】\n----------------------------\n⚠️ 抱歉，AI 未能在此照片中辨識出明確的食物或飲料。\n\n💡 建議您：\n1. 上傳角度清晰、光線充足的食物照片。\n2. 或直接用文字描述打卡（例如：「我早餐吃了一份鮪魚蛋吐司加無糖豆漿」）。\n\n----------------------------\n{self.get_help_message()}"

        return self._record_meal_and_respond(db, user, today_log, food_analysis, image_path=None, user_text=caption)

    def _record_meal_and_respond(self, db: Session, user: User, log: DailyLog, analysis: dict, image_path: str | None = None, user_text: str | None = None):
        combined_text = ((user_text or "") + " " + analysis.get("food_name", "")).lower()
        if "早餐" in combined_text:
            meal_type = "breakfast"
        elif "午餐" in combined_text:
            meal_type = "lunch"
        elif "晚餐" in combined_text:
            meal_type = "dinner"
        elif any(k in combined_text for k in ["點心", "宵夜", "下午茶", "飲料", "手搖"]):
            meal_type = "snack"
        else:
            if not log.breakfast_completed:
                meal_type = "breakfast"
            elif not log.lunch_completed:
                meal_type = "lunch"
            elif not log.dinner_completed:
                meal_type = "dinner"
            else:
                meal_type = "snack"

        cals = float(analysis.get("calories", 0))
        p = float(analysis.get("protein", 0))
        c = float(analysis.get("carbs", 0))
        f = float(analysis.get("fat", 0))
        food_name = analysis.get("food_name", "餐點")
        summary = analysis.get("summary", "")

        meal_rec = MealRecord(
            daily_log_id=log.id,
            user_id=user.user_id,
            meal_type=meal_type,
            food_description=food_name,
            calories=cals,
            protein=p,
            carbs=c,
            fat=f,
            image_path=image_path,
            ai_analysis=summary
        )
        db.add(meal_rec)

        log.total_calories += cals
        log.total_protein += p
        log.total_carbs += c
        log.total_fat += f

        if meal_type == "breakfast":
            log.breakfast_completed = True
        elif meal_type == "lunch":
            log.lunch_completed = True
        elif meal_type == "dinner":
            log.dinner_completed = True

        db.commit()
        db.refresh(log)

        meal_name_tw = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "點心/宵夜"}.get(meal_type, "餐點")
        
        p_target = user.target_protein or 100.0
        c_target = user.target_carbs or 200.0
        f_target = user.target_fat or 50.0

        p_pct = int((p / p_target) * 100) if p_target else 0
        c_pct = int((c / c_target) * 100) if c_target else 0
        f_pct = int((f / f_target) * 100) if f_target else 0

        meal_summary_text = (
            f"📸 【{meal_name_tw}紀錄成功】\n"
            f"🍽️ 食物辨識：{food_name}\n"
            f"🔥 估計熱量：{cals:.0f} kcal\n"
            f"📊 營養素：\n"
            f"  • 蛋白質：{p:.1f}g ({p_pct}%)\n"
            f"  • 碳水化合物：{c:.1f}g ({c_pct}%)\n"
            f"  • 脂肪：{f:.1f}g ({f_pct}%)\n"
            f"💬 營養師短評：{summary}"
        )

        user_profile = self._user_to_dict(user)
        total_consumed = self._log_to_dict(log)
        consumed_meals_summary = [f"{m.meal_type}: {m.food_description}" for m in log.meals]

        # Trigger next step in sequence
        if meal_type == "breakfast":
            rec_dict = gemini_service.suggest_next_meal("lunch", user_profile, total_consumed, consumed_meals_summary)
            intro_summary = rec_dict.get("intro_summary", "為您提供【午餐建議選單】：")
            options = rec_dict.get("options", [])
            flex_carousel, alt_text = build_option_carousel_card("lunch", options)
            return (f"{meal_summary_text}\n\n----------------------------\n🥗 {intro_summary}", flex_carousel, alt_text)

        elif meal_type == "lunch":
            rec_dict = gemini_service.suggest_next_meal("dinner", user_profile, total_consumed, consumed_meals_summary)
            intro_summary = rec_dict.get("intro_summary", "為您提供【晚餐建議選單】：")
            options = rec_dict.get("options", [])
            flex_carousel, alt_text = build_option_carousel_card("dinner", options)
            return (f"{meal_summary_text}\n\n----------------------------\n🍲 {intro_summary}", flex_carousel, alt_text)

        elif meal_type == "dinner" or (log.breakfast_completed and log.lunch_completed and log.dinner_completed):
            user_name = line_service.get_user_profile(user.user_id)
            day_summary = gemini_service.generate_day_summary(
                user_name,
                user_profile,
                total_consumed,
                [self._meal_to_dict(m) for m in log.meals]
            )
            progress_bar_section = build_4_progress_bars(log, user)

            full_text = f"{meal_summary_text}\n\n----------------------------\n{progress_bar_section}\n\n🎉 【一日總結與明日建議】\n{day_summary}"
            return full_text
        else:
            progress_bar_section = build_4_progress_bars(log, user)
            full_text = f"{meal_summary_text}\n\n----------------------------\n{progress_bar_section}"
            return full_text

    def generate_realtime_day_summary(self, user: User, log: DailyLog, user_name: str) -> str:
        progress_bars = build_4_progress_bars(log, user)

        meal_name_tw = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "點心/宵夜"}
        meals_text = "\n".join([
            f"• [{meal_name_tw.get(m.meal_type, m.meal_type)}] {m.food_description} - {m.calories:.0f} kcal (P:{m.protein:.1f}g, C:{m.carbs:.1f}g, F:{m.fat:.1f}g)"
            for m in log.meals
        ]) if log.meals else "尚無紀錄"

        status_header = f"""📊 【{user_name} 的今日飲食紀錄總覽】
----------------------------
{progress_bars}

🍽️ 今日已記錄餐點：
{meals_text}"""

        if not log.meals:
            return f"{status_header}\n----------------------------\n💡 您今天尚未記錄任何餐點喔！傳送照片或輸入文字即可開始記錄！"

        user_profile = self._user_to_dict(user)
        total_consumed = self._log_to_dict(log)
        ai_summary = gemini_service.generate_day_summary(
            user_name,
            user_profile,
            total_consumed,
            [self._meal_to_dict(m) for m in log.meals]
        )

        return f"{status_header}\n----------------------------\n🎉 【今日飲食 AI 總結與建議】\n{ai_summary}"

    def format_daily_status(self, user: User, log: DailyLog) -> str:
        return self.generate_realtime_day_summary(user, log, "夥伴")

    def _user_to_dict(self, u: User) -> dict:
        return {
            "current_weight": u.current_weight,
            "target_weight": u.target_weight,
            "daily_calorie_target": u.daily_calorie_target,
            "target_protein": u.target_protein,
            "target_carbs": u.target_carbs,
            "target_fat": u.target_fat
        }

    def _log_to_dict(self, log: DailyLog) -> dict:
        return {
            "calories": log.total_calories,
            "protein": log.total_protein,
            "carbs": log.total_carbs,
            "fat": log.total_fat
        }

    def _meal_to_dict(self, m: MealRecord) -> dict:
        return {
            "meal_type": m.meal_type,
            "food_description": m.food_description,
            "calories": m.calories,
            "protein": m.protein,
            "carbs": m.carbs,
            "fat": m.fat
        }

diet_manager = DietManager()
