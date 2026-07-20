# ISA 문제은행 RAG 콘텐츠 포맷 지정

`isa_qa_all_500.jsonl`(19키 스키마)을 RAG 파이프라인에 투입할 때의 **3단계
콘텐츠 포맷**을 지정한다. 구현·검증된 빌더는 `rag_formats.py` 참조.

```
원본 레코드(19키)
   ├─(1) 임베딩 콘텐츠 ──→ 임베딩 모델 ──→ 벡터
   ├─(2) 저장 콘텐츠   ──→ 벡터DB(벡터 + payload + 필터)
   └─(3) LLM 반환 콘텐츠 ─→ 검색 결과 렌더 ──→ LLM 프롬프트 주입
```

원칙: **임베딩 = 검색용 최소 의미 텍스트**, **저장 = 원본 전체 보존**,
**LLM 반환 = 인용 가능한 근거 블록**. 세 포맷은 역할이 다르므로 담는 필드가 다르다.

---

## 1) 임베딩 콘텐츠 포맷 (Embedding content)

**목적**: 사용자 질의와의 의미 유사도 매칭. 검색에 기여하는 자연어 필드만 담고,
관리·메타 필드(`id`, `basis_priority`, `related_ids`, `verification_needed`,
`verification_note`)는 **벡터에 넣지 않는다**(노이즈 감소).

**포함 필드**: `category`, `subcategory`, `difficulty`, `question`, `answer`,
`explanation`, `calculation`(있을 때), `keywords`.

**템플릿**
```
[분류] {category} > {subcategory} | 난이도 {difficulty}
[질문] {question}
[정답] {answer}
[해설] {explanation}
[계산] {calculation}          # calculation != null 일 때만
[키워드] {keywords 공백결합}
```

**선택(권장) — 이중 벡터(dual embedding)**: 질의는 대개 '질문' 형태이므로,
`question(+keywords)`만 담은 보조 벡터를 함께 인덱싱하면 질의-질문 정밀 매칭이
오른다. 본문 벡터(위 템플릿)는 recall, 질문 벡터는 precision을 담당한다.
(`build_embedding_text_question_only`)

**주의**
- `practical_notes`·`exceptions`·`common_misconceptions`는 recall을 넓히지만
  주제를 희석한다 → 기본 제외, 재현율이 부족하면 별도 필드 벡터로만 추가.
- 임베딩 텍스트는 저장 콘텐츠의 `embedding_text`로 함께 보관해 재임베딩·디버깅에 쓴다.

---

## 2) 저장 콘텐츠 포맷 (Storage content / 벡터DB payload)

**목적**: 벡터와 함께 저장하여 검색·필터·표시·인용에 사용. **원본 19키를
그대로 보존**하고, 사전 필터 키와 재현용 임베딩 소스를 별도로 노출한다.

**구조**
```json
{
  "id": "ISA-B01-001",
  "vector": [ ... ],                 // 임베딩 결과(길이 = 모델 차원). dual이면 vector_q 추가
  "embedding_text": "[분류] ... [키워드] ...",   // (1)의 산출물, 재임베딩·감사용
  "payload": { ...원본 19키 전체... },            // 표시·인용·후처리용 원본 보존
  "filters": {                        // 사전 필터링 인덱스(중복 저장)
    "category": "ISA 제도",
    "subcategory": "가입자격",
    "difficulty": "기본",
    "basis_law": "조세특례제한법",
    "basis_priority": 1,
    "verification_needed": false
  },
  "source_batch": "B01"
}
```

**필터 키 설계**
| 필터 | 용도 |
|---|---|
| `verification_needed` | **운영 답변에서 미확정 문항 제외**(=false만) 또는 별도 표기 |
| `category` / `subcategory` | 주제 스코프 제한(예: 세제만, 연금전환만) |
| `difficulty` | 평가셋 난이도 구성 |
| `basis_law` | 법령 계열 필터(조특법 vs 상증세법 등 세목 구분) |
| `basis_priority` | 법률(1~) vs 증권사 운영실무(10) 구분 |

