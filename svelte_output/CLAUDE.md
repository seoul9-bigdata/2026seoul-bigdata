# CLAUDE.md — svelte_output 가이드

## 프로젝트 개요

서울 노인 도보 생활권 진단 — 5개 도메인 통합 시각화 (2026 서울 빅데이터 활용 경진대회 시각화 부문).

- **스택**: SvelteKit + Tailwind v4 + Svelte 5 runes (JSDoc, TS 안 씀)
- **호스팅**: `@sveltejs/adapter-static` + prerender 전체
- **지도**: Leaflet 1.9 + CartoDB Light tile
- **차트**: Chart.js 4
- **그래프 분석**: pako (gzip 해제) + 자체 Dijkstra/Convex Hull (`$lib/util/isochrone.js`)
- **포트**: dev 5174 (`pnpm dev --port 5174`)

## 디렉토리

```
svelte_output/
├── src/
│   ├── routes/
│   │   ├── +layout.svelte         # Header + main + Footer (도메인별 --pill-accent inject)
│   │   ├── +page.svelte           # / 메인 허브 (Hero stat 4개 + 5 도메인 카드)
│   │   ├── layout.css             # @theme + @utility (Tailwind v4)
│   │   ├── introduce/             # / 서론 (2026/2040 인구 변화 + 4 속도 + Leaflet choropleth)
│   │   ├── conclusion/            # / 결론 (보행자/경사 토글 + Leaflet + radar)
│   │   ├── transit/               # YOO — 5탭 (별자리·폭염·거점·횡단보도·OD)
│   │   ├── climate/               # KIM — 2탭 (쉼터·결빙위험구역)
│   │   ├── infra/                 # SHIM — Tobler + 5 layer 탭
│   │   ├── bokji/                 # YANG — 복지·녹지
│   │   └── medical/               # LEE — 의료 GeoJSON choropleth
│   ├── lib/
│   │   ├── theme.js               # ★ 단일 진실 원천 — 색·차트·도메인
│   │   ├── nav.js                 # ROUTES (theme.js 참조)
│   │   ├── data/                  # 도메인별 inline JSON (HTML 추출)
│   │   ├── actions/viewport.js    # IO action ([data-in-view])
│   │   ├── util/isochrone.js      # OSM Dijkstra + Convex Hull (infra)
│   │   └── components/
│   │       ├── Header.svelte      # 다크 sticky (z-index: 2000)
│   │       ├── Footer.svelte      # 원형 이전/다음 (도메인 액센트 hover)
│   │       ├── Card.svelte
│   │       ├── ChartCard.svelte   # Chart.js canvas wrapper
│   │       ├── MapShell.svelte    # Leaflet div wrapper + 범례
│   │       ├── PillButton.svelte  # 알약 토글 — --pill-accent 사용
│   │       ├── PillTabs.svelte    # 메인 탭
│   │       ├── StatGrid.svelte / StatCard.svelte
│   │       ├── KickerLabel.svelte
│   │       ├── Note.svelte        # warm/cool 톤
│   │       ├── CountUp.svelte     # rAF + IntersectionObserver
│   │       ├── climate/{Shelter,Ice}Tab.svelte
│   │       └── transit/{Constellation,Heat,Anchor,Crosswalk,OD}Tab.svelte
│   ├── app.html                   # Noto Sans/Serif KR + IBM Plex Mono link
│   └── app.d.ts
├── _research/                     # ENSEMBLE 분석 spec
├── static/
└── svelte.config.js               # adapter-static, prerender '*'
```

## 디자인 시스템

### 컬러 토큰 (`src/routes/layout.css`)

라이트 KIM 톤:
```css
--color-bg: #f5f4f0          /* 아이보리 베이스 */
--color-card: #fff           /* 흰 카드 */
--color-card-soft: #f5f4f0   /* 카드 안 더 옅은 베이지 */
--color-text: #2c2c2a        /* 다크 차콜 */
--color-text2: #5f5e5a       /* 보조 */
--color-text3: #888780       /* 라벨 */
--color-text4: #b4b2a9       /* 옅은 보더 */
--color-border: #d3d1c7
--color-dark: #2c2c2a        /* 헤더 */
--color-dark-text: #f1efe8

/* 액센트 */
--color-accent: #d85a30      /* 메인 오렌지 (main_ver1 톤) */
--color-coral: #fb923c       /* 인트로 (climate amber 와 충돌 회피) */
--color-gold: #f5b740        /* 강조용 (다른 곳) */
```

