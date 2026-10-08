# 클라우드 연결 끊김 복구 시험 계획 (W3-3 · G4) — 2026-10-08

계획서의 원래 이름은 "랜선 끊김 시험"이다.
**무엇을 보는가**: Jetson과 Aiven 사이 인터넷이 끊긴 동안 현장에서 만든 인계·질의가 Jetson에 남고, 연결이 돌아오면 클라우드에 **빠짐없이, 한 번씩만** 올라가는가.

## 0. 기준값 (10/8 09:56 KST, Claude, 읽기만 함)

| 항목 | 값 |
|---|---|
| `/api/outbox` 인계 | 대기 0 · 업로드 2 · 충돌 0 |
| `/api/outbox` 질의 | 대기 0 · 업로드 199 · 충돌 0 |
| Aiven `handover_upload` | 2행 |
| Aiven `query_upload` | 199행 |
| `check_upload_recon.py` | 로컬 2 · 일치 2 · 누락 0 · 충돌 0 · 클라우드에만 0 → **OK, exit 0** |
| 업로더 | `shiftlink-uploader` active, 30초 주기, DB `~/shiftlink/data/mock-mes.sqlite3` |
| Jetson 네트워크 | **Wi-Fi(wlP1p1s0)만 사용, 유선(enP8p1s0) DOWN** |

## 1. 끊는 방법: 랜선 대신 Aiven 포트만 막는다

Jetson은 유선을 쓰지 않아 뽑을 랜선이 없다. Wi-Fi를 끄면 Tailscale까지 끊겨 PDA(파이)와 SSH도 같이 죽는다. 그러면 끊긴 동안 PDA로 인계를 만들 수 없다.

그래서 **Jetson에서 Aiven DB 포트로 나가는 연결만 방화벽으로 거절**한다. 현장 네트워크(PDA↔Jetson)는 살아 있고 클라우드만 끊긴 상황이다. 실제로 가장 흔한 "공장 내부망은 되는데 인터넷이 끊긴" 경우와 같다.
- 코드나 설정 파일은 건드리지 않는다. 업로더 입장에서는 진짜 접속 실패다.
- 규칙은 재부팅하면 사라진다(영구 저장 안 함).

## 2. 역할

| 누가 | 하는 일 |
|---|---|
| 재영 또는 현준 | Jetson 별도 터미널에서 sudo 명령(차단·해제) |
| 현준 | PDA에서 인계 2건·질의 2건 만들기 |
| Claude | 각 단계 확인 명령 실행·기록, 결과 `RESULT.md` |
| 재영 | 입회 |

## 3. 절차 (약 20분)

| 단계 | 하는 일 | 확인 (Claude) | 통과 조건 |
|---|---|---|---|
| 1 | **차단**: Jetson 터미널에서 아래 "차단" 명령 | 대사 스크립트 | `cloud unreachable`, exit 2. 업로더 로그에 오류 종류만(비밀값 없음) |
| 2 | **끊긴 상태에서 작업**: PDA로 인계 2건 작성·저장, 증상 질의 2건 | `/api/outbox` | 인계 대기 **2**, 질의 대기 **2**. PDA 화면에 '업로드 대기 2건' 표시. 질의 답은 정상으로 나옴 |
| 3 | **버티기**: 업로더 2주기(60초 이상) 기다림. 이어서 `sudo systemctl restart shiftlink-uploader` | `/api/outbox`, 서비스 상태 | 대기 2·2 유지, 업로더 active(재시작해도 대기 건이 사라지지 않음) |
| 4 | **복구**: 아래 "해제" 명령 | — | — |
| 5 | **재전송 확인**: 최대 90초 대기 | `/api/outbox`, 대사 스크립트, Aiven 건수 | 대기 0·0, recon **OK exit 0**, Aiven 인계 **4행**(2+2), 질의 **201행**(199+2), 누락 0·충돌 0 |
| 6 | **중복 확인**: 업로더를 한 번 더 재시작하고 1주기 뒤 다시 셈 | Aiven 건수 | 4행·201행 그대로(다시 올려도 늘지 않음) |
| 7 | 기록 | `RESULT.md` | 단계별 시각·건수·새 ID 4개 |

새 질의 2건은 Aiven `query_upload`에서 ID와 내용 해시가 로컬과 같은지 따로 확인한다. 대사 스크립트는 인계만 대조하기 때문이다.

## 4. 명령 (Jetson 터미널, sudo 필요)

```bash
# 차단 — 포트는 접속 파일에서 읽고 화면에 주소를 찍지 않는다
set -a; . ~/shiftlink/aiven.env; set +a
PORT=$(python3 -c "import os,urllib.parse;print(urllib.parse.urlsplit(os.environ['MYSQL_DATABASE_URL']).port)")
sudo iptables -I OUTPUT -p tcp --dport "$PORT" -j REJECT && echo "차단됨"

# 해제 (같은 터미널에서)
sudo iptables -D OUTPUT -p tcp --dport "$PORT" -j REJECT && echo "해제됨"
```

중간에 문제가 생기면 언제든 "해제" 명령을 실행한다. 재부팅해도 규칙은 사라진다.

## 5. 결과 판정

- **W3-3 2점**: 5·6단계 통과(누락 0·중복 0, 대기 0).
- **G4**: W2-4(이미 2점)와 W3-3이 모두 2점이면 통과.
- 하나라도 실패하면 단계·시각·건수를 그대로 적고, 원인을 찾은 뒤 다시 시험한다.

결과는 저장소 밖 `ShiftLink-records/experiments/netcut1008/RESULT.md`에 적고, 요약을 이 문서 아래에 덧붙인다.
