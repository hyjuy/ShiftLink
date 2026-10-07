# 장비 디테일과 작동 모션 검증

2026-10-07

기존 FBX 모델에 Unity 런타임 부품을 추가한다. 롤러·드럼의 회전 표시와 끝단 볼트, 감속기 출력 플랜지 볼트, HPU 모터 냉각팬·보호망·오일 냉각기, CAU 냉각팬·보호망, RT-02 승강 실린더·가이드, CV-02 측벽·배출 립, PDP 문 경첩을 보강했다.

롤러와 드럼은 기존 MES 속도와 반지름으로 회전한다. HPU와 CAU 팬은 해당 장비가 가동 중이고 라인이 가동 중일 때만 회전한다. 대기, 심각한 고장, 정지, 일시정지, 상태 누락, 통신 단절에서는 멈춘다. 측정 RPM이 없어 팬 회전은 360도/초의 시각화용 속도다. 펌프 내부 임펠러 대신 외부에서 관찰 가능한 모터 냉각팬을 움직인다. 치수와 추가 부품 형상은 기존 합성 모델의 가정이며 실장비 도면과 대조하지 않았다.

검증은 `FactoryMotionChecks.Run`을 사용한다.

```powershell
& 'D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe' -batchmode -force-d3d11 -projectPath 'D:/obsd/Projects/ShiftLink/unity/ShiftLinkFactory' -executeMethod FactoryMotionChecks.Run -logFile 'D:/obsd/Projects/ShiftLink/tmp/equipment-motion-red.log'
```

추가한 검사에서 구현 전 `Pump and compressor require visible guarded fan rotors` 실패를 확인했다. 구현 후 Unity 컴파일과 모션 검사 모두 통과했다. 기존 롤러 수(12/16/12), 코일 이송·객체 유지, 스크랩 분기 검사도 통과했다. 0·음수·NaN·무한대 시간 간격에서 모션이 변하지 않는지 확인했다.

`unity/ShiftLinkFactory/Checks/equipment-detail-EQ-*.png`에 장비 6종의 근접 화면을 생성했다. HPU, CAU, RT-02, CV-02 화면에서 팬·보호망과 이송부 형상을 시각 확인했다. 검사 결과는 같은 디렉터리의 `motion-result.txt`에 기록한다. 로그와 렌더는 로컬 검증 산출물이며 Git에 포함하지 않는다.
