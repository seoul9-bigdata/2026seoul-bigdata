# 서울시 노인 교통 안전·이동 분석

서울시 빅데이터 캠퍼스 활용 경진대회(시각화 부문) 출품 프로젝트.
공공데이터 기반으로 서울 노인의 보행 사고·대중교통 이동·환승 부담을 결합 분석하고 인터랙티브 지도·차트로 시각화한다.

## 핵심 아이디어

- TAAS 노인 보행사고 + 노인 카드 trip + 환승 접근성 + 정류소·역 좌표 = **단일 정류소 단위 위험도 산출**
- 노인 이용량 ↑ × 환승 시간 ↑ × 주변 사고 ↑ = **종합 위험 정류소** (정책 우선 개선 대상)
- 사고 데이터(2024년) + trip 데이터(2026-02-22 일요일) + 환승(2025-10) — 시간 단위 다른 다층 데이터 결합

## 데이터 소스

| 출처 | 데이터 | 비고 |
|---|---|---|
| 공공데이터포털 (1613000) | `BusRoutespecificStopInformation`, `urban_railway`, `BusRoute`, `Region`, `RegionalTransportationCardUsageSyntheticData` | 정류소·노선·노인 카드 trip 합성데이터 |
| 공공데이터포털 | `monthly_transfer_accessibility` | 정류소별 환승 시간·인원 (2025-10) |
| TAAS | 서울시 노인 보행 사고 (2024) | 도로공단 GIS 시스템 크롤링 (좌표 EPSG:5179→4326 변환) |
| 카카오맵 | 정류소·지하철역 좌표 매칭 | 정류소명 · 시도 prefix 기반 검색 |
| 서울 열린데이터광장 | 동작구 횡단보도 (파일럿) | 신호 유무·녹색신호 시간·연장 |
| 공공데이터포털 | 서울 25구 횡단보도 (`서울특별시_자치구_횡단보도_20260320.csv`, 40,281건) | 좌표·신호유무·음향신호기·고원식·작동식 (시간·연장 데이터 없음) |

## 디렉토리 구조

```
prototype-seoul/
├── data/
│   ├── seoul.duckdb                 # 메인 분석 DB
│   ├── raw/                          # TAAS 원본 JSON
│   └── processed/                    # TAAS CSV (lat/lon 변환 후)
├── 서울특별시_동작구_횡단보도_*.csv  # 동작구 파일럿 횡단보도
├── 서울특별시_자치구_횡단보도_*.csv  # 서울 25구 전체 횡단보도 (40,281건, 신호·음향·고원식)
│
├── 데이터 수집 노트북 (DuckDB 적재)
│   ├── data_ingestion.ipynb          # 마스터/레퍼런스 (biz, trfc_mns, card_type, user_type)
│   ├── sido.ipynb                    # 법정동 코드 (region 테이블)
│   ├── bus_route.ipynb               # 버스 노선
│   ├── route_station.ipynb           # 노선 × 정류소 (768K)
│   ├── urban_railway.ipynb           # 지하철 노선 (railway_line)
│   ├── urban_railway_station.ipynb   # 지하철역 (railway_station)
│   ├── transfer_accessibility.ipynb  # 환승 접근성 (825K)
│   ├── trip_volume.ipynb             # 연간 노선×정류소 이용량 (속도 한계로 abandon)
│   ├── card_trips.ipynb              # 노인 카드 trip-level (505K, 2026-02-22)
│   └── kakao_geocode.ipynb           # 정류소·지하철역 카카오 좌표 매칭 (~36K)
│
├── 분석·시각화 노트북
│   ├── prototype.ipynb               # 동작구 파일럿 (사고 + 횡단보도)
│   ├── seoul_elderly_viz.ipynb       # 서울 25구 결합 분석 (사고+이용+환승)
│   ├── analysis_extra.ipynb          # OD·시간대·노선 분석 + Chart.js 대시보드
│   └── crosswalk_safety.ipynb        # 서울 25구 신호 없는 횡단보도 × 노인 사고
│
├── 산출물 (HTML)
│   ├── kakao_map.html                # 동작구 파일럿 지도
│   ├── seoul_elderly_map.html        # 서울 25구 종합 위험 지도
│   ├── seoul_elderly_od_flow.html    # 노인 OD 흐름선 (곡선·색상·필터)
│   ├── seoul_elderly_dashboard.html  # Chart.js 인터랙티브 대시보드 (3탭)
│   └── crosswalk_safety_map.html     # 신호 없는 횡단보도 + 노인 사고 지도
│
└── 산출물 (PNG)
    ├── elderly_time_pattern.png
    ├── transfer_time_by_hour.png
    └── elderly_by_mode.png
```

