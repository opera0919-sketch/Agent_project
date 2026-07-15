# ISA 문제은행 검증·수정 프로세스 (Audit & Correction Pipeline)

업로드된 `instructions/02_qa_audit_prompt.md`를 **재사용 가능한 실행 프로세스**로
정착시킨 문서다. 문제은행을 `생성(Generator) → 검증(Validator) → 수정(Corrector)`
3단계로 관리한다.

```
[Generator] ──► [Validator] ──► [Corrector] ──► (재검증)
 문항 생성       오류 검증        오류 수정         PASS까지 반복
```

## 단계별 실행

### 1단계: Generator (생성)
- 근거: `instructions/01_generation_master_prompt.md`
- 산출: `isa_qa_batchNN.jsonl` (스키마는 `../schema.md`)
- 원칙: 현행 시행 법령만, 조문/수치 확신이 낮으면 `verification_needed=true`.

### 2단계: Validator (검증) — 2계층

**(A) 기계 검증 — `validate.py` (자동화)**
QA Audit Prompt의 10대 영역 중 기계적으로 판정 가능한 항목을 자동화한다.

```bash
python3 audit/validate.py isa_qa_batchNN.jsonl
```

자동 검증 항목:
- JSON 유효성 / 필수 필드·타입 (③ 논리·⑩ 데이터품질 일부)
- `id` 형식·유니크, `related_ids` 무결성
- 난이도 분포(⑨) vs 목표 20/20/30/30
- 대분류 커버리지(⑧) 집계
- 중복 질문 간이 탐지(⑦, 정규화 후 완전일치)
- 계산형 문항의 `calculation` 존재(②의 형식 요건)
- `verification_needed` 문항 목록화

**(B) 내용 검증 — LLM Auditor (수동/반자동)**
기계가 판정할 수 없는 **사실·계산·법령**은 `02_qa_audit_prompt.md`의 감사인
역할로 문항별 검증한다. 10대 검증 영역:

| # | 영역 | 핵심 확인 |
|:--:|---|---|
| ① | 법령 | 법령명·조문 번호·항·호 정확성, 최신 시행 여부 |
| ② | 계산 | 수식·검산 1원 단위 일치 (불일치 시 FAIL) |
| ③ | 논리 | 질문→정답→해설→근거→계산식 일관성 |
| ④ | 조건 | 소득기준·가입기간 등 전제조건 명시 |
| ⑤ | 실무 | 증권사 전산·중도인출 등 현업 정합성 |
| ⑥ | 예외 | 사망·이주·특별해지·연금전환 등 특수케이스 |
| ⑦ | 중복 | 숫자·표현만 바꾼 유사문항 |
| ⑧ | 커버리지 | 분야 균형, 누락 분야 |
| ⑨ | 난이도 | 20/20/30/30 분포 |
| ⑩ | 데이터품질 | 정형 포맷·청크 분할·intent 매핑 적합성 |

판정 기준: **'기본적으로 오류가 존재한다'는 비판적 관점**에서 교차검증.
Zero-Tolerance: 환각(없는 조문)·계산오류·조건누락·법령상충·실무괴리·중복.

### 3단계: Corrector (수정)
- Validator가 FAIL 처리한 문항을 원문 수정 후 **2단계로 되돌려 재검증**.
- 에러 0건이 될 때까지 반복. 수정 이력은 `audit_report_batchNN.md`에 기록.

## 출력 산출물

- **개별 문항 검증 결과**: 최종판정(PASS/FAIL), 오류유형, 수정 전/후, 수정 이유,
  법적 근거 (템플릿은 `02_qa_audit_prompt.md` §5).
- **종합 감사 보고서**: 합격률, 오류유형별 통계, 커버리지·난이도 분포, AI 학습
  적합성 등급(A~F), 종합 품질점수 → `audit_report_batchNN.md`.

## verification_needed 문항의 취급

`verification_needed=true`는 "감사 미완료(사람 확인 대기)"를 뜻한다. 원문 법령으로
확정되면 `verification_needed=false`로 갱신하고 근거를 확정 기재한다. 평가셋
사용 시에는 이 문항을 제외하거나 별도 표기하는 것을 권장한다.
