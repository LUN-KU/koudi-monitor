"""
Telegram 設定小幫手
用途：用你的機器人金鑰，自動找出你的 chat id，寫進 .env，並發一則測試訊息。
用法：python3 tg_setup.py <你的機器人金鑰>
（執行前，記得先在 Telegram 打開你的新機器人、按 START 或傳一句話給它）
"""
import sys
import os
import json
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def api(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as r:
        return json.load(r)


def main():
    if len(sys.argv) < 2:
        print("請這樣執行：python3 tg_setup.py <你的機器人金鑰>")
        return
    token = sys.argv[1].strip()

    updates = api(token, "getUpdates")
    if not updates.get("ok"):
        print("金鑰好像不對，Telegram 回覆：", updates)
        return

    results = updates.get("result", [])
    if not results:
        print("找不到你傳給機器人的訊息。")
        print("請先在 Telegram 打開你的機器人，按 START 或傳一句『hi』，再重跑這支程式。")
        return

    chat = results[-1]["message"]["chat"]
    chat_id = chat["id"]
    print(f"找到你了！chat id = {chat_id}（{chat.get('first_name', '')}）")

    with open(os.path.join(HERE, ".env"), "w", encoding="utf-8") as fp:
        fp.write(f"TG_BOT_TOKEN={token}\nTG_CHAT_ID={chat_id}\n")
    print("已寫入 .env（此檔已 gitignore，不會上傳）")

    api(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "✅ 扣抵值監測機器人設定成功！以後收盤篩股、盤中警示、每週復盤都會發到這裡。",
    })
    print("已經發一則測試訊息到你的 Telegram，去看看有沒有收到。")
    print("\n之後設定 GitHub Actions 要用到這兩個值：")
    print(f"  TG_BOT_TOKEN = {token}")
    print(f"  TG_CHAT_ID   = {chat_id}")


if __name__ == "__main__":
    main()
