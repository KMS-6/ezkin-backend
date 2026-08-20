---
authored_with: Codex
features_used:
  - github:gh-address-comments
date: 2026-08-21
---

# ADR 002: Knowledge Index에 Claim 버전 고정

## 상태

승인됨

## 맥락

활성 인덱스가 `claim_id`만 저장하면 같은 ID의 새 버전이 승인되는 즉시 기존 인덱스의
검색 결과가 바뀐다. 이 동작은 인덱스 재현성과 `claim_id + version` 인용 검증을 깨뜨린다.

## 결정

인덱스 생성 시 승인된 최신 버전을 `claim_versions` JSON 객체에
`claim_id → claim_version`으로 저장한다. Briefing 근거 매칭은 활성 인덱스에 고정된
버전만 허용한다. 기존 `claim_ids` 요청·응답 계약은 유지한다.

## 대안

- 문서 UUID 저장: 가장 명확하지만 인덱스 API 계약과 관리 화면 변경 범위가 커진다.
- 인덱스 생성 시각 이전 문서 선택: 문서 생성·수집 시각의 의미에 의존해 재현성이 약하다.

## 결과

새 Claim 버전을 노출하려면 새 인덱스를 생성하고 활성화해야 한다. 마이그레이션 전 생성된
인덱스는 버전 정보가 없어 Briefing 근거를 반환하지 않으며, 안전한 재생성이 필요하다.