도메인 액센트 (theme.js `DOMAIN_THEME`에서 hex + var ref 동시 보유):
| 도메인 | hex | CSS var |
|---|---|---|
| transit | `#5aadff` | `--color-blue` |
| climate | `#f5b740` | `--color-amber` |
| infra | `#3ecfa0` | `--color-teal` |
| bokji | `#b48ef4` | `--color-purple` |
| medical | `#f472b6` | `--color-pink` |

### `--pill-accent` 자동 주입

`+layout.svelte` 가 현재 라우트 감지 → `<main>` 에 `--pill-accent` CSS 변수 주입. 자식 컴포넌트의 알약 활성 색상이 도메인 액센트로 자동 변경.

```svelte
<!-- +layout.svelte -->
<main style:--pill-accent={ROUTES.find(r => r.slug === path)?.accent}>
```

자식 컴포넌트:
```css
.pill-btn-on { background: var(--pill-accent, var(--color-dark)); }
```

### 폰트
```css
--font-sans:  'Noto Sans KR', 'Apple SD Gothic Neo', system-ui;
--font-serif: 'Noto Serif KR';
--font-mono:  'IBM Plex Mono';
```
Hero 제목 `font-serif`, kicker 라벨 `font-mono`.

### 다크모드 차단
`html { color-scheme: light }` + `input, select, button, textarea { color-scheme: light }`. OS 다크모드 환경에서도 native 폼 요소가 강제 라이트.

## theme.js — 단일 진실 원천

**모든 색·차트 토큰은 `$lib/theme.js`에서 import. 인라인 hex 박지 말 것.**

```js
import {
  DOMAIN_THEME,    // { transit: {color, accent, ...}, climate: ... }
  DOMAINS_4,       // [climate, infra, bokji, medical] — 결론용
  DOMAINS_5,       // 5 도메인 전체
  SCORE_TIERS,     // 도달가능 점수 5단계
  scoreColor(),    // (score) => hex
  scoreBg(),       // (score) => hex (light bg)
  WALK_TYPES,      // 보행자 4종
  AGING_TIERS_2026, AGING_TIERS_2040,
  COMPARE_COLORS,  // 보색 페어 (radar 등) — primary orange ↔ reference teal
  CHART_THEME,     // 폰트, 색, grid, tooltip
  applyChartTheme()  // Chart.js 글로벌 디폴트 적용
} from '$lib/theme.js';
```

차트 한 번 글로벌 적용:
```js
onMount(async () => {
  Chart = await applyChartTheme();
  // ...
});
```

## Svelte 5 runes 컨벤션

- `let x = $state(initial)` — 반응 변수
- `const y = $derived(expr)` — 계산값
- `const z = $derived.by(() => { ... return val })` — 복잡한 derived
- `$effect(() => { ... })` — 사이드 이펙트
- `let { prop1, prop2 } = $props()` — JSDoc로 타입 명시
- 자식 슬롯: `let { children } = $props()` + `{@render children?.()}`
- snippet 전달: `<Card>{#snippet children()}…{/snippet}</Card>`

### `selectedX` 패턴 (무한루프 방지)

reactive 데이터에 의존하는 selection은 **이름만 저장 + derived 객체**:
```js
let selectedGuName = $state(null);
const selectedGu = $derived(selectedGuName ? rankedByName[selectedGuName] : null);
```
이러면 scoreKey 토글 시 ranked 재계산 → selectedGu 자동 업데이트, 별도 setter 불필요.

`$effect` 안에서 state 쓸 때 무한 루프 위험 시 `untrack()` 사용:
```js
import { untrack } from 'svelte';
$effect(() => {
  scoreKey;  // tracked
  untrack(() => { drawGeoLayer(); });  // not tracked
});
```

## Leaflet 패턴

