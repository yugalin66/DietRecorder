# DietBot (LINE 飲食熱量與營養記錄 AI 機器人) 🥗🤖

DietBot 是一個基於 **LINE Messaging API**、**FastAPI** 與 **Google Gemini AI** 的智慧飲食紀錄機器人。
支援照片/文字識別食物熱量與三大營養素，提供動態階段式個人化飲食建議（早餐建議 -> 午餐建議 -> 晚餐建議 -> 全天熱量與營養總結）。

---

## 🌟 主要功能亮點

1. **體重與目標設定 (自然語言對話)**：
   - 用戶輸入例如：「我現在 75kg，想減到 68kg」，AI 自動解析數據並計算 BMR、TDEE 及每日熱量與三大營養素（蛋白質、碳水化合物、脂肪）目標預算。
2. **AI 照片與文字辨識熱量/營養素**：
   - 傳送食物照片或文字描述，Gemini Vision 自動判斷食物品項、預估總熱量 (kcal) 與三大營養素 (g)，並給予營養師簡評。
3. **動態階段式餐點引導流程**：
   - **早上**：傳送「早安」或打卡，AI 提供符合今日目標熱量的 **早餐建議**。
   - **上傳早餐**：自動紀錄熱量營養，並產生 **午餐建議**。
   - **上傳午餐**：自動紀錄熱量營養，並產生 **晚餐建議**。
   - **上傳晚餐**：自動紀錄熱量營養，產生 **今日總結報告**（含圖形化熱量進度條 `[██████░░░░]`）與明天飲食改善建議。
4. **即時總覽與點心紀錄**：
   - 輸入 `/status` 或「今日紀錄」，隨時查看今天已攝取的總熱量與剩餘預算。
   - 下午茶/手搖飲/宵夜自動歸類為點心，計入每日累積熱量而不破壞主流程。

---

## 📁 專案結構

```
DietBot/
├── database/                   # SQLite 資料庫儲存目錄
├── src/
│   ├── config.py               # 環境變數與 Gemini/LINE 設定
│   ├── database.py             # SQLAlchemy 資料庫連線
│   ├── models.py               # User, DailyLog, MealRecord 資料表
│   ├── gemini_service.py       # Gemini 多 Key/模型輪替 API 服務
│   ├── line_service.py         # LINE Messaging API 推播與回覆
│   ├── diet_manager.py         # 飲食狀態機與核心業務邏輯
│   └── scheduler.py            # APScheduler 定時推播任務
├── main.py                     # FastAPI 伺服器入口 (Webhook & Direct REST API)
├── test_diet_bot.py            # 自動化測試腳本
├── requirements.txt            # Python 依賴套件
└── .env                        # 環境變數設定檔
```

---

## 🚀 快速開始

### 1. 建立虛擬環境與安裝套件

```bash
cd /home/yuga/Desktop/Bots/DietBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定 `.env`

確認 `DietBot/.env` 中的 `LINE_CHANNEL_ACCESS_TOKEN` 與 `GEMINI_API_KEYS` 已經設定完成。

### 3. 執行測試腳本

```bash
venv/bin/pytest -v test_diet_bot.py
```

### 4. 啟動 FastAPI 服務

```bash
venv/bin/python main.py
```
伺服器將會啟動於 `http://0.0.0.0:8000`。

LINE Webhook URL 可設定為: `https://your-domain.ngrok.io/webhook`

---

## 🧪 Direct REST API 測試 (無需 LINE Webhook)

可以使用 REST API 直接測試聊天邏輯：

```bash
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user_demo", "text": "我目前 72kg，想減到 65kg"}'
```
