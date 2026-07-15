# ISA 문제은행 JSONL 스키마

각 문항은 JSONL 파일에서 **1줄 = 1 JSON 객체**로 표현된다. 모든 문자열은
UTF-8, JSON은 `ensure_ascii=false`로 직렬화한다(한글 원문 보존).

## 필드 정의

| 키 | 타입 | 필수 | 설명 | Master Prompt 대응 |
|---|---|:--:|---|---|
| `id` | string | ✔ | 문제 ID. 형식 `ISA-Bxx-nnn` (예: `ISA-B01-001`). Batch 번호 2자리 + 일련번호 3자리 | 문제 ID |
| `category` | string | ✔ | 대분류. `ISA 제도` / `투자상품` / `세제` / `연금전환` / `예외 사례` / `계산형` | 대분류 |
| `subcategory` | string | ✔ | 소분류 (예: `가입자격`, `비과세`, `연금전환 세액공제`) | 소분류 |
| `difficulty` | string | ✔ | 난이도. `기본` / `중급` / `고급` / `최고난도` | 난이도 |
| `question` | string | ✔ | 질문 본문. 계산형은 앞에 `[계산]` 표기 | 질문 |
| `answer` | string | ✔ | 정답 요약. 조건부 정답은 조건별 결론을 함께 서술 | 정답 |
| `explanation` | string | ✔ | 상세해설 | 상세해설 |
| `calculation` | string \| null | ✔(계산형) | 단계별 계산식 + 검산. 비계산형은 `null` | 계산과정 |
| `basis_law` | string | ✔ | 근거 법령명 (예: `조세특례제한법`) | 근거 법령 |
| `basis_article` | string | ✔ | 근거 조항 (예: `제91조의18 제1항`) | 근거 조항 |
| `related_law` | string[] | ✔ | 관련 법령 배열 | 관련 법령 |
| `basis_priority` | int(1~10) | ✔ | 근거 우선순위. 아래 우선순위 표 참조 | 근거 우선순위 |
| `practical_notes` | string | ✔ | 실무 주의사항 | 실무 주의사항 |
| `exceptions` | string | ✔ | 예외사항 | 예외사항 |
| `common_misconceptions` | string | ✔ | 자주 하는 오해 | 자주 하는 오해 |
| `related_ids` | string[] | ✔ | 관련 문제 ID 배열 | 관련 문제 ID |
| `keywords` | string[] | ✔ | 검색 키워드 배열 | 검색 키워드 |
| `verification_needed` | bool | ✔ | (추가) 조문 번호·세부 수치 등 인용 확신이 낮아 사람 확인이 필요한 문항 여부 | — |
| `verification_note` | string | ✔ | (추가) `verification_needed=true`일 때 확인이 필요한 사유. false면 빈 문자열 | — |

## 근거 우선순위 코드 (basis_priority)

Master Prompt의 근거 우선순위를 정수로 코드화한 값이다. 충돌 시 숫자가 작은
(상위) 근거를 따른다.

| 코드 | 근거 |
|:--:|---|
| 1 | 법률 (조세특례제한법, 소득세법, 국세기본법 등) |
| 2 | 시행령 |
| 3 | 시행규칙 |
| 4 | 금융위원회 |
| 5 | 국세청 |
| 6 | 금융감독원 |
| 7 | 한국예탁결제원 |
| 8 | 한국거래소 |
| 9 | 기타 공공기관 |
| 10 | 증권사 공식 운영기준 |

## verification_needed 설계 의도

Master Prompt는 "환각 금지·존재하는 조문만 인용"을 요구한다. 정확한 조문
번호·세부 수치는 환각 위험이 가장 큰 항목이므로, 확신이 낮은 경우 값을
꾸며내지 않고 `verification_needed=true`로 표시해 사람이 원문(국가법령정보센터
등)으로 확정하도록 남긴다. 이는 정직성을 우선한 설계다.

## 예시 (1개 문항)

```json
{"id": "ISA-B01-021", "category": "세제", "subcategory": "비과세", "difficulty": "기본", "question": "ISA의 비과세 한도는 얼마이며...", "answer": "...일반형 200만원, 서민형·농어민형 400만원...", "explanation": "...", "calculation": null, "basis_law": "조세특례제한법", "basis_article": "제91조의18 제1항", "related_law": ["소득세법(이자·배당소득)"], "basis_priority": 1, "practical_notes": "...", "exceptions": "...", "common_misconceptions": "...", "related_ids": ["ISA-B01-011", "ISA-B01-022"], "keywords": ["비과세 한도", "200만원", "400만원"], "verification_needed": false, "verification_note": ""}
```
