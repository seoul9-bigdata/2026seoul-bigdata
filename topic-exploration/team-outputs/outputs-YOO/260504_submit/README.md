# 260504 작업 — 노인 교통·이동 통합 대시보드 (5탭)

**담당**: 유호준
**작업일**: 2026-05-04 ~ 2026-05-06
**핵심 질문**: _"노인은 동네를 벗어날 때 무엇을 잃는가 — 환승·기후·거점·횡단보도·OD 5축으로 본 교통 약자성"_

---

## 5탭 구조 — 각 팀원 보완 매핑

| 탭 | 컨셉 | 팀원 보완 영역 | 사용 데이터 |
|---|---|---|---|
| 🌌 1 환승 별자리 | 정류장 환승시간 별자리 + 25구 TOP10 + 환승 종류 분해 + 병원 정류장 환승 차트 | (전체 베이스 · 응급실 정보 흡수) | sttn_coords + 환승시간 + 노인 카드 + 병원 좌표 |
| 🌡️ 2 폭염 정류장 | 정류장 50m 내 더위쉼터 유무 | KIM 기후(쉼터→집 보행) 보완 | KIM 더위쉼터 CSV + sttn_coords + 노인 trip |
| 🛒 3 거점 시설 도달 | 시장·공원·병원·복지관·터미널 등 347개 거점 환승 도달 + TOP20 유입 | SHIM 인프라 + YANG 복지 + LEE 의료 동네 단위 보완 | SHIM/YANG/LEE 거점 + 노인 trip OD |
| 🚦 4 횡단보도 안전 | 신호 없는 횡단보도 + 노인 보행사고 1,963건 | (단독 영역 — 어디에도 없음) | 서울 25구 횡단보도 + TAAS |
| 🔀 5 환승 OD | 환승 거점역 from-route → to-route 추적 (10,323건 재구성) | (단독 영역) | elderly_card_trips LAG window 재구성 |

> 💡 응급실 탭은 별자리 탭 사이드바 "🏥 병원 정류장 환승 종류 분해" + 거점 탭 응급·상급병원 75개로 흡수됨.

---

## 데이터 출처

| 출처 | 데이터 | 비고 |
|---|---|---|
| 공공데이터포털 | `monthly_transfer_accessibility` | 정류장 환승시간 825K행 (2025-10) |
| 공공데이터포털 | `elderly_card_trips` | 노인 카드 trip 505K (2026-02-22 일요일) |
| 카카오맵 | 정류장·지하철역 좌표 | sttn_coords 16,532개 |
| OSM | 서울 보행 네트워크 (osmnx, 162K nodes) | cache/, 거점 거리 측정 보조 |
| TAAS | 노인 보행 사고 1,963건 (2024) | 좌표 EPSG:5179→4326 변환 |
| 공공데이터포털 | 서울 25구 횡단보도 40,281건 | 신호유무·음향·고원식 (보수 처리: N 명시만 신호 없음) |
| LEE 차용 | `서울시 병의원 위치 정보.csv` | 응급·상급병원 75개 분리 |
| KIM 차용 | 더위쉼터 4,107·한파쉼터 1,642 | 정류장 50m 내 매칭 |
| SHIM 차용 | 전통시장·은행·마트 등 | 거점급 식별 (110개) |
| YANG 차용 | 노인복지관 62개 | 거점급 식별 |

---

## 폴더 구조

```
260504_submit/
├── README.md                ← 이 파일
├── src/                     ← 데이터 가공·렌더 스크립트
│   ├── 01_build_osm_graph.py        # OSM 보행망 캐시
│   ├── 02_constellation_data.py     # 별자리 + 25구 + 환승 종류 + 병원 정류장
│   ├── 03_emergency_hospital.py     # (응급실 좌표 - 거점에 통합)
│   ├── 04_climate_station.py        # 더위·한파 쉼터 매칭
│   ├── 05_anchor_destinations.py    # 거점 도달 OD
│   ├── 06_build_dashboard.py        # 5탭 HTML 빌더 (최종)
│   ├── 07_rebuild_crosswalk.py      # 횡단보도 보수 재처리
│   ├── 08_expand_anchors.py         # 거점 347개 확장 + TOP20
│   └── 09_transfer_chain.py         # 노인 카드 trip chain LAG 재구성
├── cache/                   ← gitignore (graphml, npy)
├── data/                    ← 가공 결과 JSON
│   ├── constellation.json
│   ├── climate_station.json · heat_shelters.json · cold_shelters.json
│   ├── anchor_access.json
│   ├── shim_mkt.json · shim_centers.json · shim_sup.json · shim_seoul_banks.json
│   ├── emergency_access.json
│   └── transfer_chain.json          ← 환승 OD 재구성 결과
└── outputs/
    ├── transit_dashboard.html       ← 5탭 통합 대시보드 (메인)
    └── tab5_crosswalk.html          ← 횡단보도 단독 뷰 (참고)
```

---

## 실행 순서

```bash
cd YOO/260504_submit/src
uv run python 01_build_osm_graph.py     # 1회, 10~20분
uv run python 02_constellation_data.py  # 별자리 + 25구 통계
uv run python 04_climate_station.py     # 폭염 정류장
uv run python 05_anchor_destinations.py # 거점 OD
uv run python 07_rebuild_crosswalk.py   # 횡단보도 보수 처리
uv run python 08_expand_anchors.py      # 거점 347개 확장
uv run python 09_transfer_chain.py      # 환승 OD 재구성
uv run python 06_build_dashboard.py     # 최종 HTML 생성
```

---

## 산출물 목록 (대회 제출용)

- `outputs/transit_dashboard.html` — 5탭 인터랙티브 대시보드 (메인 산출물)
- `data/transfer_chain.json` — 노인 환승 from→to 재구성 (10,323건)

---

## 핵심 분석 결과

- **재구성된 환승 이벤트**: 10,323건 / 환승 발생 정류장 2,815개
- **거점 시설**: 347개 (시장 110, 공원 77, 응급·상급병원 75, 노인복지관 62, 환승거점 10, 장거리터미널 8, 노인명소 5)
- **TOP1 거점 유입**: 가톨릭대학교 서울성모병원 5,328명
- **신호 없는 횡단보도(보수 처리)**: N 명시만 인정 — Y/'-'/NaN은 신호 있음으로 가정

---

## 데이터 해석 원칙

- **보수 처리**: 공공데이터 결측은 부정 단정 금지. 횡단보도 `보행등유무`는 **'N' 명시된 행만** 신호 없음으로 인정.
- **추측 금지**: 검증 안 된 사실 단언하지 않음. 모르면 "확인 필요" 표기.

---

## 한계

- ⚠️ 노인 카드 trip은 **2026-02-22 일요일 단일 일자** — 평일/주말 구분 불가
- ⚠️ 환승시간 데이터는 노인 한정 아님 (전체 인구 환승) — 노인 trip과 결합 시 인구 가중 추정
- ⚠️ OSM 보행망은 도로 정보 기반, 실제 노인 우회 패턴(계단·턱) 미반영
- ⚠️ 환승 chain 재구성 시 GTX 등 일부 노선이 환승으로 잡힘 (30분 내 별도 카드 태그 = 환승 가정)
- ⚠️ 횡단보도 N 명시 큰 도로 4,208건 — 실제 신호 있을 가능성 일부 포함 (데이터 노이즈)
