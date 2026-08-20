# 공통 지식 RAG 시드 데이터 (research.md 인용 논문 5편)

- 관련 마이그레이션: `alembic/versions/20260821_0014_knowledge_seed_research_claims.py`, `alembic/versions/20260821_0015_fix_knowledge_chunks_timestamp_default.py`, `alembic/versions/20260821_0016_knowledge_seed_humidity_claim.py`, `alembic/versions/20260821_0018_revert_sleep_humidity_to_draft.py`
- 관련 문서: `../docs/research.md`(2절 안드로겐 경로 근거), `../docs/archieve/공통지식_RAG_근거와_응답규칙_v1.md`(Claim Card 표준, 4.1/4.2/4.7/4.8절)
- 관련 확인 작업: `system_architecture.md` 5.4/5.5절(Common Knowledge Layer, Retrieval Orchestrator) 실제 데이터 유무 점검

> ⚠️ **2026-08-21 정정**: sleep·humidity 2건은 애초 스펙 3.1절이 요구하는 의료 자문·법무 검토 없이 `approved`로 등록됐다(다른 4건은 draft로 남겨 규칙을 지켰으나 이 두 건에는 실수로 적용하지 않음). `alembic/versions/20260821_0018_revert_sleep_humidity_to_draft.py`에서 두 건 모두 `review_status`를 `draft`로 되돌려 검색·인용 대상에서 제외했다. **현재 시드된 6건 전부 의료 자문·법무 검토를 받은 적이 없고 전부 `draft` 상태다.** 아래 문서는 시드 당시의 원래 의도(및 매칭 로직이 정상 동작함을 확인했던 검증 기록)를 남기되, 실제 콘텐츠는 아직 하나도 승인되지 않았다는 점을 기준으로 읽어야 한다. `find_claim`은 sleep/humidity를 포함한 모든 topic에 대해 `None`을 반환한다.

## 배경

`system_architecture.md` 검증 과정에서 공통 지식 RAG(`knowledge_documents`/`knowledge_chunks`/`knowledge_indexes`)의 코드(모델, 청커, 키워드 검색, Claim 매칭, 관리자 CRUD API, Report/Briefing 연동)는 모두 구현돼 있지만 **시드 데이터가 전혀 없어** 활성 인덱스가 존재하지 않고, `find_claim`/`keyword_search`가 항상 빈 결과를 반환하는 상태였다. 이 마이그레이션은 `docs/research.md`에 실제로 링크된 논문 5편을 근거로 최소 시드 데이터를 채워 이 문제를 해결한다.

## 범위 결정 (시드 당시 원래 의도 — 현재는 정정됨, 아래 "현재 상태" 참고)

`research.md` Sources 중 학술 논문 링크는 5개다(시장 리포트·SDK 문서 등은 제외). 이 중 실제로 Report/Briefing 코드가 자동 조회하는 topic은 `sleep`·`humidity`뿐이며, `공통지식_RAG_근거와_응답규칙_v1.md` 4.7절(HRV·스트레스)과 4.8절(음식·야식)은 인과 주장 Claim Card 자체를 만들지 말라고 명시한다. 이에 따라:

- **`sleep` 주제 1건만 `approved` Claim Card로 등록**하고 활성 인덱스에 연결해 실제로 검색되도록 한다.
- **나머지 4건(생리주기 2편, 스트레스, 식단/안드로겐 병인)은 `draft` 상태로만 등록**한다. 검색·인용 대상이 아니며, 향후 의료 자문·법무 검토(스펙 3.1절) 후 정식 Claim Card로 승격할 수 있는 참고 문헌으로만 둔다.

## 현재 상태 (2026-08-21 정정 이후)