**SSR 안전 + bind:this 타이밍 가드:**
```js
let mapEl = $state();
let mapInited = false;
async function initMap() {
  if (mapInited || !mapEl) return;
  mapInited = true;
  await import('leaflet/dist/leaflet.css');
  const L = (await import('leaflet')).default;
  const map = L.map(mapEl, { ... }).setView([37.555, 127.0], 11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    { subdomains: 'abcd', maxZoom: 19 }).addTo(map);
}
$effect(() => {
  if (mapEl && !mapInited && typeof window !== 'undefined') initMap();
});
onDestroy(() => map?.remove());
```

**GeoJSON choropleth:** `L.geoJSON(geo, { style, onEachFeature })`. SIG_KOR_NM 우선, fallback `name/NAME/sig_kor_nm`.

**커스텀 Canvas 레이어 (zoom 동기화 필수)**: `IceTab.svelte` 참고. `leaflet-zoom-animated` 클래스 + `_animateZoom` 메서드로 `L.DomUtil.setTransform(cv, offset, scale)` 호출. 이 없으면 줌 시 폴리곤이 타일과 따로 놂.

## Chart.js 패턴

```svelte
<ChartCard title="..." onmount={setupChart} />
```
```js
import Chart from 'chart.js/auto'; // 또는 await applyChartTheme()
function setupChart(canvas) {
  new Chart(canvas, {
    type: 'bar',
    data: { ... },
    options: {
      ...CHART_THEME.baseOptions,
      // ...
    }
  });
}
```

데이터셋 색상은 `DOMAIN_THEME[k].color` 또는 `domainColors(['climate', 'infra'])` 사용.

비교 차트 (예: 선택 vs 평균) 두 시리즈는 `COMPARE_COLORS.primary` ↔ `COMPARE_COLORS.reference` 보색 페어.

## 애니메이션 패턴

**전 페이지 공통 토큰**: `theme.js` 의 `ANIM` 객체 (`bar`, `countUp`, `fade`, `chart`, `statReveal`).
페이지마다 inline duration 박지 말 것 — 토큰만 참조.

```js
import { ANIM, barStagger } from '$lib/theme.js';
// ANIM.bar.duration = 850, easing = cubic-bezier(0.16,0.84,0.36,1), stagger = 60
// ANIM.countUp.duration = 900
// ANIM.fade.duration = 220
// ANIM.chart.duration = 700
```

### CountUp (`$lib/components/CountUp.svelte`)
IntersectionObserver + rAF + ease-out cubic. 화면에 보이면 자동 0 → value 카운트업.
**디폴트 duration = `ANIM.countUp.duration`** — 호출부에서 prop 안 줘도 통일됨.
```svelte
<CountUp value={76.7} decimals={1} suffix="점" />
```

### 막대 reveal (CSS)
GPU 합성 `transform: scaleX` 사용. `width` 변경 X. **duration 0.85s + cubic-bezier(0.16,0.84,0.36,1)** 고정.
```svelte
<div class="bar-fill" style:width="{w}%" style:--ad="{i*60}ms"></div>
<style>
.bar-fill {
  animation: bar-reveal 0.85s cubic-bezier(0.16,0.84,0.36,1) both;
  animation-delay: var(--ad, 0ms);
  transform-origin: left center;
  will-change: transform;
}
@keyframes bar-reveal {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}
</style>
```
`prefers-reduced-motion` 가드 필수.

### 토글 시 재애니메이션 — `{#key}`
state 토글 시 자식 트리 destroy + remount → 애니메이션 재생.
```svelte
{#key year}
  <div in:fade={{ duration: 200 }}>
    {#each rows as r, i}
      <div class="bar-fill" style:--ad="{i*22}ms" />
    {/each}
  </div>
{/key}
```

### iOS 토글 스위치
`conclusion/+page.svelte` 의 `.toggle-switch.on .toggle-slider` 참고. 38×22px, ON 시 `--pill-accent` 색.

## OSM 보행 그래프 — Dijkstra 이소크론

**원본 SHIM v6 동등 기능 — 실제 도로망 기반 도달 범위 폴리곤.**

