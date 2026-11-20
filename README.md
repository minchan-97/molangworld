# 보는 쪽만 Vercel — 3번 길

```
Streamlit   대화 · 승인 · pkl 옮기기   (그대로)
Vercel      지도 · 사이 · 사회 · 근거  (여기를 넓혔다)
Supabase    둘이 같은 곳을 본다
```

## 왜 채팅은 안 옮겼나

몰랑이가 답하려면 유형 고르기 → 트리 걷기 → 기억 꺼내기 →
groundcheck 가 다 돌아야 하는데, 그건 엔진 쪽에만 있다.
여기서 LLM 을 따로 부르면 **기억은 같은 Supabase 에 남아도
그 기억을 만든 길이 둘로 갈린다.** 경로도 안 남고 가드도 안 거친다.

그게 진짜로 연속성을 해치는 쪽이라, 이 배포는 끝까지 **읽기만** 한다.

## 먼저 고친 것 둘

| 전 | 후 | 왜 |
|---|---|---|
| `manifest.py` | `manifest.json` | index.html 이 `/manifest.json` 을 찾는다 — 웹앱 아이콘이 안 붙던 이유 |
| `requirements .txt` | **없앰** | 이름에 빈칸이 있어 Vercel 이 못 찾았고, world.py 는 표준 라이브러리만 쓴다 |

## 넓힌 것

탭 넷이 생겼다. 지도는 그대로고 셋이 늘었다.

- **🫂 사이** — 누구와 얼마나 가까운가, 몇 번 만났나
- **🏘️ 사회** — 마주침 수, 어디서 자주 만났나, 최근 마주침, 떠도는 말
- **📎 근거** — 최근 대화마다 무엇을 꺼내 보고 말했나 (점수는 안 매긴다)

## 올릴 것

```
index.html            탭 넷
api/world.py          bonds · society · evidence 를 더 읽는다
manifest.json         (이름 고침)
vercel.json  icon.svg  apple-touch-icon.png  LICENSE
```

`requirements .txt` 는 **지우세요.**

환경변수는 그대로 `SUPABASE_URL` 과 `SUPABASE_ANON_KEY` 입니다.

---

## 한 가지 확인이 필요합니다

`molang_bonds` 표의 열 이름을 몰라서, **여러 모양을 다 받도록**
짰습니다 (한 줄에 한 쌍이어도, `data` 한 덩이여도 읽습니다).
그래도 안 맞으면 "사이" 칸이 비어 보일 거예요.

한 줄만 돌려서 알려주시면 정확히 맞추겠습니다.

```sql
select * from molang_bonds limit 3;
```

사회 탭의 **떠도는 말**도 같습니다. `molang_society` 의 `data` 안에서
`rumors / talk / hearsay / said` 중 하나를 찾는데, 이름이 다르면
그 칸만 비어요.

```sql
select jsonb_object_keys(data) from molang_society where id = 1;
```

나머지(지도·발자국·근거)는 표 모양을 아는 것들이라 그대로 뜹니다.
