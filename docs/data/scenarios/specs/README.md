# 합성 사건 명세

[`shiftlink.data.scenario`](../../../../shiftlink/data/scenario.py)의 입력이다.
여기서 [시나리오 파일](../)이 만들어진다.

```powershell
python -m shiftlink.data.scenario --spec docs/data/scenarios/specs/<파일>.json `
  --scenarios docs/data/scenarios artifacts/scenarios
```

## 명세에 쓰는 것과 도구가 채우는 것

작성자는 사람만 정할 수 있는 것을 쓴다. 나머지는 도구가 계산한다.

| 작성자 | 도구 |
|---|---|
| 증상·관측·운전 컨텍스트 | 사건·관측·컨텍스트 ID 발급 |
| `true_cause`, `true_actions` | 원형 계보 판정과 split 해시 배정 |
| 관측자 페르소나 배정 | 카나리 토큰 발급 |
| 원형 식별 4키 | 기준정보 참조·부품 귀속 검증 |

`true_cause`와 `true_actions`는 **필수 입력**이다. 모델이 정답지를 만들면 평가가
무의미해지므로 도구가 생성하지 않는다.

## 주의

- `group_id`는 해시 결과를 보기 전에 원문 계보로 확정한다. 원하는 split이 나올
  때까지 ID를 바꾸지 않는다([분할 계약 §63](../../policies/source-and-split-contract.md)).
- 같은 원형 식별 4키를 쓰면 새 계보를 열지 않고 기존 프로토타입을 상속한다.
- 부품은 실존 여부뿐 아니라 소속 설비까지 대조한다. 다른 설비의 실제 부품 ID는
  실존 검사만으로는 통과한다.
- 도구는 배정표를 고치지 않고 제안만 낸다. 등록은 사람이 한다.

## 현재 명세

| 파일 | 사건 | 프로토타입 | split |
|---|---|---|---|
| `lubrication_starvation.json` | EV-0034 | PT-0017 | dev |
| `no_fault_variation.json` | EV-0035 | PT-0018 | kb |
| `restart_blocked.json` | EV-0036 | PT-0019 | dev |

모두 합성이며 수치는 실제 설비 값이 아니다.
