# 扣抵值選股自動監測系統

依「扣抵值選股策略」自動盯盤：收盤篩股、盤中警示、每週復盤，通知發到專屬 Telegram。

策略依據：`../000_Agent/knowledge/扣抵值選股策略.md`

## 五大功能對應

| 功能 | 由誰負責 | 何時跑 |
|------|---------|--------|
| 持續掃描 | `intraday_scan.py` + `close_scan.py` | 盤中每 30 分、收盤後 |
| 觸發警示 | `intraday_scan.py` | 條件達成立刻發 Telegram |
| 狀態監控 | 部分（`positions.json` 待補） | 目前用「近 14 天曾為候選」代理 |
| 主動復盤 | `weekly_review.py` | 每週六早上 |
| 觀察清單更新 | `update_watchlist.py` | 你貼報告書後手動／請 AI 執行 |

## 第一次設定（三步）

1. **申請 Telegram 機器人**：在 Telegram 找 `@BotFather` → 傳 `/newbot` → 取名 → 拿到一串金鑰
2. **打開你的新機器人按 START**，然後執行：
   ```
   python3 tg_setup.py <你的機器人金鑰>
   ```
   會自動寫好 `.env` 並發一則測試訊息
3. **上雲端（可選但建議）**：把本資料夾推到 GitHub，在 repo 的
   Settings → Secrets and variables → Actions 加兩個 Secret：
   `TG_BOT_TOKEN`、`TG_CHAT_ID`（值就是上一步印出來的）

## 日常使用

```bash
python3 fetch_k.py            # 抓日 K（換日要重抓）
python3 close_scan.py --dry   # 收盤掃描，--dry 只印不發
python3 intraday_scan.py --dry
python3 weekly_review.py --dry
```

### 更新觀察清單（你貼報告書後）

```bash
python3 update_watchlist.py --add 2330=台積電 6414=樺漢
python3 update_watchlist.py --remove 1301 1303
python3 update_watchlist.py --prune-kills   # 移除今天被濾網刪掉的
python3 update_watchlist.py --list
```

## 雲端排程（GitHub Actions）

`.github/workflows/monitor.yml`，時間已換算成台灣時間：

- 盤中 09:30–13:00 每 30 分 → 盤中掃描
- 14:30 → 收盤掃描（含重抓日 K）
- 週六 10:00 → 每週復盤

也可以在 Actions 頁面手動觸發（`workflow_dispatch`，可選 intraday / close / weekly）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `watchlist.json` | 觀察清單（代號:名稱） |
| `kdata.json` | 日 K 快取，收盤掃描時更新 |
| `alert_log.json` | 所有發過的警示紀錄，供復盤統計 |
| `strategy.py` | 策略大腦：濾網、評分、進出場訊號、盤中關鍵價位 |
| `quote.py` | TWSE 即時報價（免登入，自動 tse/otc fallback） |
| `notify.py` / `tg_setup.py` | Telegram 發送與一次性設定 |
| `.env` | 機密（已 gitignore） |

## 已知限制

- **盤中訊號是簡化版**：只比對現價與扣抵值／基準價／昨高低／MA5，不做策略檔要求的「五分 K 帶量突破」確認（那需要券商即時資料）。收到訊號請自行看盤確認量能。
- **停損訊號有防洗出場的時間規則**（`strategy.stop_gate`）：賣訊（跌破扣抵值＝停損點）在 13:15 前先按住不發，避免被盤中下影線洗出場；除非急殺跌破停損點逾 7% 才立即通知。到 13:15（收盤前）若仍沒站回停損點，才發出確認的止損出場通知。因此排程多了一個 13:15 的掃描。
- **部位追蹤尚未實作**：目前沒有 `positions.json`。要啟用時建立該檔（`{"2330": {"cost": 1000, "shares": 1000}}`），出場提醒會自動納入。
- **盤中通知時間不保證準時（已知取捨，維持全雲端）**：GitHub 免費排程官方不保證準時、忙碌時會延遲甚至跳過。系統已加「交易時段守門」——盤中掃描只在台灣 09:00–13:35 執行，遲到超時的排程直接略過（寧可不發，也不發錯的）。因此盤中通知偶爾會晚幾分鐘或漏掉；有跳就是有效訊號。收盤報告與週報不受影響。
- **資料新鮮度保護**：某檔最新 K 線離今天超過 6 天（殘缺/漏抓）時，盤中自動跳過該檔，不拿舊資料算錯昨日低點/扣抵值。
- 本系統為技術面判斷輔助，不是投資建議，也不會自動下單。
