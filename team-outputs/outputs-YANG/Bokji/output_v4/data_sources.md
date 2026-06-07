# 데이터 출처 명세 — Bokji v4

> 서울시 노인 보행일상권 분석 v4 파이프라인에서 사용된 전체 데이터셋의 출처 및 활용 방식 정리  
> 작성 기준: `compute_tobler_v4.py` + `generate_dashboard_v4.py`

---

## 1. 서울 열린데이터 광장 (data.seoul.go.kr) 데이터

---

### 1-1. 서울시 사회복지시설 (노인여가복지시설) 목록

| 항목 | 내용 |
|------|------|
| **파일명** | `서울시 사회복지시설(노인여가복지시설) 목록.csv` |
| **포털 데이터셋명** | 서울시 사회복지시설(노인여가복지시설) 목록 |
| **제공기관** | 서울특별시 복지정책실 |
| **파일 형식** | CSV (EUC-KR) |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py`, `generate_dashboard_v4.py` |

**활용 방식**

원본에서 시설주소 컬럼을 추출해 `geocode_cache.json`을 조회하여 WGS84 좌표(lat, lng)로 변환한다. 주소가 결측이거나 지오코딩에 실패한 시설은 제외하고 **185개** 시설만 분석에 사용한다.

시설유형 컬럼을 파싱해 3가지로 재분류한다.
- `노인복지관` / `노인교실` / `노인복지관(소규모)`

이후 두 스크립트에서 목적이 갈린다.

- **`compute_tobler_v4.py`**: 185개 시설 좌표를 OSM 그래프의 최근접 노드(`nearest_nodes`)에 매핑하고, 노드별 시설 수를 딕셔너리로 집계한다. Dijkstra 결과에서 도달 가능한 노드 집합과 교집합을 취해 **동별 복지시설 도달 수**를 산출한다.
- **`generate_dashboard_v4.py`**: 시설명·자치구·시설유형·좌표를 지도 마커 데이터로 직렬화한다. 대시보드 지도에서 시설유형별 색상으로 표시된다.

---

### 1-2. 서울시 주요 공원현황 (2026 상반기)

| 항목 | 내용 |
|------|------|
| **파일명** | `서울시 주요 공원현황(2026 상반기).xlsx` |
| **포털 데이터셋명** | 서울시 주요공원 현황 |
| **제공기관** | 서울특별시 푸른도시국 공원녹지과 |
| **기준 시점** | 2026년 상반기 |
| **파일 형식** | XLSX |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py`, `generate_dashboard_v4.py` |

**활용 방식**

공원 데이터는 WGS84 좌표(X_WGS84, Y_WGS84)가 원본에 포함되어 있어 지오코딩이 불필요하다. `지역` 컬럼으로 서울시 25개 자치구만 필터링하고 좌표가 유효한 **132개** 공원을 사용한다.

- **`compute_tobler_v4.py`**: 공원 좌표를 OSM 최근접 노드에 매핑하고 노드별 공원 수를 집계한다. Dijkstra 도달 범위 내 노드를 기준으로 **동별 공원 도달 수**를 산출한다. 복지시설과 동일한 Dijkstra 결과를 재활용하므로 추가 계산이 없다.
- **`generate_dashboard_v4.py`**: 공원명·자치구·면적·좌표를 지도 마커 데이터로 직렬화한다. 대시보드 지도에서 면적에 비례한 크기의 원으로 표시된다.

---

### 1-3. 서울시 고령자 현황

| 항목 | 내용 |
|------|------|
| **파일명** | `고령자현황_20260421103806.csv` |
| **포털 데이터셋명** | 서울시 동별 주민등록인구 현황 (고령자) |
| **제공기관** | 서울특별시 (행정안전부 주민등록 통계 기반) |
| **기준 시점** | 2025년 4분기 |
| **다운로드 일시** | 2026년 4월 21일 10:38:06 (파일명 타임스탬프 기준) |
| **파일 형식** | CSV (UTF-8-sig, 4행 멀티 헤더) |
| **v4 직접 로드** | ❌ 간접 의존 — `analysis_v2.py`가 처리 → `dong_reachability_v2.csv`에 내장됨 |

**활용 방식**

v4 스크립트가 직접 읽지 않는다. `analysis_v2.py`가 이 파일을 읽어 행정동 단위로 집계한 뒤, 아래 세 지표를 `dong_reachability_v2.csv`에 포함시킨다. v4는 이 CSV를 읽을 때 해당 컬럼을 그대로 승계한다.

