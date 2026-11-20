# 보는 쪽만 Vercel — 3번 길

```
Streamlit   대화 · 승인 · pkl 옮기기   (그대로)
Vercel      지도 · 사이 · 사회 · 대화 · 꿈 · 근거
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

## 탭 여섯

| 탭 | 읽는 표 | 보이는 것 |
|---|---|---|
| 🗺️ 동네 | `molang_atlas` `molang_steps` | 지형·길·하루 되감기 (그대로) |
| 🫂 사이 | `molang_bonds` | 몰랑이와 가까운 사이, **몰랑이 없이 맺어진 사이** |
| 🏘️ 사회 | `molang_society` | 마주침, 어디서, 최근, **누가 무슨 말을 들었나** |
| 💬 대화 | `molang_peer_talks` `molang_episodes` | 피우피우와 나눈 말, 나와 나눈 말 |
| 💭 꿈 | `molang_dreams` | 꿈과 **그 꿈의 재료** |
| 📎 근거 | `molang_evidence` | 그때 무엇을 꺼내 보고 말했나 |

## 여행 중 대화는 어떻게 보이나

따로 저장되는 게 아니라 **자리로 드러난다.**

`molang_peer_talks` 에 `place` 가 같이 적히는데, 여행 중이면
거기가 호텔·산길 같은 여행지다. 그래서 대화 탭에서 이렇게 뜬다.

```
📍 호텔   빵 만들기        11. 20. 오후 12:10
🐰 오늘, 우유식빵 만드는 법을 봤어…
🐤 우와! 몰랑이가 빵 만드는 걸 좋아하는구나!
```

집에 있을 때 나눈 말에는 자리가 안 붙는다. 그 차이가 그대로 보인다.

## 표 모양은 저장소에서 확인했다

지난번에 "bonds 열 이름을 몰라 여러 모양을 받도록 짰다"고 했는데,
저장소를 열어 **정확한 꼴을 찾아 그대로 맞췄다.** 추측이 아니다.

```
molang_bonds      id=1, data = { "몰랑이|피우피우": {warmth, met, talks[], topics{}} }
molang_society    id=1, data = { meets[], rumors{들은이: [말]}, log[] }
molang_dreams     text, feeling, lingering, energy, pieces[], linger_why[]
molang_peer_talks topic, molang, piupiu, place, source
molang_episodes   owner, place, question, answer, emotion
```

소문이 **목록이 아니라 묶음**이었다. 전에 쓴 코드로는 사회 탭이
통째로 비었을 것이다 — 고쳤다.

## 올릴 것

```
index.html            탭 여섯
api/world.py          bonds · society · dreams · talks · peer · evidence
manifest.json         (이름 고침)
vercel.json  icon.svg  apple-touch-icon.png  LICENSE
```

`requirements .txt` 는 **지우세요.**
환경변수는 그대로 `SUPABASE_URL` 과 `SUPABASE_ANON_KEY` 입니다.

새 표를 읽으니 **anon 키에 읽기 권한(RLS)** 이 열려 있어야 합니다.
사이·사회·꿈·대화 칸이 비면 그쪽부터 보세요.