### 데이터
- **파일**: `static/infra_graph.json.gz` (~3.2 MB gzipped, ~4.3 MB raw json)
- **소스**: `final_output/ENSEMBLE/dashboard/2_Shim_infra.html` 의 `GRAPH_GZ` 추출
- **노드**: 266,780 (전체 서울 보행 가능 segment)
- **포맷**: CSR sparse matrix
  - `n` (메타), `lat_base`, `lng_base` (좌표 기준점)
  - `lats`, `lngs` (Uint16, base + i × 1e-5)
  - `row` (Uint32, CSR row pointer), `col` (Uint32, neighbor index), `dist` (Uint16, edge weight m)
  - 모두 base64 + raw deflate (pako 호환)

### API (`$lib/util/isochrone.js`)
```js
import { loadGraph, computeIsochrone } from '$lib/util/isochrone.js';
const G = await loadGraph();   // 모듈 캐시 — 1회만 fetch (~3 sec)
const { ring, count, ms } = computeIsochrone(G, lat, lng, maxDistM);
//   ring: [[lat, lng], ...] | null  (Convex Hull 폴리곤)
//   count: 도달 노드 수
//   ms: 계산 시간
L.polygon(ring, { color, fillOpacity: 0.18 }).addTo(map);
```

### 알고리즘
1. **nearestNode**: 클릭 lat/lng → 유클리드 근사로 최근접 그래프 노드
2. **Dijkstra (Min-Heap)**: src → maxDistM 이내 reachable 노드 집합
3. **Graham scan Convex Hull**: reachable의 lat/lng 점들 → 외곽 폴리곤 ring

### 원본 Python 코드 (참고용)
`scripts/build_osm_graph_isochrone.py` — `final_output/KIM/17_slope_dijkstra_ver3.py` 의 복사본.
주요 함수: `convex_hull_coords(dx_arr, dy_arr, fallback_r, simplify_tol=30)` — `shapely.MultiPoint().convex_hull` 사용.
`isochrone.js` 의 JS 구현은 이 Python 로직의 동등 변환 (shapely → Graham scan).
GRAPH_GZ 생성 파이프라인도 동일 파일에 있음 (OSM 보행 네트워크 → CSR sparse matrix → base64 + raw deflate).

### Infra 페이지 통합
- 점선 원 = 직선 반경 (참고용)
- 채워진 폴리곤 = OSM 도로망 기반 실제 도달 범위
- 보행자/시간/경사 토글 시 자동 재계산
- 첫 진입 시 그래프 fetch (~3 sec) → 이후 클라이언트 메모리에 캐시 (페이지 이동해도 유지)

## 데이터 (`src/lib/data/`)

ENSEMBLE 5개 HTML에서 inline JSON 추출 (Python state-machine 파서로 한글 키·single quote 처리).

| 파일 | 출처 | 키 |
|---|---|---|
| `transit.json` | `0_Yoo_transit.html` | DATA.{stations, anchors, od_stations, ...} |
| `transit_crosswalk.json` | `0_1_crosswalk.html` | ACC, CW |
| `climate.json` | `1_Kim_climate_opt2.html` | 20 keys (DONG_GEO, GU_META, JISEOL, REACH_*, ...) |
| `infra.json` | `2_Shim_infra.html` (v6) | 17 keys (TOBLER_DONG, BANK_SERIES, GU_BANK_*, ...) |
| `bokji.json` | `3_Yang_bokji.html` | DONG, WELFARE, PARK, ... |
| `medical.json` | `4_Lee_medical.html` | COUNTS, DONG_META, GEOJSON, SPEEDS |
| `conclusion.json` | `final_output/ENSEMBLE/conclusion-csv/*.csv` | gus + domains.{climate,infra,bokji,medical} |

📦 OSM 보행 그래프는 `infra.json` 에서 분리되어 **`static/infra_graph.json.gz` (~3.2 MB gzip)** 로 별도 호스팅. infra 페이지 진입 시 lazy fetch + `pako.inflate()` 해제 → `$lib/util/isochrone.js` 가 Dijkstra + Graham scan Convex Hull 실행 → **실제 도로망 기반 도달 폴리곤** 그림.

