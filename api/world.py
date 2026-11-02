"""
/api/world — 화면이 읽는 한 덩이.

**Supabase 표만 읽는다.**
  전에는 atlas·home·villagers 를 import 했는데, 그 파일들은 몰랑이
  저장소에만 있다. Vercel 에 복사하면 거기 딸린 것이 줄줄이 따라온다.
  표를 직접 읽으면 이 파일 하나로 끝난다.

읽기만 하므로 anon 키로 충분하다. 브라우저에는 키를 두지 않는다.
"""
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = (os.environ.get("SUPABASE_ANON_KEY")
       or os.environ.get("SUPABASE_KEY") or "")

# 집 안 방 자리 — home.layout() 과 같은 값.
# 여기 적어두면 몰랑이 코드를 안 가져와도 집을 그릴 수 있다.
ROOMS = {"부엌": [4, 4], "서재": [4, 1], "창가": [2, 0],
         "작업방": [0, 4], "마당": [0, 1], "다락": [2, 3]}


def _get(table, select="*", **q):
    """PostgREST 를 그냥 호출한다 — supabase 꾸러미가 없어도 된다."""
    if not URL or not KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY 가 없습니다")
    params = {"select": select}
    params.update(q)
    u = f"{URL}/rest/v1/{table}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(u, headers={
        "apikey": KEY, "Authorization": f"Bearer {KEY}",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def _one(table, select="*", **q):
    rows = _get(table, select, limit="1", **q)
    return rows[0] if rows else {}


def _frames(rows):
    """같은 시각끼리 묶는다 — 한 회차가 한 장면."""
    out, cur, t0 = [], {}, None
    for r in rows:
        t = round(float(r.get("at") or 0) / 60)
        if t0 is None:
            t0 = t
        if t != t0:
            if cur:
                out.append({"at": t0 * 60, "who": cur})
            cur, t0 = {}, t
        cur[r["who"]] = {"spot": r.get("spot"), "room": r.get("room"),
                         "feel": r.get("feel")}
    if cur:
        out.append({"at": (t0 or 0) * 60, "who": cur})
    return out


def world():
    import time

    atlas = (_one("molang_atlas", "data", id="eq.1").get("data") or {})
    view = {"size": atlas.get("size") or [21, 15],
            "spots": atlas.get("spots") or {}, "who": {}}

    # 지금 누가 어디 있나
    try:
        who = (_one("molang_villagers", "data", id="eq.1").get("data") or {})
        for n, v in who.items():
            if isinstance(v, dict):
                view["who"][n] = {"at": v.get("where"),
                                  "feel": (v.get("feel") or {})}
    except Exception:
        pass

    try:
        h = (_one("molang_home", "layout", id="eq.1").get("layout") or {})
        for key, name in (("molang", "몰랑이"), ("piupiu", "피우피우")):
            room = (h.get("where") or {}).get(key)
            if room:
                view["who"][name] = {"at": "몰랑이네", "room": room}
        view["home"] = {"coords": ROOMS,
                        "objects": h.get("objects") or {},
                        "where": h.get("where") or {}}
    except Exception:
        pass

    try:
        pk = (_one("molang_pinko", "data", id="eq.1").get("data") or {})
        view["pinko"] = {k: v.get("name") for k, v in pk.items()
                         if isinstance(v, dict) and v.get("known")}
    except Exception:
        pass

    # **길.** 자주 오간 사이는 땅에 자국이 남는다.
    # bonds 에 누가 누구와 몇 번 만났는지가 있고, society 에 어디서
    # 만났는지가 있다. 그 둘로 "이 자리와 저 자리 사이를 자주 오갔다"
    # 를 센다.
    try:
        soc = (_one("molang_society", "data", id="eq.1").get("data") or {})
        pair = {}
        prev = {}
        for m in (soc.get("meets") or []):
            for who in (m.get("a"), m.get("b")):
                spot = m.get("place")
                if not who or not spot:
                    continue
                last = prev.get(who)
                if last and last != spot:
                    k = tuple(sorted([last, spot]))
                    pair[k] = pair.get(k, 0) + 1
                prev[who] = spot
        view_spots = view.get("spots") or {}
        view["paths"] = [
            {"a": a, "b": b, "n": n}
            for (a, b), n in sorted(pair.items(), key=lambda kv: -kv[1])[:40]
            if a in view_spots and b in view_spots]
    except Exception:
        view["paths"] = []

    # 하루치 발자국
    frames = []
    try:
        since = time.time() - 24 * 3600
        rows = _get("molang_steps", "at,who,spot,room,feel",
                    **{"at": f"gte.{since}", "order": "at.asc",
                       "limit": "3000"})
        frames = _frames(rows)

        # 발자국이 더 촘촘하다 — 한 사람이 어디서 어디로 옮겼나
        pair = {}
        prev = {}
        for r in rows:
            who, spot = r.get("who"), r.get("spot")
            if not who or not spot:
                continue
            last = prev.get(who)
            if last and last != spot:
                k = tuple(sorted([last, spot]))
                pair[k] = pair.get(k, 0) + 1
            prev[who] = spot
        spots = view.get("spots") or {}
        more = [{"a": a, "b": b, "n": n}
                for (a, b), n in sorted(pair.items(), key=lambda kv: -kv[1])
                if a in spots and b in spots][:40]
        if more:
            view["paths"] = more
    except Exception:
        pass

    return {"view": view, "replay": {"frames": frames, "n": len(frames)}}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body = json.dumps(world(), ensure_ascii=False)
            code = 200
        except Exception as e:
            body = json.dumps({"error": f"{type(e).__name__}: {str(e)[:160]}"},
                              ensure_ascii=False)
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
