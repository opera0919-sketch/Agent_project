#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISA 문제은행 JSONL 기계 검증기 (Validator).

QA Audit Prompt의 10대 검증영역 중 '기계적으로 검증 가능한' 항목을 자동화한다.
 - 구조 검증: 필수 필드 존재/타입, JSON 유효성
 - 스키마 검증: 난이도/근거우선순위 허용값
 - ID 검증: 유니크, 형식(ISA-Bxx-nnn)
 - 난이도 분포: 목표 비율(기본20/중급20/고급30/최고난도30)과 비교
 - 커버리지: 대분류 분포 집계
 - 중복 검증: 질문 텍스트 정규화 후 유사/중복 탐지(간이)
 - 계산 검증(보조): '계산' 문항에 calculation 필드 존재 여부
 - 관련 문제 ID 무결성: related_ids가 실제 존재하는 id인지
 - verification_needed 문항 목록화(사람 확인 유도)

내용(법령 조문의 정확성, 계산 수치의 정오)까지는 사람이 audit_report에서 검증한다.

사용법:
    python3 validate.py ../isa_qa_batch01.jsonl
종료코드 0=통과(에러 없음), 1=에러 존재.
"""
import json
import re
import sys
from collections import Counter

REQUIRED_FIELDS = [
    "id", "category", "subcategory", "difficulty", "question", "answer",
    "explanation", "calculation", "basis_law", "basis_article", "related_law",
    "basis_priority", "practical_notes", "exceptions", "common_misconceptions",
    "related_ids", "keywords", "verification_needed", "verification_note",
]
LIST_FIELDS = ["related_law", "related_ids", "keywords"]
DIFFICULTIES = ["기본", "중급", "고급", "최고난도"]
DIFFICULTY_TARGET = {"기본": 0.20, "중급": 0.20, "고급": 0.30, "최고난도": 0.30}
ID_RE = re.compile(r"^ISA-B\d{2}-\d{3}$")


def normalize(text):
    """질문 정규화: 공백/기호 제거, 소문자화 → 간이 중복 비교용."""
    return re.sub(r"[\s\W_]+", "", (text or "")).lower()


def load(path):
    items, errors = [], []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                errors.append(f"[JSON] {ln}행 파싱 실패: {e}")
    return items, errors


def validate(path):
    items, errors = load(path)
    warnings = []

    ids = []
    for i, it in enumerate(items, 1):
        tag = it.get("id", f"(line {i})")
        # 필수 필드
        for fld in REQUIRED_FIELDS:
            if fld not in it:
                errors.append(f"[필드] {tag}: 필수 필드 '{fld}' 누락")
        # 리스트 타입
        for fld in LIST_FIELDS:
            if fld in it and not isinstance(it[fld], list):
                errors.append(f"[타입] {tag}: '{fld}'는 배열이어야 함")
        # 난이도
        if it.get("difficulty") not in DIFFICULTIES:
            errors.append(f"[난이도] {tag}: 허용되지 않은 값 '{it.get('difficulty')}'")
        # 근거 우선순위
        bp = it.get("basis_priority")
        if not isinstance(bp, int) or not (1 <= bp <= 10):
            errors.append(f"[우선순위] {tag}: basis_priority는 1~10 정수여야 함 (현재 {bp})")
        # id 형식
        if not ID_RE.match(str(it.get("id", ""))):
            errors.append(f"[ID형식] {tag}: 'ISA-Bxx-nnn' 형식 아님")
        ids.append(it.get("id"))
        # 계산 문항 보조 검증
        is_calc = (it.get("category") == "계산형") or ("[계산]" in (it.get("question") or ""))
        if is_calc and not it.get("calculation"):
            errors.append(f"[계산] {tag}: 계산형인데 calculation 필드가 비어 있음")
        # verification 일관성
        if it.get("verification_needed") and not (it.get("verification_note") or "").strip():
            warnings.append(f"[검증플래그] {tag}: verification_needed=true인데 note 없음")
        # 빈 필수 텍스트
        for fld in ["question", "answer", "explanation", "basis_law", "basis_article"]:
            if not (str(it.get(fld, "")).strip()):
                errors.append(f"[빈값] {tag}: '{fld}'가 비어 있음")

    # ID 유니크
    dup_ids = [k for k, v in Counter(ids).items() if v > 1]
    for d in dup_ids:
        errors.append(f"[ID중복] '{d}' 가 2회 이상 등장")

    # related_ids 무결성
    idset = set(ids)
    for it in items:
        for rid in it.get("related_ids", []):
            if rid not in idset:
                warnings.append(f"[관련ID] {it.get('id')}: 존재하지 않는 related_id '{rid}'")

    # 중복 질문(간이)
    seen = {}
    for it in items:
        key = normalize(it.get("question"))
        if key in seen:
            warnings.append(f"[중복질문] {it.get('id')} ↔ {seen[key]}: 질문 텍스트 유사/동일 의심")
        else:
            seen[key] = it.get("id")

    # 난이도 분포
    n = len(items)
    dcount = Counter(it.get("difficulty") for it in items)
    ccount = Counter(it.get("category") for it in items)
    vflag = [it.get("id") for it in items if it.get("verification_needed")]

    # 리포트 출력
    print("=" * 60)
    print(f"ISA 문제은행 기계 검증 리포트: {path}")
    print("=" * 60)
    print(f"총 문항 수: {n}")
    print("\n[난이도 분포] (목표: 기본20/중급20/고급30/최고난도30)")
    for d in DIFFICULTIES:
        c = dcount.get(d, 0)
        pct = (c / n * 100) if n else 0
        target = DIFFICULTY_TARGET[d] * 100
        mark = "✓" if abs(pct - target) < 1e-9 else "≈" if abs(pct - target) <= 4 else "✗"
        print(f"  {d:<6} {c:>3}개  {pct:5.1f}%  (목표 {target:.0f}%) {mark}")
    print("\n[대분류 커버리지]")
    for cat, c in ccount.most_common():
        print(f"  {cat:<10} {c:>3}개  ({c/n*100:4.1f}%)")
    print(f"\n[verification_needed 문항] {len(vflag)}개")
    if vflag:
        print("  " + ", ".join(vflag))

    print(f"\n[에러] {len(errors)}건")
    for e in errors:
        print("  ✗ " + e)
    print(f"\n[경고] {len(warnings)}건")
    for w in warnings:
        print("  ! " + w)

    print("\n" + "=" * 60)
    ok = len(errors) == 0
    print("결과: " + ("PASS (에러 없음)" if ok else f"FAIL ({len(errors)}건 에러)"))
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "../isa_qa_batch01.jsonl"
    sys.exit(validate(target))