**주의**
- `verification_needed=true`(268/500)는 payload에 유지하되 필터로 분리한다.
  운영 서비스는 `false`만 노출하거나 답변 시 '확인 필요'로 표기.
- `related_ids`는 벡터에는 안 넣지만 payload에 보존 → 검색 후 연관 문항 확장에 사용.

---

## 3) LLM 반환 콘텐츠 포맷 (LLM context / 프롬프트 주입)

**목적**: 검색된 문항을 LLM에 근거로 전달. **raw JSON이 아니라 인용 가능한 라벨
블록**으로 렌더링하고, 미확정 문항은 경고를 병기한다.

**포함 필드**: `id`(인용용), `category/subcategory/difficulty`, `question`,
`answer`, `explanation`, `calculation`(있을 때), `basis_law`+`basis_article`,
`exceptions`, `practical_notes`, 그리고 `verification_needed=true`면 경고.
**제외**: `keywords`, `related_ids`, `related_law`, `basis_priority`,
`embedding_text`(프롬프트 토큰 낭비).

**문항 블록 템플릿**
```
[문서 {id}] ({category} > {subcategory}, 난이도 {difficulty})
질문: {question}
정답: {answer}
해설: {explanation}
계산: {calculation}                 # 있을 때만
근거: {basis_law} {basis_article}
예외: {exceptions}
실무 주의: {practical_notes}
⚠️ 미확정(사람 확인 필요): {verification_note}   # verification_needed=true 일 때만
```

**결합 블록(시스템/컨텍스트 헤더)**
```
아래는 검색된 ISA 근거 문항이다. 이 안에서만 답하고, 각 사실 뒤에 [문서 ID]로
출처를 표기하라. ⚠️ 표시 문항은 단정하지 말고 '확인 필요'로 안내하라.

{문항 블록 1}

{문항 블록 2}
...
```

**주의**
- **조건부 정답 문항**(국내주식 손실 통산·종합과세 절세폭·압류/회생 추징 등)은
  `answer`에 조건별 결론이 병기돼 있으므로 그대로 전달 → LLM이 단일 정답으로
  뭉개지 않도록 헤더에서 지시.
- 계산형은 `calculation`을 반드시 포함해 LLM이 재검산·인용하게 한다.
- 토큰 예산이 빡빡하면 `question`을 생략(질의와 중복)하고 `answer`+`근거`+
  `⚠️`만 남기는 축약 모드를 쓴다.

---

## 요약: 필드 × 포맷 매트릭스

| 필드 | (1) 임베딩 | (2) 저장 payload | (3) LLM 반환 |
|---|:--:|:--:|:--:|
| id | ✕ | ✅ | ✅(인용) |
| category / subcategory | ✅ | ✅(+필터) | ✅ |
| difficulty | ✅ | ✅(+필터) | ✅ |
| question | ✅ | ✅ | ✅(축약 시 생략) |
| answer | ✅ | ✅ | ✅ |
| explanation | ✅ | ✅ | ✅ |
| calculation | ✅(있을 때) | ✅ | ✅(있을 때) |
| basis_law / basis_article | ✕ | ✅(law 필터) | ✅(근거) |
| related_law | ✕ | ✅ | ✕ |
| basis_priority | ✕ | ✅(필터) | ✕ |
| practical_notes | ✕ | ✅ | ✅ |
| exceptions | ✕ | ✅ | ✅ |
| common_misconceptions | ✕ | ✅ | ✕(오답 유도 방지) |
| related_ids | ✕ | ✅ | ✕ |
| keywords | ✅ | ✅ | ✕ |
| verification_needed | ✕ | ✅(필터) | ✅(경고 트리거) |
| verification_note | ✕ | ✅ | ✅(true일 때) |

> 구현: `rag_formats.py` — `build_embedding_text` / `build_storage_doc` /
> `build_llm_context`. 실행: `python3 rag_formats.py isa_qa_all_500.jsonl`
> (3종 포맷 샘플 출력).
