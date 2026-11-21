"""
/api/world — 화면이 읽는 한 덩이.

**Supabase 표만 읽는다.**
  전에는 atlas·home·villagers 를 import 했는데, 그 파일들은 몰랑이
  저장소에만 있다. Vercel 에 복사하면 거기 딸린 것이 줄줄이 따라온다.
  표를 직접 읽으면 이 파일 하나로 끝난다.

읽기만 하므로 anon 키로 충분하다. 브라우저에는 키를 두지 않는다.

**보는 것만 여기서 한다.**
  대화와 승인은 Streamlit 에 둔다. 몰랑이가 답하려면 유형 고르기,
  트리 걷기, 기억 꺼내기, 가드가 다 돌아야 하는데 그건 엔진 쪽에만
  있다. 여기서 LLM 을 따로 부르면 **판단 구조가 둘로 갈린다** —
  기억은 같은 Supabase 에 남아도, 그 기억을 만든 길이 달라진다.
  그래서 이 파일은 끝까지 읽기만 한다.

표가 아직 없거나 모양이 다르면 그 칸만 비운다. 한 칸 때문에
화면 전체가 안 뜨는 일이 없도록, 모든 덧읽기는 따로 감싼다.
"""
import json
import math
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

# atlas.py 와 같은 값 — 마을은 가운데 칸, 바깥은 바깥 고리.
VILLAGE_BOX = (7, 5, 7, 5)

_ICON = {
    "몰랑이네": "🏠", "슈야토야네": "🧁", "미피네": "🍼",
    "빵집": "🥐", "우물가": "⛲", "꽃밭": "🌷", "언덕": "🌾",
    "가게": "🏪", "놀이터": "🛝", "도서관": "📚", "음악방": "🎵",
    "사진관": "📷", "별보는터": "🔭", "목욕탕": "♨️",
    "작업실": "🔧", "카페": "☕", "텃밭": "🥕",
    "바다": "🌊", "숲": "🌲", "산": "⛰️", "들판": "🌾", "물가": "🏞️",
    "언덕마루": "🌄", "밤하늘터": "✨", "꽃길": "🌸", "폐허": "🏚️",
    "안개골": "🌫️", "메아리벽": "🔊", "마을": "🏘️",
}


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


def _safe(fn, default):
    """한 칸이 안 되는 것과 화면이 안 뜨는 것은 다르다."""
    try:
        return fn()
    except Exception:
        return default


