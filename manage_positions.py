"""維護持倉 positions.json（供儀表板顯示出場條件）。

用法：
  python3 manage_positions.py --add 2330 成本=2380 股數=1000 停損=2370 目標=3000
  python3 manage_positions.py --remove 2330
  python3 manage_positions.py --list

欄位：成本(必填)、股數(選)、停損(選,不填則用昨日低點)、目標(選,停利目標價)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
POS = os.path.join(HERE, "positions.json")
WL = os.path.join(HERE, "watchlist.json")
FIELD = {"成本": "cost", "股數": "shares", "停損": "stop", "目標": "target"}


def load():
    return json.load(open(POS, encoding="utf-8")) if os.path.exists(POS) else {}


def save(d):
    json.dump(d, open(POS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    argv = sys.argv[1:]
    pos = load()
    if not argv or argv[0] == "--list":
        if not pos:
            print("目前沒有持倉。")
            return
        for k, v in pos.items():
            print(f"  {k} {v.get('name', '')}｜成本 {v.get('cost')}｜股數 {v.get('shares', '-')}"
                  f"｜停損 {v.get('stop', '未設')}｜目標 {v.get('target', '未設')}")
        return

    cmd = argv[0]
    if cmd == "--remove":
        for k in argv[1:]:
            pos.pop(k, None)
        save(pos)
        print("已移除；剩", len(pos), "檔")
    elif cmd == "--add":
        code = argv[1]
        rec = pos.get(code, {})
        wl = json.load(open(WL, encoding="utf-8")) if os.path.exists(WL) else {}
        rec.setdefault("name", wl.get(code, ""))
        for a in argv[2:]:
            if "=" not in a:
                continue
            k, v = a.split("=", 1)
            if k in FIELD:
                rec[FIELD[k]] = float(v)
        if "cost" not in rec:
            print("缺少成本，請加 成本=xxx")
            return
        pos[code] = rec
        save(pos)
        print(f"已記錄 {code} {rec.get('name', '')}：{rec}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