- `65세이상인구`: 65세 이상 주민등록 인구 (내국인 + 등록외국인 합산)
- `고령화율`: 65세이상인구 / 전체인구 × 100
- `vulnerability_v2`: 복지박탈 50% + 공원박탈 50% 가중 합산 후 Min-Max 정규화한 취약도 지수

대시보드 상세표의 65세이상·고령화율·취약도 컬럼이 모두 이 원본에서 비롯된다.

```
고령자현황.csv → analysis_v2.py → dong_reachability_v2.csv
                                         ↓ compute_tobler_v4.py
                                   dong_reachability_v4.csv
                                         ↓ generate_dashboard_v4.py
                            대시보드 상세표 (65세이상 / 고령화율 / 취약도)
```

> 필터 조건: 구분='소계', 동명='소계'인 합계·소계 행 제거 → 행정동 단위 데이터만 추출

---

## 2. 서울 열린데이터 광장 외 데이터

---

### 2-1. 행정동 경계 GeoJSON

| 항목 | 내용 |
|------|------|
| **파일명** | `HangJeongDong_ver20230701.geojson` (로컬 저장 없음) |
| **출처** | GitHub — [vuski/admdongkor](https://github.com/vuski/admdongkor) (ver20230701) |
| **라이선스** | 행정안전부 공공데이터 가공물 (MIT) |
| **기준일** | 2023년 7월 1일 행정동 고시 기준 |
| **취득 방법** | 런타임 HTTP GET — 로컬 캐시 없이 매 실행마다 다운로드 |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py`, `generate_dashboard_v4.py` |

**활용 방식**

서울시 행정동 경계 폴리곤에서 `sido == '11'`(서울)만 추출해 426개 행정동 데이터를 확보한다. 폴리곤의 centroid를 계산해 (centroid_lon, centroid_lat)를 각 동의 출발점으로 사용한다.

- **`compute_tobler_v4.py`**: centroid 좌표를 Dijkstra 출발 노드(`nearest_nodes`)로 사용한다. 동별 경사 보정 Dijkstra의 시작점이 이 값이다.
- **`generate_dashboard_v4.py`**: 동별 반경 표시 기능(동별 반경 표시 ON)에서 각 행정동 원의 중심좌표로 사용한다. 또한 구명/동명을 `동_key`(`구명_동명`) 형식으로 조합해 데이터 조인 키로 활용한다.

---

### 2-2. OSM 서울 보행 네트워크

| 항목 | 내용 |
|------|------|
| **파일명** | `output_v2/seoul_walk.graphml` (약 188MB) |
| **출처** | OpenStreetMap (© OpenStreetMap contributors, ODbL) |
| **취득 방법** | `osmnx.graph_from_place("Seoul, South Korea", network_type="walk")` → GraphML 캐시 저장 |
| **캐시 전략** | 파일 존재 시 로드 / 없으면 자동 다운로드 후 저장 |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py` |

**활용 방식**

v4 파이프라인의 핵심 계산 기반이다. 서울 전역의 보행 가능 도로(footway, pedestrian, residential 등)를 노드·엣지 그래프로 표현하며, 로드 후 undirected 변환(`to_undirected`)해 사용한다.

세 가지 용도로 쓰인다.

1. **복지시설·공원 노드 매핑**: 185개 복지시설과 132개 공원의 WGS84 좌표를 그래프 내 최근접 노드(`nearest_nodes`)로 변환한다.
2. **동 중심점 노드 매핑**: 426개 행정동 centroid를 그래프 노드로 변환해 Dijkstra 출발점으로 사용한다.
3. **Dijkstra 최단거리 계산**: 동당 1회 `single_source_dijkstra_path_length(cutoff=MAX_DIST)`를 실행해 도달 가능한 노드와 거리를 반환한다. 이후 속도별 threshold 필터로 각 보행자 유형의 도달 노드 집합을 추출한다.

---

### 2-3. 복지시설 지오코딩 캐시

| 항목 | 내용 |
|------|------|
| **파일명** | `output/geocode_cache.json` |
| **출처** | Kakao Maps API 결과를 `analysis_v2.py`가 캐시로 저장한 파일 |
| **구조** | `{ "주소 문자열": { "lat": float, "lng": float } }` |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py`, `generate_dashboard_v4.py` |

**활용 방식**

복지시설 목록(1-1)의 시설주소 문자열을 키로 이 캐시를 조회해 WGS84 좌표를 얻는다. v2 파이프라인에서 Kakao Maps API를 호출해 사전에 생성된 파일이므로, v4는 API 재호출 없이 결과를 재활용한다. 캐시에 없는 주소는 해당 시설을 분석에서 제외한다.

---

### 2-4. 동별 Tobler 경사 보정 비율 (LEE팀 산출물)

| 항목 | 내용 |
|------|------|
| **파일명** | `medical_LEE/outputs/tobler_ratio_LEE.csv` |
| **출처** | 의료 접근성 분석팀 (LEE) — `04_slope_correction.py` 실행 결과 |
| **원본 데이터** | 국토지리정보원 서울시 표고점 5000 (`N3P_F002.shp`) |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py` |

**활용 방식**

`dong_reachability_v2.csv`에 `동_key` 기준으로 left join해서 각 동의 `tobler_ratio`를 붙인다. 매칭되지 않는 동(n=미소수)은 1.0(평지)으로 대체한다.

이 값은 두 곳에서 사용된다.

1. **MAX_DIST 동적 계산**: `max(BASE_SPEEDS.values()) × max(tobler_ratio) × 1800s`로 Dijkstra의 전역 cutoff를 결정한다. tobler_ratio가 1.0을 초과하는 동이 있을 경우를 대비해 실제 최대값으로 계산한다.
2. **속도별 threshold 계산**: 각 동의 Dijkstra 결과에서 `speed_mps × tobler_ratio × 1800s` 이하인 노드만 도달 가능으로 판정한다. 경사가 심한 동일수록 tobler_ratio가 낮아 도달 반경이 줄어든다.

생성 방법 요약:
```
표고점 SHP → 행정동 공간결합(sjoin) → 동별 고도차(h_max - h_min) 집계
→ slope ≈ 고도차 / (√면적 × 1.13)  (원형 동 가정)
→ Tobler 함수: V = 6 × exp(−3.5 × |slope + 0.05|)
→ tobler_ratio = V(slope) / V(0)   (평지 대비 속도 비율)
```

---

### 2-5. 기존 도달가능성 데이터 (v2 산출물)

| 항목 | 내용 |
|------|------|
| **파일명** | `output_v2/dong_reachability_v2.csv` |
| **출처** | `analysis_v2.py` 실행 결과 (팀 자체 분석 산출물) |
| **v4 직접 로드** | ✅ `compute_tobler_v4.py` |

**활용 방식**

v4 계산의 출발점이다. 이 파일에는 경사 보정 없이 4가지 보행속도 기준으로 계산한 원본 도달 수와 인구통계가 담겨 있다. `compute_tobler_v4.py`는 이 파일을 읽고 `tobler_ratio_LEE.csv`를 조인한 뒤, 경사 보정 Dijkstra로 산출한 보정값 컬럼 6개(복지·공원 × 노인·보조기기·하위15%)를 추가해 `dong_reachability_v4.csv`를 생성한다.

원본 도달 수(`복지_일반인`, `공원_일반인` 등)는 v4에서도 그대로 유지되어 도달가능점수의 분모(일반인 기준값)로 사용된다. 인구통계(`65세이상인구`, `고령화율`, `vulnerability_v2`)도 수정 없이 v4 결과물로 이어진다.

---

## 3. 요약 테이블

| 데이터 | 출처 | 서울 열린데이터 광장 | v4 직접 로드 |
|--------|------|:-------------------:|:------------:|
| 서울시 노인여가복지시설 목록 | 서울 열린데이터 광장 | ✅ | ✅ |
| 서울시 주요공원현황 | 서울 열린데이터 광장 | ✅ | ✅ |
| 서울시 고령자현황 | 서울 열린데이터 광장 | ✅ | ❌ (v2 경유) |
| 행정동 경계 GeoJSON | GitHub (vuski/admdongkor) | ❌ | ✅ |
| OSM 보행 네트워크 | OpenStreetMap | ❌ | ✅ |
| 복지시설 지오코딩 캐시 | Kakao Maps API (팀 생성) | ❌ | ✅ |
| tobler_ratio_LEE.csv | LEE팀 산출 (원본: 국토지리정보원) | ❌ | ✅ |
| dong_reachability_v2.csv | 팀 자체 분석 산출물 | ❌ | ✅ |

---

*생성일: 2026-05-06 · Bokji v4 파이프라인*
