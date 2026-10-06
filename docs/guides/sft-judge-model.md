# SFT 판정기(`exaone-sft-judge`) 등록과 되돌리기

시연 질의는 **E1 추출 답 + SFT 판정기**로 돈다(2026-10-06 채택). 판정기는 검색 1위 카드가 질문에 답하는지 0~3점으로 매기고 2점 미만이면 "해당 지식 없음"으로 끝낸다. 답 본문은 모델이 아니라 카드에서 만든다(E1).

## 무엇인가

| 항목 | 내용 |
|---|---|
| 기반 | `LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct` (Jetson의 `exaone3.5:2.4b-instruct-q4_K_M`과 같은 기반) |
| 학습 | LoRA(r=16, α=32) 3에폭, 카드에서 만든 합성 질문 655개(점수 0~3). 평가 문항은 학습에 쓰지 않았다 |
| 배포 파일 | `exaone-sft-judge-Q4_K_M.gguf` (1.50GB, git에 올리지 않음). SHA-256 `e96e0940b054e02e6fe1e5006d841b2331f63cf45308bef99c9bae27a331eced` |
| 보관 위치 | PC `C:\Users\abab9\models-sft\judge\`, Jetson `~/sft/judge/` (`Modelfile` 포함) |
| 재현 자료 | 데이터·스크립트·사전 등록·결과는 저장소 밖 `ShiftLink-records/experiments/sft1006/`. GGUF 변환은 llama.cpp(5e03bdd)의 EXAONE 변환기 한 줄 수정이 필요했다 |

## 채택 근거 (요약)

- 블라인드 4종 최종 셋 66문항: 답 있음 통과 13 → 12(−1), 답 없음 거절 10 → **19**(+9), 판정 p95 0.91 → 0.80초
- 새 블라인드 문항(B3-011~020) 8문항: 통과 2·2, 거절 1·1로 같음(사전 등록 규칙 충족)
- 기준 판정기만 쓴 E1을 처음 보는 질문 30개에 채점하면 미충족 12개인데, SFT 판정기는 그중 12개를 막았고 막은 문항에 충족은 하나도 없었다
- 한계: 맞는 답을 거절할 수 있다(개발 셋에서 4건). 시연 질문 9개(HPU·GR·CV)는 9/9 통과했다

## Jetson에 등록

```bash
# GGUF와 Modelfile이 ~/sft/judge/ 에 있다고 가정 (없으면 PC에서 scp)
cd ~/sft/judge
sha256sum exaone-sft-judge-Q4_K_M.gguf     # 위 해시와 같아야 한다
ollama create exaone-sft-judge -f Modelfile
ollama list | grep exaone-sft-judge
```

`Modelfile`은 `FROM ./exaone-sft-judge-Q4_K_M.gguf`와 EXAONE 3.5 채팅 템플릿, `temperature 0`, 종료 토큰 `[|endofturn|]`로 구성된다.

## 켜기

`deploy/install_service.sh mes`가 서비스에 두 환경변수를 넣는다.

- `SHIFTLINK_ANSWER_MODE=extract` (기본): 질의 답을 카드에서 만들고 모델을 부르지 않는다
- `SHIFTLINK_JUDGE_MODEL=exaone-sft-judge` (기본): 판정기 모델 이름. 바꾸려면 `JUDGE_MODEL=…`로 실행

이미 등록된 서비스는 다시 실행하면 unit이 갱신된다(`sudo systemctl daemon-reload` 포함).

```bash
deploy/install_service.sh mes
journalctl -u shiftlink-mes -f
```

## 되돌리기

- 판정기만 기준 모델로: `JUDGE_MODEL=exaone3.5:2.4b-instruct-q4_K_M deploy/install_service.sh mes`
- 모델이 답을 쓰게: `ANSWER_MODE=model deploy/install_service.sh mes`

## 주의

- **판정 모델이 Ollama에 없으면 판정이 실패하고, 코드는 판정을 건너뛰고 계속 진행한다.** E1 모드에서는 판정 없이 카드 내용이 그대로 나간다. 서비스를 켜기 전에 `ollama list`로 모델 등록을 꼭 확인한다.
- 판정기는 처음 한 번 모델을 올리느라 20초 넘게 걸린다. 시연 전에 질문 하나를 먼저 보내 두면 된다.