def _pick(d, keys):
    """표의 열 이름이 판마다 다르다. 있는 것을 쓴다."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


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


# ── 사이 ────────────────────────────────────────────────────────
#
# bonds 표의 모양을 여기서 단정하지 않는다. 한 줄에 한 쌍일 수도,
# data 한 덩이에 전부 들어 있을 수도 있다. 둘 다 받는다.

# molang_bonds 는 id=1 한 줄에 data 한 덩이다.
#   data = { "몰랑이|피우피우": {met, last_at, warmth, talks[], topics{}} }
# 열쇠는 두 이름을 **정렬해 이어붙인** 것이라, 쪼개서 상대를 찾는다.
ME = "몰랑이"


def _bonds():
    data = (_one("molang_bonds", "data", id="eq.1").get("data") or {})
    mine, others = [], []
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        names = str(k).split("|")
        if len(names) != 2:
            continue
        row = {"level": round(float(v.get("warmth") or 0), 3),
               "times": int(v.get("met") or 0),
               "topics": [t for t, _ in sorted(
                   (v.get("topics") or {}).items(),
                   key=lambda kv: -kv[1])[:3]]}
        if ME in names:
            row["who"] = names[0] if names[1] == ME else names[1]
            mine.append(row)
        else:
            # **몰랑이가 없어도 맺어진 사이.** 이게 사회가 도는 증거다.
            row["who"] = " · ".join(names)
            others.append(row)
    mine.sort(key=lambda x: -x["level"])
    others.sort(key=lambda x: -x["level"])
    return {"mine": mine[:12], "others": others[:10]}


# ── 사회 ────────────────────────────────────────────────────────

def _society():
    soc = (_one("molang_society", "data", id="eq.1").get("data") or {})
    meets = soc.get("meets") or []

    # **소문은 목록이 아니라 묶음이다.**
    #   rumors = { "들은 이": ["누가 요즘 무슨 얘기를 하더라", …] }
    # 누가 무엇을 들었는지가 핵심이라, 들은 이로 묶어 보여준다.
    rumors = []
    for who, lines in (soc.get("rumors") or {}).items():
        if lines:
            rumors.append({"who": who, "lines": list(lines)[-4:][::-1]})

    # 어디서 몇 번 마주쳤나
    where = {}
    for m in meets:
        if isinstance(m, dict) and m.get("place"):
            where[m["place"]] = where.get(m["place"], 0) + 1

    # 최근 마주침 몇 개
    last = []
    for m in meets[-8:]:
        if not isinstance(m, dict):
            continue
        last.append({"a": m.get("a"), "b": m.get("b"),
                     "place": m.get("place"),
                     "topic": m.get("topic") or m.get("about")})
    last.reverse()

    return {
        "n_meets": len(meets),
        "where": sorted(where.items(), key=lambda kv: -kv[1])[:8],
        "last": last,
        "rumors": rumors[:6],
    }


# ── 근거 ────────────────────────────────────────────────────────
#
# 점수는 매기지 않는다. 대놓고 정보를 묻지 않으면 근거가 아예 안
# 딸려 오고, 와도 답과 글자가 겹칠 이유가 없다. 보이게만 한다.

def _evidence():
    rows = _get("molang_evidence", "type_id,sources,n_sources,created_at",
                order="id.desc", limit="12")
    out = []
    for r in rows:
        src = r.get("sources")
        if isinstance(src, str):
            src = _safe(lambda: json.loads(src), [])
        out.append({"type": r.get("type_id"),
                    "n": r.get("n_sources") or 0,
                    "sources": [str(s)[:90] for s in (src or [])][:5],
                    "at": r.get("created_at")})
    return out


# ── 꿈 ──────────────────────────────────────────────────────────
#
# molang_dreams: text, feeling, lingering, energy, drive,
#                pieces[], linger_why[]
# 꿈은 **겪은 것을 섞어 만든다.** pieces 가 그 재료라, 같이 보여준다.

def _dreams():
    rows = _get("molang_dreams",
                "text,feeling,lingering,energy,pieces,created_at",
                order="id.desc", limit="10")
    out = []
    for r in rows:
        if not r.get("text"):
            continue
        pieces = r.get("pieces")
        if isinstance(pieces, str):
            pieces = _safe(lambda: json.loads(pieces), [])
        out.append({"text": r["text"], "feel": r.get("feeling"),
                    "linger": r.get("lingering"),
                    "energy": r.get("energy"),
                    "pieces": [str(p)[:40] for p in (pieces or [])][:4],
                    "at": r.get("created_at")})
    return out


# ── 대화 ────────────────────────────────────────────────────────
#
# 두 가지가 따로 쌓인다.
#   molang_episodes    사람과 나눈 말 (owner 로 누구 기억인지 나뉜다)
#   molang_peer_talks  피우피우와 나눈 말 (place 가 있으면 그때 거기)
#
# 여행 중이면 place 가 호텔·산길 같은 여행지로 찍힌다. 그래서
# "여행 다니면서 나눈 말"이 따로 저장되는 게 아니라, **자리로 드러난다.**

def _talks():
    rows = _get("molang_episodes", "place,question,answer,emotion,created_at",
                owner="eq.molang", order="id.desc", limit="12")
    return [{"place": r.get("place"), "q": (r.get("question") or "")[:300],
             "a": (r.get("answer") or "")[:400],
             "emotion": r.get("emotion"), "at": r.get("created_at")}
            for r in rows]


def _peer():
    rows = _get("molang_peer_talks", "topic,molang,piupiu,place,created_at",
                order="id.desc", limit="14")
    return [{"topic": r.get("topic"), "place": r.get("place"),
             "molang": r.get("molang"), "piupiu": r.get("piupiu"),
             "at": r.get("created_at")} for r in rows]


# ── 기념품 ──────────────────────────────────────────────────────
#
# molang_travel.data.souvenirs = [{at, name, from}]
# 같은 물건이 집 안에도 놓인다. 어느 방에 뒀는지까지 보여야
# "가져와서 저기 뒀구나" 가 된다.

def _keepsakes(home_objects):
    tv = (_one("molang_travel", "data", id="eq.1").get("data") or {})
    room_of = {}
    for room, items in (home_objects or {}).items():
        for it in (items or []):
            nm = it.get("name") if isinstance(it, dict) else str(it)
            if nm:
                room_of[nm] = room
    out = []
    for s in (tv.get("souvenirs") or []):
        if not isinstance(s, dict) or not s.get("name"):
            continue
        out.append({"name": s["name"], "from": s.get("from"),
                    "at": s.get("at"), "room": room_of.get(s["name"])})
    out.reverse()
    return out[:12]


# ── 자란 길 ─────────────────────────────────────────────────────
#
# 언제 무엇이 **처음** 생겼나. 네 군데에 따로 적히고 있다.
#   molang_land.layout.log    지형이 생긴 날
#   molang_village.data.born  모임에서 지은 곳
#   molang_travel.data.trips  여행을 떠난 날
#   molang_pinko.data         핀코를 알게 된 날
# 한 줄로 모아야 자란 게 보인다.

def _timeline():
    ev = []

    def add(at, kind, what, why=""):
        if at and what:
            ev.append({"at": float(at), "kind": kind,
                       "what": str(what), "why": why})

    ld = (_one("molang_land", "layout", id="eq.1").get("layout") or {})
    for r in (ld.get("log") or []):
        add(r.get("at"), "땅", r.get("kind"),
            ", ".join(r.get("from") or []) + " 에서" if r.get("from") else "")

    vg = (_one("molang_village", "data", id="eq.1").get("data") or {})
    for r in (vg.get("born") or []):
        add(r.get("at"), "마을", r.get("name"), "모임에서 지었어요")

    tv = (_one("molang_travel", "data", id="eq.1").get("data") or {})
    for r in (tv.get("trips") or []):
        s = r.get("souvenir")
        add(r.get("at"), "여행", r.get("where"),
            f"{s} 를 가져왔어요" if s else "")

    pk = (_one("molang_pinko", "data", id="eq.1").get("data") or {})
    for place, v in pk.items():
        if isinstance(v, dict) and v.get("known"):
            add(v.get("known_at"), "이웃", v.get("name"),
                f"{place}에서 알게 됐어요")

    ev.sort(key=lambda e: -e["at"])
    return ev[:24]


# ── 목적 ────────────────────────────────────────────────────────
#
# molang_purposes 에 판본이 다 남아 있다. status='core' 가 핵심 목적,
# 'active' 가 지금 품은 하위 목적. 사람이 승인한 것만 들어온다.

def _purposes():
    rows = _get("molang_purposes", "purpose,why,status,created_at",
                order="id.asc", limit="80")
    core = [{"text": r.get("purpose"), "why": r.get("why"),
             "at": r.get("created_at")}
            for r in rows if r.get("status") == "core" and r.get("purpose")]
    now = [{"text": r.get("purpose"), "at": r.get("created_at")}
           for r in rows if r.get("status") == "active" and r.get("purpose")]
    return {"core": core[-8:], "now": now[-8:][::-1]}


# ── 오늘 마음 ───────────────────────────────────────────────────
#
# organism_state.moods 에 마지막 120개가 쌓인다. 맨 끝이 지금 기분.

def _mood():
    rows = (_one("organism_state", "moods", id="eq.1").get("moods") or [])
    if not rows:
        return {}
    m = rows[-1] if isinstance(rows[-1], dict) else {}
    return {"name": m.get("name"), "note": m.get("note")}


# ── 아직 지도에 안 붙은 자리 ──────────────────────────────────
# atlas.rebuild 는 **밤 워커에서만** 돈다. 그래서 낮에 생긴 자리는
# 다음 날 새벽까지 지도에 없다. 생겼다는 소식은 streamlit 에 뜨는데
# 지도에는 없으니 사라진 것처럼 보인다.
#
# 그래서 여기서 molang_village · molang_land 를 직접 보고, 지도에
# 없는 이름을 atlas.py 와 **같은 식**으로 임시로 놓는다. 자리를
# 저장하지는 않는다 — 자리를 정하는 건 끝까지 atlas 의 일이다.
# 밤이 지나면 atlas 가 같은 식으로 계산해 같은 칸에 박아 넣는다
# (이미 찬 칸이면 옆으로 밀리므로 한 칸 정도는 달라질 수 있다).

def _unplaced(view):
    W, H = (view.get("size") or [21, 15])[:2]
    bx, by, bw, bh = VILLAGE_BOX
    spots = view.setdefault("spots", {})
    taken = {tuple(v.get("xy") or (-1, -1)) for v in spots.values()}

    def put(name, xy, zone, extra=None):
        x, y = xy
        for r in range(0, max(W, H)):            # 찬 칸이면 옆으로
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    px, py = x + dx, y + dy
                    if not (0 <= px < W and 0 <= py < H):
                        continue
                    if (px, py) in taken:
                        continue
                    taken.add((px, py))
                    spots[name] = {"xy": [px, py], "zone": zone,
                                   "icon": _ICON.get(
                                       name, "🏡" if zone == "village"
                                       else "📍"),
                                   "fresh": True, **(extra or {})}
                    return
        return

    # 마을 — 가운데 칸, SOM 좌표의 차례만 가져온다
    vg = (_one("molang_village", "data", id="eq.1").get("data") or {})
    for name, p in sorted((vg.get("places") or {}).items(),
                          key=lambda kv: tuple(
                              (kv[1] or {}).get("at") or (0, 0))):
        if name in spots or not isinstance(p, dict):
            continue
        at = p.get("at") or (0, 0)
        put(name, (bx + int(at[1]) % bw, by + int(at[0]) % bh), "village")

    # 바깥 — 거리만큼 바깥 고리로, 방향은 이름의 해시
    cx, cy = bx + bw / 2, by + bh / 2
    ld = (_one("molang_land", "layout", id="eq.1").get("layout") or {})
    for p in (ld.get("places") or []):
        name = (p or {}).get("kind")
        if not name or name in spots:
            continue
        dist = float(p.get("dist") or 3.0)
        ring = min(max(bw, bh) / 2 + 1.5 + dist * 0.55, min(W, H) / 2 - 1)
        ang = (sum(ord(c) for c in name) % 360) * math.pi / 180
        put(name, (int(cx + ring * math.cos(ang)),
                   int(cy + ring * math.sin(ang) * 0.75)),
            "land", {"dist": dist})


def world():
    import time

    atlas = (_one("molang_atlas", "data", id="eq.1").get("data") or {})
    view = {"size": atlas.get("size") or [21, 15],
            "spots": atlas.get("spots") or {}, "who": {}}
    _safe(lambda: _unplaced(view), None)

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

    # ── 여기부터가 넓힌 쪽 ──
    # 여태까지 Streamlit 사이드바에서만 보이던 것들이다. 보는 것은
    # 이쪽으로 옮기고, 대화와 승인은 그대로 둔다.
    view["bonds"] = _safe(_bonds, {})
    view["society"] = _safe(_society, {})
    view["evidence"] = _safe(_evidence, [])
    view["dreams"] = _safe(_dreams, [])
    view["talks"] = _safe(_talks, [])
    view["peer"] = _safe(_peer, [])
    view["keepsakes"] = _safe(
        lambda: _keepsakes((view.get("home") or {}).get("objects")), [])
    view["timeline"] = _safe(_timeline, [])
    view["purposes"] = _safe(_purposes, {})
    view["mood"] = _safe(_mood, {})

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
