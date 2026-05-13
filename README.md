# Calendar Notification Bot

每天早上 8:00 自動抓取 **Apple Calendar（iCloud）** 當日行程，透過 **Discord Webhook** 發送到指定頻道。整個服務跑在 Docker 容器內，常駐排程。

---

## 功能

- 透過 CalDAV 連線 iCloud，讀取所有行事曆當日事件
- 自動排序：全天事件在前，其餘按開始時間
- 格式化輸出時間、標題、地點
- 沒有行程時也會送訊息「今天沒安排」
- 每日 08:00（時區可調）自動執行
- 容器啟動時可選擇立即執行一次（測試用）
- 執行失敗會送錯誤通知到 Discord

---

## 架構

```
┌─────────────────────────────────────┐
│ Docker container                    │
│                                     │
│  APScheduler ──08:00 每日觸發──┐   │
│                                ▼   │
│  iCloud CalDAV ──events──▶ 格式化  │
│                                │   │
│                                ▼   │
│                       Discord Webhook
└─────────────────────────────────────┘
```

---

## 前置準備

### 1. 產生 Apple App 專用密碼

> 不能用 Apple ID 主密碼，必須產生 App 專用密碼

1. 前往 https://appleid.apple.com
2. 登入 → **登入與安全性** → **App 專用密碼**
3. 點「+」產生新密碼，名稱填 `Calendar Bot`
4. 複製產生的 `xxxx-xxxx-xxxx-xxxx` 格式密碼

### 2. 建立 Discord Webhook

1. 進入目標 Discord 伺服器與頻道
2. 頻道齒輪 → **編輯頻道** → **整合** → **Webhook**
3. 點「新 Webhook」，取個名字（例如 `Calendar Bot`），可選頭像
4. **複製 Webhook URL**

### 3. 確認 iCloud 行事曆已啟用

iPhone：設定 → Apple ID → iCloud → 行事曆 開啟  
Mac：系統設定 → Apple ID → iCloud → 行事曆 開啟

---

## 安裝與啟動

### 1. clone 並設定環境變數

```bash
git clone <this-repo>
cd Calendar-Notification-Bot
cp .env.example .env
```

編輯 `.env`：

```dotenv
ICLOUD_USERNAME=your_apple_id@example.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
TZ=Asia/Taipei
NOTIFY_HOUR=8
NOTIFY_MINUTE=0
RUN_ON_START=0
```

### 2. 啟動容器

```bash
docker compose up -d --build
```

### 3. 看 log

```bash
docker compose logs -f
```

### 4. 停止

```bash
docker compose down
```

---

## 測試

想立即測試一次（不等 08:00）：

```bash
# 把 .env 裡 RUN_ON_START 改成 1
RUN_ON_START=1

# 重啟容器
docker compose up -d --force-recreate
docker compose logs -f
```

預期會立刻送一則訊息到 Discord 頻道，之後恢復每日排程。

---

## 環境變數總覽

| 變數                  | 必填 | 預設           | 說明                                        |
| --------------------- | ---- | -------------- | ------------------------------------------- |
| `ICLOUD_USERNAME`     | ✅   | -              | Apple ID（email）                           |
| `ICLOUD_APP_PASSWORD` | ✅   | -              | App 專用密碼，**不是主密碼**                |
| `DISCORD_WEBHOOK_URL` | ✅   | -              | Discord 頻道 Webhook URL                    |
| `TZ`                  | ❌   | `Asia/Taipei`  | 時區（影響「今天」定義與排程時間）          |
| `NOTIFY_HOUR`         | ❌   | `8`            | 每日通知小時（0–23）                        |
| `NOTIFY_MINUTE`       | ❌   | `0`            | 每日通知分鐘（0–59）                        |
| `RUN_ON_START`        | ❌   | `0`            | 設為 `1` 時容器啟動立即跑一次               |

---

## 訊息範例

```
📅 今日行程 2026-05-14 (Thu)

• `全天`  公司 Off-site
• `09:30–10:00`  Daily standup  📍 線上
• `14:00–15:00`  Design review  📍 Room 402
• `19:00–21:00`  晚餐聚會
```

沒有行程時：

```
📅 今日行程 2026-05-14 (Thu)

今天沒有安排，好好休息 ☕
```

---

## 疑難排解

**`401 Unauthorized`**：密碼錯誤。確認用的是 App 專用密碼，不是 Apple ID 主密碼。

**抓不到事件**：確認 iCloud 行事曆已啟用同步；事件是否在 iCloud 行事曆而非「本機」或「Google」行事曆。

**時間對不上**：檢查 `TZ` 設定。容器內 timezone 由 `TZ` 環境變數決定，預設 `Asia/Taipei`。

**Webhook 失敗**：直接用 curl 測試 Webhook 是否還有效：
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"test"}' "$DISCORD_WEBHOOK_URL"
```

---

## 檔案結構

```
.
├── main.py              # 主程式：CalDAV 抓資料 + 排程 + Discord
├── requirements.txt     # Python 依賴
├── Dockerfile           # 容器映像
├── docker-compose.yml   # 一鍵啟動
├── .env.example         # 環境變數範本
├── .gitignore
└── README.md
```

---

## 技術選型

- **CalDAV over iCloud**：跨平台，可在 Linux Docker 內運作（EventKit / AppleScript 都限 macOS）
- **Discord Webhook**：單向推訊息夠用，不需常駐 Bot gateway 連線
- **APScheduler**：容器內排程，不依賴 host cron
- **`zoneinfo`**：Python 3.9+ 內建 IANA 時區