## DuckDB 스키마 (`data/seoul.duckdb`)

### 마스터/레퍼런스
- `biz` (10): 정산사업자 (티머니, 마이비 등)
- `trfc_mns` (1,959): `(clcln_bzmn_id, clcln_bzmn_trfc_mns_cd)` → 운영주체명 (서울교통공사 1-4 / 5-8 등)
- `card_type` (105): 카드 유형
- `user_type` (8): 이용자 유형 (`04` = 경로/노인)
- `region` (20,560): 전국 법정동 코드 (10자리)

### 노선·정류소
- `bus_route` (21,956): 버스 노선
- `route_station` (768,065): 노선 × 정류소 — PK: `(rte_id, sttn_seq)`
- `railway_line` (51): 도시철도 노선 — PK: `(sarea_nm, rte_id)`
- `railway_station` (1,103): 도시철도 역 — PK: `(sarea_nm, rte_id, sttn_id)`

### 분석 대상 사실 테이블
- `monthly_transfer_accessibility` (825,519): 환승 시간·인원, PK: `(opr_ym, sttn_id, inoutf_type_cd, trnf_type_cd, tzon)`
- `elderly_card_trips` (505,754): 노인 trip-level 이벤트 (2026-02-22), PK: `(vr_card_no, ride_dt, rte_id)`

### 좌표 매핑
- `stop_coords` (~34,723 수도권): 버스 정류소 좌표 — PK: `(ctpv_cd, sgg_cd, sttn_nm)`, 매칭률 약 95%
- `station_coords` (~774 수도권): 지하철역 좌표 — PK: `(ctpv_cd, sttn_nm)`, 매칭률 ~99.5%
- `sttn_coords` (view): `sttn_id` → `(lat, lon)` 통합 lookup

## 설치 & 실행

```bash
# 의존성 설치 (uv 권장)
uv sync

# .env 작성
cat > .env <<EOF
MY_SERVICE_KEY=공공데이터포털_API_KEY
KAKAO_KEY=카카오_REST_API_KEY
EOF

# DB 압축 해제 (한 번만 — 원본은 .gitignore로 무시됨)
gunzip -k YOO/data/seoul.duckdb.gz   # → YOO/data/seoul.duckdb (159MB)

# Jupyter 실행
jupyter notebook
# 또는 IDE (PyCharm/VS Code/Cursor)에서 .ipynb 직접 열기
```

> **DB 파일 안내**: `seoul.duckdb`는 159MB라 GitHub에 직접 올리지 못해 **gzip 압축본**(`seoul.duckdb.gz`, 45MB)만 올라갑니다. 클론 후 `gunzip -k`로 한 번만 풀어주세요. 원본 `.duckdb`는 `.gitignore`에 등록되어 있어 다시 올라가지 않습니다.

### HTML 산출물 보기

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/seoul_elderly_dashboard.html
```

(카카오맵 SDK가 일부 브라우저에서 `file://`을 막을 수 있으므로 로컬 서버 권장.)

## 데이터 적재 순서 (DB 처음부터 만들 때)

`data/seoul.duckdb`가 없으면 아래 순서대로 노트북 실행:

