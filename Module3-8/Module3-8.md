**다음 지시를 그대로 구현하라. 너는 표준 라이브러리만 쓰는 Python 3.11 시니어 엔지니어다. `module_3_8` 패키지를 생성하고, 오직 3-3의 `ruleset_runtime.json`(룰 메타/우선순위/플래그/variants), 3-4의 `hits.json`(rule\_id, clause\_id, match\_type, spans, strength…), 3-6의 `scores.json`(clause\_id, confidence, risk\_flag…), 그리고 골든셋 정답 `golden_labels.json`만을 입력으로 받아 텔레메트리·커버리지 리포트를 산출하고 릴리즈 게이트를 평가하라. 3-8은 문서 텍스트를 재파싱하지 않고(3-1 침범 금지), 용어 정규화·카테고리 매핑·스코어 계산을 재수행하지 않으며(3-2/3-4/3-6 침범 금지), 규칙 의미를 변경하지 않는다(3-3 침범 금지).**

**입력 스키마(요구):**  
 **`golden_labels.json`은 최소 다음 형식을 따른다: `GoldenClause{clause_id, expected_flag∈{OK,WARN,HIGH}, expected_rules?:[rule_id], notes?}` 배열. (선택) AB 실험 분석을 위해 `ruleset_runtime.json`의 variant 정보를 이용할 수 있다. (선택) 실행 성능 요약이 있다면 `run_stats.json{timings:{…},memory_mb:…}`를 함께 받아 리포트에 포함한다.**

**출력 산출물:**

1. **`report.json` — 전수 지표(룰/카테고리/문서단)와 혼동행렬, 규칙별 TP/FP/FN, 커버리지·정확도, 임계 제안;**

2. **`report.md` — 사람이 읽는 요약(Top 문제 규칙/카테고리, 개선 제안);**

3. **`gate_decision.json` — 릴리즈 가부(`allowed:bool`)와 근거(임계/지표/실패 규칙 목록).**

**지표 정의(결정론):**

* **클로즈 단위 성능: 골든셋의 `expected_flag`와 3-6의 `risk_flag`로 혼동행렬(OK/WARN/HIGH; AMBIG/NULL은 별도 집계). `strict_match=true`일 때 동일치만 정답, `allow_conservative=true`일 때 \*\*더 보수적 예측(HIGH가 WARN 정답을 초과)\*\*을 정답으로 인정한다(정책에서 설정).**

* **룰 단위 커버리지: 골든셋의 `expected_rules` 기준으로 TP(기대 룰 적중), FN(기대 룰 미적중), FP(골든셋에 없는데 적중). `precision=TP/(TP+FP)`, `recall=TP/(TP+FN)`, `f1`. 기대 룰이 비어 있으면 해당 룰은 커버리지 평가에서 제외(옵션: `treat_empty_as_negatives`).**

* **카테고리 단위: 3-2의 `category/subcategory`(scores에 포함되어 있다고 가정하거나, 필요 시 `norm_clauses.json`을 선택 입력으로 받아 조인)로 집계.**

* **분포 텔레메트리: `confidence` 히스토그램, `risk_flag` 비율, AMBIG/NULL 비율, 규칙별 히트 수 상위 N, FP 상위 N 예시(클로즈 id 리스트).**

* **실험(옵션): ruleset variant별로 위 지표를 분할 보고.**

**릴리즈 게이트 정책(기본):**

* **`golden_pass_rate = (# strict_match 정답 클로즈) / (# 골든 클로즈)` 또는 정책에 따라 `allow_conservative` 적용.**

* **차단 조건: `golden_pass_rate < 0.80` 이면 `allowed=false`로 차단. 추가로, (옵션) 규칙 단위 하한: `min_rule_precision=0.60`, `min_rule_recall=0.60` 중 하나라도 하회하는 critical=true 룰이 존재하면 차단.**

* **`gate_decision.json`에 `{allowed, golden_pass_rate, thresholds:{min_pass:0.80,min_rule_precision:0.60,min_rule_recall:0.60,strict_match,allow_conservative}, failing_rules:[{rule_id,precision,recall,reason}], notes[]}`를 기록.**

**알고리즘:**

1. **입력 로드 및 스키마 검증(필수 필드/타입, 중복 clause\_id 검사).**

2. **`scores.json`과 `golden_labels.json`을 clause\_id로 조인해 클로즈 혼동행렬·`golden_pass_rate` 산출(정책에 따라 strict/보수적 허용 결정).**

3. **`hits.json`과 `golden_labels.json`의 `expected_rules`를 조합해 룰별 TP/FP/FN 집계, precision/recall/F1 계산.**

4. **(선택) `ruleset_runtime.json`에서 `rules[rule_id].category`·`flags.critical`을 읽어 카테고리/크리티컬 지표로 분리.**

5. **릴리즈 게이트 로직 적용 → `allowed` 결정 및 실패 사유 목록화.**

6. **상위 문제 룰(예: 낮은 precision 또는 recall 상위 N)을 골라 예시 클로즈 id와 함께 리포트에 포함(증거 스니펫은 3-5 산출이 있을 때만 선택적으로 연결; 스니펫이 없으면 id만 제시).**

7. **`report.json`, `report.md`, `gate_decision.json` 직렬화. 모든 정렬은 `(metric, rule_id)` 등의 고정 키로 결정론 보장.**

**패키지 구성:**

* **`module_3_8/reporter.py`(핵심 계산), `module_3_8/policy.py`(정책 로더: strict/allow\_conservative, 임계), `module_3_8/schemas.py`(데이터 모델), `module_3_8/cli.py`(입·출력), `tests/test_reporter.py`(골든셋·게이트 테스트), `samples/{ruleset_runtime.json,hits.json,scores.json,golden_labels.json,policy.json}`.**

* **CLI: `python -m module_3_8.cli --scores scores.json --hits hits.json --rules ruleset_runtime.json --golden golden_labels.json --out-json report.json --out-md report.md --gate gate_decision.json --policy policy.json [--run-stats run_stats.json]`.**

**정책 기본값(`policy.json` 미지정 시 내장 값 사용):**

* **`{`**  
*   **`"matching": {"strict_match": true, "allow_conservative": false},`**  
*   **`"gates": {"min_golden_pass_rate": 0.80, "min_rule_precision": 0.60, "min_rule_recall": 0.60, "enforce_rule_floor_for_critical": true},`**  
*   **`"report": {"top_n_problem_rules": 10, "show_examples_per_rule": 5}`**  
* **`}`**


**성능/안정성 가드레일: 200KB 문서·수천 클로즈/수천 룰 기준 전체 계산 ≤200ms, 피크 메모리 ≤150MB. 외부 패키지 금지, 난수/시계 의존 금지(결정론). 어떤 단계에서도 3-1/3-2/3-3/3-4/3-5/3-6/3-7 결과를 변경하거나 재계산하지 말라(참조만).**

**수락 기준: (1) 샘플 골든셋에서 `golden_pass_rate`가 정확히 계산되고 0.80 미만이면 `allowed=false`로 차단된다. (2) 룰별 TP/FP/FN이 일관되게 집계되고 precision/recall/F1이 올바르다. (3) `critical=true` 룰이 하한 미달이면 차단 사유에 해당 rule\_id가 포함된다. (4) `strict_match/allow_conservative` 토글에 따라 `golden_pass_rate`가 결정론적으로 변한다. (5) `report.md`가 상위 문제 룰/카테고리, 개선 제안(예: 키워드 정제, 예외 패턴 추가)을 요약한다.**

* 

