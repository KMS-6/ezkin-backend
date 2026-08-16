"""SOS 챗봇 FAQ mock 데이터 — 기능명세서_chatbot.md 8.1절 FAQ_ITEMS/FAQ_UTTERANCES를 단순화한 것.

전부 AI가 작성한 가상 질문·답변이며 실제 고객 상담 기록이 아니다. `keywords`는
FAQ_UTTERANCES(유사 질문 표현)를 대신하는 트리거 문구 목록이다 — 사용자 발화에 이
문구 중 하나라도 포함되면 해당 FAQ의 후보로 본다(app.modules.triggers.logic의
점수 계산에서 사용).

`intent`는 app.modules.triggers.nlu.INTENTS 중 하나로, 8.2절 2단계("파싱한 intent와
category로 FAQ 후보를 좁힌다")에서 후보를 줄이는 데 쓴다. product_alternative·
sunscreen·skin_trouble·product_combination처럼 전용 규칙엔진 분기가 이미 처리하는
intent는 여기 태그를 붙이지 않는다 — 그 분기가 항상 먼저 가로채 도달하지 않기 때문이다.
"""

FAQ_ENTRIES = [
    {
        "faq_id": "faq_after_irritating_food",
        "version": 1,
        "label": "야식·자극적인 음식 이후 관리",
        "intent": "food_aftercare",
        "keywords": ["야식", "매운", "자극적인 음식", "튀김"],
        "reply": "오늘 등록된 진정·보습 제품 위주로 순하게 관리해 보세요.",
    },
    {
        "faq_id": "faq_new_product_irritation",
        "version": 1,
        "label": "새 제품 사용 후 자극",
        "intent": "skin_condition",
        "keywords": ["따가", "화끈", "새 제품", "새제품"],
        "reply": "새로 사용한 제품이 있다면 사용을 중단하고 순한 세안 후 보습에 집중해 주세요.",
    },
    {
        "faq_id": "faq_dryness",
        "version": 1,
        "label": "건조·당김 관리",
        "intent": "skin_condition",
        "keywords": ["건조", "당김", "푸석"],
        "reply": "보습 제품을 층층이 덧발라 수분 손실을 줄여보세요.",
    },
    {
        "faq_id": "faq_routine_order",
        "version": 1,
        "label": "스킨케어 사용 순서",
        "intent": "routine_order",
        "keywords": ["다음에 뭐", "사용 순서", "바르는 순서", "순서가 어떻게"],
        "reply": "일반적으로 클렌징 → 토너 → 세럼/앰플 → 크림 → 자외선차단제 순서로 사용해요.",
    },
    {
        "faq_id": "faq_sunscreen_reapply",
        "version": 1,
        "label": "자외선차단제 덧바르기",
        "intent": "sunscreen",
        "keywords": ["선크림", "자외선차단", "덧발라"],
        "reply": "자외선 차단제는 2~3시간 간격으로 덧발라 주세요.",
    },
    {
        "faq_id": "faq_double_cleansing",
        "version": 1,
        "label": "이중 세안 방법",
        "intent": "product_usage",
        "keywords": ["이중세안", "이중 세안", "클렌징오일", "클렌징 오일"],
        "reply": "자외선차단제나 메이크업을 사용한 날은 오일·밤 클렌저로 1차 세안 후 폼 클렌저로 "
        "2차 세안하면 잔여물을 줄이는 데 도움이 돼요.",
    },
    {
        "faq_id": "faq_over_cleansing",
        "version": 1,
        "label": "과도한 세안·피부 장벽",
        "intent": "product_usage",
        "keywords": ["세안을 자주", "너무 자주 씻", "세안 횟수"],
        "reply": "하루 2회(아침·저녁) 세안이 일반적인 기준이에요. 너무 잦은 세안은 피부 장벽이 "
        "약해지는 느낌으로 이어질 수 있어 주의가 필요해요.",
    },
    {
        "faq_id": "faq_exfoliation_frequency",
        "version": 1,
        "label": "각질 제거 주기",
        "intent": "product_usage",
        "keywords": ["각질제거", "각질 제거", "필링", "스크럽"],
        "reply": "각질 제거는 주 1~2회 정도가 일반적으로 권장돼요. 피부가 예민한 날에는 건너뛰는 "
        "것이 좋아요.",
    },
    {
        "faq_id": "faq_pore_care",
        "version": 1,
        "label": "모공 관리",
        "intent": "skin_condition",
        "keywords": ["모공", "블랙헤드"],
        "reply": "모공은 완전히 없애기보다 피지·각질 관리로 눈에 덜 띄게 관리하는 방향이 "
        "일반적이에요. 꾸준한 세안과 저자극 각질 관리를 참고해 보세요.",
    },
    {
        "faq_id": "faq_oily_skin_care",
        "version": 1,
        "label": "지성·유분 관리",
        "intent": "skin_condition",
        "keywords": ["유분", "번들거림", "기름기"],
        "reply": "산뜻한 제형의 보습제로 유수분 밸런스를 맞추고, 세정력이 과한 클렌저는 피해 "
        "보세요.",
    },
    {
        "faq_id": "faq_sensitive_skin_routine",
        "version": 1,
        "label": "민감성 피부 루틴",
        "intent": "skin_condition",
        "keywords": ["민감성 피부", "예민한 피부", "피부가 예민"],
        "reply": "향료·알코올 함량이 낮은 저자극 제품 위주로 단순한 루틴을 유지하는 것이 "
        "일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_acne_spot_care",
        "version": 1,
        "label": "트러블·뾰루지 스팟 케어",
        "intent": "skin_condition",
        "keywords": ["뾰루지", "여드름", "트러블 케어"],
        "reply": "해당 부위는 손으로 만지거나 짜지 않고, 자극이 적은 진정 제품으로 관리하는 "
        "것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_niacinamide_usage",
        "version": 1,
        "label": "나이아신아마이드 사용법",
        "intent": "product_usage",
        "keywords": ["나이아신아마이드"],
        "reply": "나이아신아마이드는 일반적으로 아침·저녁 모두 사용 가능한 성분으로 알려져 "
        "있어요. 처음 사용한다면 소량으로 며칠 지켜본 뒤 사용량을 늘려 보세요.",
    },
    {
        "faq_id": "faq_salicylic_acid_usage",
        "version": 1,
        "label": "살리실산·BHA 사용법",
        "intent": "product_usage",
        "keywords": ["살리실산", "bha"],
        "reply": "살리실산(BHA)은 자극이 있을 수 있어 처음에는 주 2~3회로 시작해 피부 반응을 "
        "지켜보는 것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_aha_bha_caution",
        "version": 1,
        "label": "AHA·BHA 함께 사용 시 주의",
        "intent": "product_usage",
        "keywords": ["aha", "산성분", "각질산"],
        "reply": "AHA·BHA 계열 성분은 같은 날 여러 제품을 중복 사용하면 자극 가능성이 높아질 수 "
        "있어 하나만 사용하는 것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_hyaluronic_acid_usage",
        "version": 1,
        "label": "히알루론산 사용법",
        "intent": "product_usage",
        "keywords": ["히알루론산", "히알루론"],
        "reply": "히알루론산은 수분감이 있는 토너·세럼 뒤에 사용하면 보습 효과를 더 느끼기 쉬운 "
        "것으로 알려져 있어요.",
    },
    {
        "faq_id": "faq_centella_soothing",
        "version": 1,
        "label": "센텔라·병풀 진정 성분",
        "intent": "product_usage",
        "keywords": ["센텔라", "병풀"],
        "reply": "센텔라(병풀) 성분은 자극받은 피부를 진정시키는 목적으로 흔히 사용돼요. 트러블 "
        "부위 위주로 얇게 발라 보세요.",
    },
    {
        "faq_id": "faq_peptide_usage",
        "version": 1,
        "label": "펩타이드 사용법",
        "intent": "product_usage",
        "keywords": ["펩타이드"],
        "reply": "펩타이드는 일반적으로 세럼·앰플 단계에서 사용하며, 특별한 주의 성분과의 "
        "상호작용 규칙이 확인되지 않는 한 다른 성분과 함께 사용해도 괜찮은 것으로 "
        "알려져 있어요.",
    },
    {
        "faq_id": "faq_patch_test",
        "version": 1,
        "label": "패치 테스트 방법",
        "intent": "product_usage",
        "keywords": ["패치테스트", "패치 테스트"],
        "reply": "새 제품은 팔 안쪽 등에 소량 발라 24~48시간 정도 반응을 지켜본 뒤 얼굴에 사용하는 "
        "것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_expiration_check",
        "version": 1,
        "label": "화장품 유통·사용 기한",
        "intent": "product_usage",
        "keywords": ["유통기한", "사용기한", "언제까지 써"],
        "reply": "제품 용기의 개봉 후 사용 기한(PAO) 표시를 확인해 주세요. 표시가 없다면 개봉 후 "
        "6개월~1년 이내 사용을 참고해 보세요.",
    },
    {
        "faq_id": "faq_opened_product_storage",
        "version": 1,
        "label": "개봉 후 보관법",
        "intent": "product_usage",
        "keywords": ["보관법", "어떻게 보관"],
        "reply": "직사광선과 고온다습을 피해 서늘한 곳에 밀폐해 보관하는 것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_cotton_pad_reuse",
        "version": 1,
        "label": "화장솜 재사용",
        "intent": "product_usage",
        "keywords": ["화장솜 재사용", "화장솜 다시"],
        "reply": "위생을 위해 화장솜은 1회 사용 후 새 것으로 교체하는 것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_sheet_mask_frequency",
        "version": 1,
        "label": "시트마스크 사용 빈도",
        "intent": "product_usage",
        "keywords": ["시트마스크", "마스크팩"],
        "reply": "시트마스크는 주 2~3회 정도가 일반적인 기준이에요. 매일 사용하면 오히려 자극이 "
        "될 수 있어요.",
    },
    {
        "faq_id": "faq_seasonal_care_winter",
        "version": 1,
        "label": "겨울철 피부 관리",
        "intent": "skin_condition",
        "keywords": ["겨울철 피부", "겨울에 피부"],
        "reply": "건조한 계절에는 보습 제품의 사용량을 늘리고 밀폐력이 있는 크림을 층에 마지막에 "
        "덧발라 주는 것이 일반적으로 권장돼요.",
    },
    {
        "faq_id": "faq_seasonal_care_summer",
        "version": 1,
        "label": "여름철 피부 관리",
        "intent": "skin_condition",
        "keywords": ["여름철 피부", "여름에 피부", "장마철"],
        "reply": "높은 습도·자외선이 함께 관찰되는 계절이에요. 산뜻한 제형과 자외선 차단제 "
        "재도포를 함께 챙겨 보세요.",
    },
    {
        "faq_id": "faq_pregnancy_caution_ingredients",
        "version": 1,
        "label": "임신·수유 중 주의 성분",
        "intent": "product_usage",
        "keywords": ["임신 중", "수유 중", "임산부"],
        "reply": "임신·수유 중에는 레티놀 등 일부 성분에 주의가 필요하다고 알려져 있어요. 정확한 "
        "사용 가능 여부는 담당 의료진과 상담하는 것을 권장해요.",
    },
    {
        "faq_id": "faq_risk_level_explanation",
        "version": 1,
        "label": "오늘의 위험도 등급 설명",
        "intent": "service_explanation",
        "keywords": ["위험도가 뭐", "위험도 높음", "위험도란"],
        "reply": "오늘의 위험도는 수면·식습관·최근 스캔 등 생활·환경 데이터를 종합한 참고 "
        "지표예요. 의료적 진단이 아닌 상대적 변화 안내로 이해해 주세요.",
    },
    {
        "faq_id": "faq_my_shelf_registration",
        "version": 1,
        "label": "My Shelf 제품 등록 방법",
        "intent": "service_explanation",
        "keywords": ["마이쉘프", "my shelf", "제품 등록"],
        "reply": "보유하신 화장품을 My Shelf에 등록하면 성분과 오늘 피부 상태를 함께 확인해 더 "
        "구체적으로 안내할 수 있어요.",
    },
]