1. `data_ingestion.ipynb` — 마스터 테이블 (biz/trfc_mns/card_type/user_type)
2. `sido.ipynb` — region (전국 법정동)
3. `bus_route.ipynb` — bus_route
4. `route_station.ipynb` — 정류소 (전국, 시간 1~2시간)
5. `urban_railway.ipynb` — railway_line
6. `urban_railway_station.ipynb` — railway_station
7. `transfer_accessibility.ipynb` — 환승 (서울만, 2025-10)
8. `card_trips.ipynb` — 노인 trip (서울 1,157 버스 + 25 지하철 노선, ~30분)
9. `kakao_geocode.ipynb` — 좌표 매칭 (수도권 ~36K, ~1.5시간)
10. `prototype.ipynb` — TAAS 사고 크롤링 (서울 전체 2024년)
11. (분석) `seoul_elderly_viz.ipynb` / `analysis_extra.ipynb` 차례로 실행
12. (분석) `crosswalk_safety.ipynb` — 서울 25구 횡단보도 CSV + TAAS 사고 결합 (DuckDB 불필요, CSV 2개만 있으면 실행)

## 주요 분석 결과 (2026-02-22 일요일 기준)

### OD 흐름
- **강남구 자족비율 68%** — 자기 구 안에서 가장 많이 이동
- **송파구 서울외 비율 70.7%** — 남양주·포천 방면 외래 출타 다수
- **종로/중구/동대문** — 도심권은 자기 구 내 이동 비중 높음

### 시간대 활동
- 첫 승차 피크: 05~06시 (8K~10K명)
- 외출 피크: 12~14시 (각 30K+ trip)
- 일일 1회만 이용: 234,896명 (68%)

### 노선·운영사
- 노인 이용 TOP 노선: **2호선 76,763건**, 5호선 56K, 7호선 46K, 3·4호선 각 46K
- 운영주체별: 서울교통공사(1-4) 209K → 서울교통공사(5-8) 147K → 코레일 52K
- 평균 이동거리: 도시철도 7~10km, 버스 2~4km

### 정류소 종합 위험도 (Z-score 합산)
- 노인 이용 ↑ × 환승 시간 ↑ × 주변 사고 ↑ — 정책 우선 개선 후보 정류소 식별

### 신호 없는 횡단보도 × 노인 사고 (`crosswalk_safety.ipynb`)
- 서울 25구 횡단보도 40,281건 중 **보행등 없음** 비율을 자치구별로 집계
- TAAS 노인 사고 1,963건과 BallTree 공간 결합 — 사고 50m / 100m 반경 내 신호 없는 횡단보도 존재 비율
- 인프라 결핍도(신호 + 음향신호기 + 고원식 z-score 합) vs 사고 산점도 — 정책 우선 자치구 식별

## 한계 및 향후 작업

- ⚠️ 카드 trip 데이터: **2026-02-22 일요일 단일 일자** — 평일 추가 수집 시 주말/평일 비교 가능
- ⚠️ 공공데이터 API: 서울만 합성데이터 제공, 인천·대전·대구 등 미제공
- ⚠️ 동명이정류소(예: "관악구보훈회관"이 DB는 금천구·실제는 관악구) — `find_stop_coords_loose`로 일부 보정
- ⚠️ TAAS 사고와 카드 trip 시간 단위 불일치 (1년 vs 1일) → 정량 인과 추론보다 **상관 패턴**으로 해석
- ⚠️ 25구 횡단보도 데이터: 신호 *유무*만 있고 **녹색신호 시간/연장은 없음** (동작구 파일럿 CSV에만 존재)
- 🔜 평일 카드 trip 1일 추가 수집 → 주말/평일 비교
- 🔜 정류소 ARS 번호 + 차로 종류(중앙/일반) 매칭 — 서울 열린데이터광장 CSV 기반

## 산출물 미리보기

- **`seoul_elderly_dashboard.html`** — Chart.js 3탭 대시보드 (OD·시간대·노선)
- **`seoul_elderly_map.html`** — 카카오맵 종합 위험 지도 (사고·이용·환승·결합)
- **`seoul_elderly_od_flow.html`** — 노인 OD 흐름선 (곡선·색상 그라디언트·슬라이더 필터)
- **`crosswalk_safety_map.html`** — 신호 없는 횡단보도 + 노인 사고 (자치구 필터)
