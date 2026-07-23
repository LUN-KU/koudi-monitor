"""警示紀錄：寫入 alert_log.json，供每週復盤統計成效。"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "alert_log.json")


def load():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding="utf-8"))
    return []


def save(entries):
    json.dump(entries, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def log(kind, stk, name, price, detail, source):
    """kind: 進場候選 / 進場觀察 / 轉強 / 賣訊 / 警戒；source: close / intraday"""
    entries = load()
    entries.append({
        "ts": datetime.datetime.now().isoformat(timespec="minutes"),
        "date": datetime.date.today().isoformat(),
        "kind": kind, "stk": stk, "name": name,
        "price": price, "detail": detail, "source": source,
    })
    save(entries)


def sent_today(kind, stk):
    today = datetime.date.today().isoformat()
    return any(e["date"] == today and e["kind"] == kind and e["stk"] == stk for e in load())


def tracked(days=14):
    """近期曾被列為進場候選的代號 — 出場提醒只針對這些標的，避免整張清單洗版。
    之後有 positions.json（實際部位）時，一併納入。"""
    import os
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    stks = {e["stk"] for e in load() if e["kind"] == "進場候選" and e["date"] >= cutoff}
    pos = os.path.join(HERE, "positions.json")
    if os.path.exists(pos):
        stks |= set(json.load(open(pos, encoding="utf-8")))
    return stks