## 라우팅

`@sveltejs/adapter-static` + `prerender: { entries: ['*'] }` — 모든 라우트 정적 generate. `_layout.svelte`에서 `base` path 적용.

원형 흐름:
```
/  →  /introduce  →  /transit  →  /climate  →  /infra
                                                      ↓
                                            /bokji
                                              ↓
                                            /medical
                                              ↓
                                            /conclusion  →  / (메인으로)
```
`Footer.svelte`가 ROUTES 배열 인덱스 기반 prev/next 자동 계산.

## 스타일 컨벤션

- 페이지별 hero: `<section class="X-hero">` 다크 (`var(--color-dark)`)
- 본문 wrap: `max-width: 1340px`, padding `18px 18px 60px`
- 카드 그리드: `r2` (1.45fr 1fr — 지도/사이드), `r2b` (1fr 1fr — 차트 2열), `sgrid` (4열 통계)
- z-index 위계: header 2000 > Leaflet pane 1000 > popup 700 > marker 600 > overlay 400 > tile 200

## Known issues / 의도된 동작

- **TS 경고 다수** — `@types/leaflet` 미설치. JSDoc strict 모드 in Svelte 5 inferrence noise. 런타임 영향 없음.
- **Tailwind 4 short-form 권고** (`w-[420px]` → `w-105`). 가독성 위해 무시.
- **IceTab Canvas 레이어** — 줌 동기화 위해 `leaflet-zoom-animated` + `_animateZoom` 필수. 빼면 폴리곤 분리됨.
- **dev 서버 reload 시 occasionally HMR 실패** → `pnpm dev` 재시작 필요.
- **첫 진입 시 Leaflet GeoJSON fetch** (남한 raw GitHub URL). 오프라인이면 지도 빈 화면.
- **Infra 페이지 첫 도달 시 OSM 그래프 ~3 MB fetch + 압축 해제 (~2~3 sec)** — Dijkstra 폴리곤 표시 지연. 이후 모듈 캐시.
- **자치구별 점수 집계 원칙** — bokji/medical/infra 는 **동별 점수 평균 → 구로 집계** 패턴 (DONG 데이터 기반).
  단 `ShelterTab` 만 예외 — `REACH_G` (구 단위 캐시) 데이터 자체가 구 단위로 이미 집계되어 있어 동 평균 단계가 없음.
  즉 **데이터 출처가 구 단위인 경우에만 부득이하게 구 직접 집계 사용** (원칙: 데이터 가능하면 동 → 구).
- **교통(transit) 페이지 자치구 필터** — `transit.json` 의 모든 데이터셋 (stations/anchors/heat/climate/emergency/od_stations) 에
  Python 전처리(`scripts/preprocess_transit_gu.py`)로 `gu` 필드 추가 완료. od_stations 는 `ride_gu`/`goff_gu` 두 필드.
  cG === '전체' 면 필터 없음. 매핑 실패 ~1% (서울 외 GTX/경기 경계 좌표).

## Build / Dev

```bash
pnpm dev --port 5174        # 개발 (http://localhost:5174)
pnpm build                  # 정적 build → build/ 폴더
pnpm preview                # build 결과 미리보기
pnpm check                  # svelte-check
```

새 도메인 색 추가 시:
1. `src/routes/layout.css` `@theme` 에 `--color-X` 추가
2. `src/lib/theme.js` `DOMAIN_THEME.x` 객체 추가
3. `src/lib/nav.js` ROUTES 배열에 `domainRoute('x', 'x', '...')` 추가
4. 페이지 만들 때 hero kicker color 적용

## 참고 — 원본 (디자인 기준)

- `final_output/ENSEMBLE/main/main_ver1.html` (2,127줄) — 메인/intro/conclusion 톤
- `final_output/ENSEMBLE/dashboard/1_Kim_climate_opt2.html` — 라이트 KIM 톤 기준
- `final_output/ENSEMBLE/dashboard/2_Shim_infra.html` (v6) — Tobler + canvas 모식도 패턴
- `_research/ensemble_analysis.md` — 5 대시보드 spec 분석
