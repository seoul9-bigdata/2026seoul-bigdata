# ENSEMBLE 5 대시보드 Svelte 마이그레이션 스펙

## 분석 완료 요약

| 파일 | 줄수 | 톤 | 핵심 |
|---|---|---|---|
| `1_Kim_climate_opt2.html` | 2,308 | 라이트 | 디자인 기준 / main-tabs(2) / Canvas 단절망 |
| `3_Yang_bokji.html` | 9,842 | 라이트 | 경사보정 토글 / 동별 반경원 / DONG 426개 |
| `2_Shim_infra.html` | 60,418 | 라이트 | 시설분류 필터 / 대규모 JSON |
| `0_Yoo_transit.html` | 96,811 | 다크 | Kakao Maps / 5탭 |
| `4_Lee_medical.html` | 623 | 라이트 | 최소형 / 거리 막대 |

## 통합 컬러 토큰

### 라이트 톤 (KIM/YANG/SHIM/LEE)
- 배경: `#f5f4f0` · 헤더: `#2c2c2a` · 카드: `#fff` · 보더: `#d3d1c7`
- 텍스트: `#2c2c2a` (주) / `#5f5e5a` `#888780` (보조)
- 점수: `#2E7D32` (높음) / `#F57F17` (중) / `#C62828` (낮음)
- 특수: `#FF8C00` (열) / `#4A90D9` (냉) / `#2c2c2a` (버튼 on)

### 다크 톤 (YOO 전용)
- `#070910` 배경 / `#edecea` 텍스트 / `#3ecfa0` `#5aadff` `#ff5f5f`

## 공통 DOM 골격
```
<header>
<div class="wrap">
  <div class="main-tabs">      (옵션, 다중탭)
  <div class="ctrl">            (컨트롤 패널)
  <div class="sgrid">           (4열 통계)
  <div class="r2">              (지도/차트 1.45fr 1fr)
  <div class="r2b">             (차트 2열)
  <table>                       (상세표)
  <div class="note">            (설명)
```

## 차트·지도 라이브러리
- **지도**: KIM/YANG/SHIM/LEE = **Leaflet v1.9.4 + CartoDB Light Tile** ✅ 통일됨 / YOO = Kakao Maps SDK v2
- **차트**: 전 도메인 = **Chart.js v4.4.1** ✅ 통일됨
- 차트 인스턴스 수: KIM(2) / YANG(3) / SHIM(3+) / YOO(여러) / LEE(1)
- Canvas ID 네이밍: `gc-chart`, `wc-chart`, `cv-network` 등

## 인라인 JSON 변수 (Agent C가 추출)

### KIM Climate
- `SHELTERS` (line ~1100~2000, 쉼터 배열)
- `GU_META` (line ~2100~2800, 자치구 메타)

### YANG Bokji ⭐ 가장 큼
- `DONG` (line ~580~3400, 426개 동 × 21필드)
- `WELFARE`, `PARK`
- shape: `{gu, dong, pop65, aging, w[], p[], wc[], pc[], tobler, vuln, clat, clng}`

### SHIM Infra (대규모)
- `INFRA_DATA` 또는 `FACILITY`

### YOO Transit
- `STATIONS`, `LINES`, `FREQUENCY_DATA`

### LEE Medical
- `HOSPITAL_DATA`, `PHARMACY`, `ACCESSIBILITY_SCORES`

## 컨트롤 패턴
- 보행자 유형 4개: 일반(1.28)/노인(1.12)/보조(0.88)/하위15%(0.70)
- 시간 버튼: 15/30/45분
- 행정 단위: 자치구/행정동
- 레이어 토글: 더위·한파·경사·배경
- select: 자치구 드롭다운
- 활성: `.classList.add('on')`

## 인터랙션
- Leaflet `.bindTooltip(html)` + 고정 tooltip 박스 (KIM)
- 호버 행 강조 (`tr:hover td { background: #fafaf8 }`)
- 클릭→지도이동 (테이블 행 클릭)
- 차트 update() — 컨트롤 변경 시 재그리기
- YANG: Circle + circleMarker 동적 추가
- KIM: Canvas force-directed graph
- YOO: Kakao InfoWindow

## Svelte 마이그레이션 체크리스트

### 공통 컴포넌트 (Agent B 작성 완료)
- ✅ `Card` `PillButton` `PillTabs` `KickerLabel`
- ✅ `StatGrid` `StatCard` `ChartCard` `MapShell` `Note`

### 라우트 (메인 스레드 작업 완료)
- ✅ `/transit` `/climate` `/infra` `/bokji` `/medical` `/introduce` `/conclusion`

### 색상 토큰
- ✅ `layout.css` Tailwind v4 `@theme` 정의

### 데이터 (Agent C 진행 중)
- ⏳ `lib/data/{transit,climate,infra,bokji,medical}.json`

### 상태 관리 (다음 단계)
- 보행자 속도, 시간, 자치구 stores

---

**기록 시점**: Agent A (Explore) 분석 결과 — 2026-05-07