**시드된 6건 전부 아직 의료 자문·법무 검토를 받은 적이 없고, 전부 `draft` 상태다.** sleep/humidity 2건은 위 "범위 결정"에 따라 원래 `approved`로 등록됐지만, 검토 없이 승인 처리한 실수였음을 뒤늦게 발견해 `draft`로 되돌렸다(자세한 경위는 문서 상단 정정 안내와 "알려진 이슈와 후속 작업" 참고). 즉 이 작업은 **실제 콘텐츠를 노출한 게 아니라, 매칭 로직·시드 파이프라인이 정상 동작한다는 것만 검증해둔 상태**다. 실제 서비스 노출은 검토가 끝나 review_status를 `approved`로 전환하는 별도 마이그레이션이 있어야만 가능하다.

## 시드된 문서 목록

| 문서 | 출처 | review_status (현재) | topic | 비고 |
|---|---|---|---|---|
| Sleep and Skin Barrier — NCBI PMC 2022 | [PMC8775463](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8775463/) | `draft` (0018에서 되돌림, 원래 등록 시 `approved`) | `sleep` | Claim Card `claim_sleep_barrier_001` — 검토받은 적 없음, 검토 완료 후에만 approved 전환 가능 |
| Trigger Factors in Adult Female Acne — PubMed 2020 | [PubMed 32832440](https://pubmed.ncbi.nlm.nih.gov/32832440/) | `draft` | — | 자기 보고 기반 트리거 순위, 인과 주장 아님 |
| Quantitative Premenstrual Acne Flare — JAMA Dermatology | [JAMA](https://jamanetwork.com/journals/jamadermatology/fullarticle/480456) | `draft` | — | 개인 생리주기 fact 산출 로직 부재로 보류 |
| Stress-Induced Acne Mechanisms — Research Square 2024 | [rs-4477781](https://www.researchsquare.com/article/rs-4477781/v1) | `draft` | — | 4.7절: HRV·스트레스는 evidence level D, Claim Card 미생성 |
| Etiology of Adult Female Acne Systematic Review 2025 — PMC | [PMC12042216](https://pmc.ncbi.nlm.nih.gov/articles/PMC12042216/) | `draft` | — | 4.8절: 식단 인과 주장 금지, Claim Card 미생성 |
| Ambient Humidity and the Skin — PubMed 2016 | [PubMed 27306376](https://pubmed.ncbi.nlm.nih.gov/27306376/) | `draft` (0018에서 되돌림, 원래 등록 시 `approved`) | `humidity` | Claim Card `claim_humidity_dryness_001` — 검토받은 적 없음, 검토 완료 후에만 approved 전환 가능 |

## Sleep Claim Card 상세

```text
claim_id: claim_sleep_barrier_001
version: 1
topic: sleep
population: 성인
evidence_level: C (human_observational)
allowed_features: [briefing, report]
required_user_facts: [sleep_hours_available, sleep_below_personal_baseline_or_threshold]
allowed_expressions: "최근 수면이 짧아 오늘은 피부 자극을 줄여보세요. 수면의 질이 낮으면
                      피부 장벽 회복이 더뎌질 수 있어요."
forbidden_expressions: "수면 부족 때문에 트러블이 생겼어요. / 수면 부족으로 피부 장벽이
                        손상됐어요."
```

활성 인덱스: ~~`knowledge-index-2026-08-21-v1`~~ → `knowledge-index-2026-08-21-v2` (`claim_ids=["claim_sleep_barrier_001", "claim_humidity_dryness_001"]`). ADR 002(기존 인덱스의 claim 목록을 변경하지 않고 새 버전을 만들어 활성화)에 따라 v1은 0016 마이그레이션에서 비활성화하고 v2를 신규 생성·활성화했다.

## Humidity Claim Card 상세

```text
claim_id: claim_humidity_dryness_001
version: 1
topic: humidity
population: 성인
evidence_level: C (human_observational)
allowed_features: [briefing, report]
required_user_facts: [weather_consent, fresh_humidity_data, humidity_below_rule_threshold]
```

스펙 4.2절 근거 논문(PubMed 27306376, "Ambient humidity and the skin")을 바탕으로 등록. `weather_consent`가 없거나 습도 데이터가 최신이 아니면 매칭되지 않는다.

## 검증 결과 (시드 당시, 되돌리기 전 기록)

로컬 Postgres(`docker compose up -d db` → `alembic upgrade head`)에서 직접 확인함. **아래는 0016까지 적용했을 때(당시 approved 상태)의 결과이며, 이후 0018에서 두 claim 모두 `draft`로 되돌렸다 — 지금은 `find_claim(topic="sleep"/"humidity")` 모두 `None`을 반환한다. 이 기록은 "매칭 로직 자체가 정상 동작한다"는 걸 확인했다는 뜻일 뿐, 콘텐츠가 검토·승인됐다는 뜻이 아니다.**

```python
await find_claim(
    db,
    feature="briefing",
    topic="sleep",
    facts={"sleep_hours_available", "sleep_below_personal_baseline_or_threshold"},
)
# => ClaimMatch(claim_id='claim_sleep_barrier_001', version=1, sentence='...')

await keyword_search(db, ["수면", "TEWL"], limit=5)
# => sleep 문서 청크 1건 반환

await keyword_search(db, ["IGF", "안드로겐", "생리"], limit=10)
# => [] (draft 문서는 검색되지 않음 — 의도한 동작)

await find_claim(
    db,
    feature="briefing",
    topic="humidity",
    facts={"weather_consent", "fresh_humidity_data", "humidity_below_rule_threshold"},
)
# => ClaimMatch(claim_id='claim_humidity_dryness_001', version=1, sentence='...')

await keyword_search(db, ["습도", "TEWL"], limit=5)
# => sleep, humidity 문서 청크 모두 반환
```

- `alembic upgrade head` / `alembic downgrade -1` 왕복 확인
- `uv run pytest` 전체 230개 통과 (humidity 후속 시드 반영 후)
- `uv run ruff format --check .` / `uv run ruff check .` 통과

## 알려진 이슈와 후속 작업

- ~~`knowledge_chunks` 테이블의 `created_at`/`updated_at` `server_default`가 Postgres 전용 `now()`로 정의돼 있어(`20260816_0002_knowledge_tables.py`), SQLite 마이그레이션 테스트에서 그대로 insert하면 실패한다.~~ **해결됨**: `alembic/versions/20260821_0015_fix_knowledge_chunks_timestamp_default.py`에서 `server_default`를 Postgres/SQLite 모두 호환되는 `CURRENT_TIMESTAMP`로 통일했다(기존 병합된 마이그레이션은 수정하지 않고 새 마이그레이션으로 처리).
- `draft` 상태인 6건(sleep·humidity 포함) 전부 의료 자문·법무 검토(스펙 3.1절) 없이는 `approved`로 전환하면 안 된다. (코드 변경으로 해결할 수 없는 항목이라 그대로 남겨둠)
- ~~`humidity` 주제 Claim Card는 아직 시드되지 않았다~~ **해결됨**: `alembic/versions/20260821_0016_knowledge_seed_humidity_claim.py`에서 `공통지식_RAG_근거와_응답규칙_v1.md` 4.2절 근거(PubMed 27306376)로 `claim_humidity_dryness_001`을 시드하고, 활성 인덱스를 `knowledge-index-2026-08-21-v2`(sleep+humidity)로 교체했다.
- **신규(2026-08-21)**: 0014·0016 마이그레이션에서 sleep/humidity 2건이 의료 자문·법무 검토 없이 `approved`로 등록됐던 것을 발견 — 3.1절 규칙을 다른 4건에는 지켰으나 이 두 건에는 실수로 적용하지 않았다. `alembic/versions/20260821_0018_revert_sleep_humidity_to_draft.py`로 두 건 모두 `draft`로 되돌렸다. **현재 시드된 6건 전부 의료 자문·법무 검토를 받은 적이 없다.** 실제 검토가 끝나면 review_status를 `approved`로 되돌리는 후속 마이그레이션을 새로 작성해야 한다(0018을 재사용하지 않는다).
