"""ISA 문제은행 RAG 콘텐츠 포맷 빌더.

하나의 원본 레코드(19키)로부터 세 가지 콘텐츠 포맷을 생성한다.
  1) build_embedding_text(rec)  → 임베딩 콘텐츠(벡터화 대상 텍스트)
  2) build_storage_doc(rec, vec)→ 저장 콘텐츠(벡터DB payload)
  3) build_llm_context(rec)     → LLM 반환 콘텐츠(프롬프트 주입용 근거 블록)

사용 예:
    import json
    from rag_formats import build_embedding_text, build_storage_doc, build_llm_context
    recs = [json.loads(l) for l in open("isa_qa_all_500.jsonl", encoding="utf-8") if l.strip()]
"""
from __future__ import annotations
from typing import Any


# ── 1) 임베딩 콘텐츠 포맷 ─────────────────────────────────────────────
# 목적: 사용자 질의와의 의미 매칭. 검색에 기여하는 자연어 필드만 담고,
#       관리·메타(id, basis_priority, related_ids, verification_*)는 제외한다.
def build_embedding_text(rec: dict[str, Any]) -> str:
    kw = " ".join(rec.get("keywords") or [])
    parts = [
        f"[분류] {rec['category']} > {rec['subcategory']} | 난이도 {rec['difficulty']}",
        f"[질문] {rec['question']}",
        f"[정답] {rec['answer']}",
        f"[해설] {rec['explanation']}",
    ]
    if rec.get("calculation"):
        parts.append(f"[계산] {rec['calculation']}")
    if kw:
        parts.append(f"[키워드] {kw}")
    return "\n".join(parts)


# 선택: 질의-질문 정밀 매칭용 보조 벡터(dual embedding) 소스.
def build_embedding_text_question_only(rec: dict[str, Any]) -> str:
    kw = " ".join(rec.get("keywords") or [])
    return f"{rec['question']}\n[키워드] {kw}" if kw else rec["question"]


# ── 2) 저장 콘텐츠 포맷 ───────────────────────────────────────────────
# 목적: 벡터DB에 벡터와 함께 저장. 원본 19키를 payload로 보존하고,
#       필터 키와 재현용 임베딩 소스를 별도 노출한다.
FILTER_KEYS = ("category", "subcategory", "difficulty", "basis_law",
               "basis_priority", "verification_needed")


def build_storage_doc(rec: dict[str, Any], vector: list[float] | None = None) -> dict[str, Any]:
    batch = rec["id"].split("-")[1]  # ISA-B01-001 → B01
    return {
        "id": rec["id"],
        "vector": vector,                          # 임베딩 결과(길이 = 모델 차원)
        "embedding_text": build_embedding_text(rec),  # 재임베딩·디버그용 원문
        "payload": dict(rec),                      # 원본 19키 전체 보존(표시·인용)
        "filters": {k: rec.get(k) for k in FILTER_KEYS},  # 사전 필터링용
        "source_batch": batch,
    }


# ── 3) LLM 반환 콘텐츠 포맷 ───────────────────────────────────────────
# 목적: 검색된 문항을 LLM 프롬프트에 주입. raw JSON이 아니라 인용 가능한
#       라벨 블록으로 렌더링하고, 미확정(verification_needed) 문항은 경고를 병기한다.
def build_llm_context(rec: dict[str, Any]) -> str:
    lines = [
        f"[문서 {rec['id']}] ({rec['category']} > {rec['subcategory']}, 난이도 {rec['difficulty']})",
        f"질문: {rec['question']}",
        f"정답: {rec['answer']}",
        f"해설: {rec['explanation']}",
    ]
    if rec.get("calculation"):
        lines.append(f"계산: {rec['calculation']}")
    lines.append(f"근거: {rec['basis_law']} {rec['basis_article']}")
    if rec.get("exceptions"):
        lines.append(f"예외: {rec['exceptions']}")
    if rec.get("practical_notes"):
        lines.append(f"실무 주의: {rec['practical_notes']}")
    if rec.get("verification_needed"):
        note = rec.get("verification_note") or "원문 대조 필요"
        lines.append(f"⚠️ 미확정(사람 확인 필요): {note}")
    return "\n".join(lines)


def build_llm_context_block(recs: list[dict[str, Any]]) -> str:
    """검색 결과 여러 건을 하나의 근거 블록으로 결합."""
    header = ("아래는 검색된 ISA 근거 문항이다. 이 안에서만 답하고, 각 사실 뒤에 "
              "[문서 ID]로 출처를 표기하라. ⚠️ 표시 문항은 단정하지 말고 '확인 필요'로 안내하라.\n")
    return header + "\n\n".join(build_llm_context(r) for r in recs)


if __name__ == "__main__":
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "isa_qa_all_500.jsonl"
    rec = json.loads(open(path, encoding="utf-8").readline())
    print("=" * 70, "\n[1] 임베딩 콘텐츠\n", "=" * 70)
    print(build_embedding_text(rec))
    print("\n", "=" * 70, "\n[2] 저장 콘텐츠(payload 키만)\n", "=" * 70)
    doc = build_storage_doc(rec, vector=None)
    print("top-level:", list(doc.keys()))
    print("filters:", json.dumps(doc["filters"], ensure_ascii=False))
    print("payload 19키:", list(doc["payload"].keys()))
    print("\n", "=" * 70, "\n[3] LLM 반환 콘텐츠\n", "=" * 70)
    print(build_llm_context(rec))
