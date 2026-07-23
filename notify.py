"""發送 Telegram 訊息。"""
import os
import json
import urllib.parse
import urllib.request

KEYS = ("TG_BOT_TOKEN", "TG_CHAT_ID")


def load_env(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k in KEYS:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def send(text, env=None):
    env = env or load_env()
    url = f"https://api.telegram.org/bot{env['TG_BOT_TOKEN']}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": env["TG_CHAT_ID"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as r:
        return json.load(r)


if __name__ == "__main__":
    print(send("測試訊息：扣抵值監測機器人正常運作 ✅"))
