# 의료 대시보드 지도 통합 구현 계획

> 작성 목적: 구현 세션에서 이 문서만 읽고 바로 코딩할 수 있도록 모든 결정을 사전에 확정.  
> 참조 파일: `bokji/+page.svelte`, `climate/ShelterTab.svelte`, `medical/+page.svelte` (현재)

---

## 1. 목표 상태 (완성 시 지도 모습)

단일 Leaflet 지도 위에 4개 레이어가 독립 토글됨:

| 레이어 | 기본값 | 설명 |
|---|---|---|
| **Choropleth** (동 색칠) | ON | 행정동 polygon을 도달가능점수 색상으로 채색 |
| **병의원 마커** | ON | 의원/병원/보건소/종합병원 circleMarker |
| **약국 마커** | ON | 약국 circleMarker |
| **동 반경 원** | OFF | 각 행정동 centroid 기준 보행 반경 점선 원 + 중심점 핀 |

현재 코드 문제점:
- 지도가 `facilityMap` (POI만) 하나뿐 — choropleth 분리 보관 중 (주석)
- 두 지도를 **하나로 통합**해야 함

---

## 2. 아키텍처 결정

### 2-1. 단일 지도 통합 (가장 중요한 결정)

현재 구조:
```
mapEl2 → facilityMap (POI only)
+ CHOROPLETH_MAP_ARCHIVED (주석)
```

목표 구조:
```
mapEl → map (Leaflet instance)
  ├── geoLayer       (choropleth, L.geoJSON)
  ├── hospGroup      (L.layerGroup)
  ├── pharmGroup     (L.layerGroup)
  └── dongCircleGroup (L.layerGroup, 동적 rebuild)
```

### 2-2. 동 centroid 계산 전략

**외부 데이터 불필요** — GEOJSON polygon에서 직접 계산.

```js
function polygonCentroid(geometry) {
  const ring = geometry.type === 'MultiPolygon'
    ? geometry.coordinates[0][0]   // 섬 등 멀티폴리곤 대응
    : geometry.coordinates[0];
  let lat = 0, lng = 0;
  ring.forEach(([lo, la]) => { lng += lo; lat += la; });
  return [lat / ring.length, lng / ring.length];
}

// module scope (스크립트 최상위에 선언)
const dongCentroids = {};
GEOJSON.features.forEach(f => {
  dongCentroids[f.properties.dc] = polygonCentroid(f.geometry);
});
```

- `dongCentroids[dc]` → `[lat, lng]` 형태로 Leaflet에 바로 사용 가능
- 계산 비용: 426개 polygon × 수십~수백 점 = 무시할 수준 (동기, 즉시)
- climate.json import 불필요 (4MB 절약)

---

## 3. 상태 변수 변경 사항

### 제거
```js
let mapEl2 = $state();       // → mapEl로 교체
let facilityMap = null;      // → map으로 rename
```

### 추가/변경
```js
// Leaflet 인스턴스 (rename)
let mapEl = $state();
let map = null;
let geoLayer = null;
let hospGroup = null;
let pharmGroup = null;
let dongCircleGroup = null;

// 레이어 토글 상태 (기존 showHosp/showPharm 유지, 새 항목 추가)
let showChoropleth = $state(true);    // NEW
let showHosp = $state(true);          // 기존
let showPharm = $state(true);          // 기존
let showDongCircle = $state(false);   // NEW
```

---

## 4. `onMount` 전체 구조

```js
onMount(async () => {
  const L = (await import('leaflet')).default;
  await import('leaflet/dist/leaflet.css');

  // ── 지도 초기화 ──
  map = L.map(mapEl, { zoomControl: true, attributionControl: false })
         .setView([37.5665, 126.978], 11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd', maxZoom: 18
  }).addTo(map);

  // ── Layer 1: Choropleth ──
  geoLayer = L.geoJSON(GEOJSON, {
    style: styleFeature,
    onEachFeature: (feat, layer) => {
      layer.bindTooltip(tooltipContent(feat), { sticky: true });
      layer.on('mouseover', function () {
        this.setStyle({ weight: 2, color: '#FFD700', fillOpacity: 0.95 });
      });
      layer.on('mouseout', function () {
        geoLayer?.resetStyle(this);
      });
    }
  }).addTo(map);

  // ── Layer 2 & 3: POI 마커 ──
  hospGroup = L.layerGroup().addTo(map);
  pharmGroup = L.layerGroup().addTo(map);

  facilities.HOSP.forEach((h) => {
    const col = HOSP_COLOR[h.sub] || '#f472b6';
    L.circleMarker([h.lat, h.lng], {
      radius: 4, fillColor: col, color: '#fff', weight: 0.8, fillOpacity: 0.85
    })
      .bindTooltip(`<b>${h.name}</b><br><span style="color:#888780">${h.sub}</span>`,
        { direction: 'top', offset: [0, -4] })
      .addTo(hospGroup);
  });

  facilities.PHARM.forEach((p) => {
    L.circleMarker([p.lat, p.lng], {
      radius: 3.5, fillColor: '#10b981', color: '#fff', weight: 0.8, fillOpacity: 0.85
    })
      .bindTooltip(`<b>${p.name}</b><br><span style="color:#888780">약국</span>`,
        { direction: 'top', offset: [0, -4] })
      .addTo(pharmGroup);
  });

  // Layer 4 (dongCircleGroup)는 $effect에서 동적 생성 — onMount에서 불필요

  // ── Chart.js ──
  await initCharts();
});
```

---

## 5. `$effect` 목록 (전체)

### Effect 1: Choropleth 스타일 갱신 (컨트롤 변경 시)
```js
$effect(() => {
  void cB; void cT; void cF; void cSlope;
  if (!geoLayer) return;
  geoLayer.setStyle(styleFeature);
  geoLayer.eachLayer((l) => {
    // @ts-ignore
    l.setTooltipContent(tooltipContent(l.feature));
  });
});
```

### Effect 2: Choropleth 레이어 토글
```js
$effect(() => {
  if (!map || !geoLayer) return;
  showChoropleth ? geoLayer.addTo(map) : geoLayer.remove();
});
```

### Effect 3: 병의원/약국 레이어 토글 (기존 코드 동일)
```js
$effect(() => {
  if (!hospGroup || !pharmGroup || !map) return;
  showHosp ? hospGroup.addTo(map) : hospGroup.remove();
  showPharm ? pharmGroup.addTo(map) : pharmGroup.remove();
});
```

### Effect 4: 동 반경 원 빌드 + 토글 (핵심 신규)
```js
$effect(() => {
  // 반응 의존성: showDongCircle + 점수 계산에 쓰이는 모든 컨트롤
  void showDongCircle; void cB; void cT; void cSlope; void cF;
  if (!map) return;

  // 이전 그룹 제거
  if (dongCircleGroup) { dongCircleGroup.remove(); dongCircleGroup = null; }
  if (!showDongCircle) return;

  const tr = cSlope ? AVG_TOBLER : 1.0;
  const radiusM = Math.round(SPEEDS[cB].speed * cT * 60 * tr);

  dongCircleGroup = L.layerGroup().addTo(map);

  Object.entries(DONG_META).forEach(([dc, meta]) => {
    const centroid = dongCentroids[dc];
    if (!centroid) return;
    const score = dongScore(dc);
    const col = scoreColor(score);
    const nYoung = getN('young', cT, cF, dc, cSlope);
    const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
    const impact = Math.round((Math.max(0, 100 - score) / 100) * meta.el);
    const slopeTip = cSlope ? `<br>경사 보정 (Tobler: ${AVG_TOBLER})` : '';

    // 점선 반경 원
    L.circle(centroid, {
      radius: radiusM,
      color: col,
      weight: 1.2,
      dashArray: '5,4',
      fillColor: col,
      fillOpacity: 0.06
    })
      .bindTooltip(
        `<b>${meta.fn}</b><br>` +
        `반경: ~${(radiusM / 1000).toFixed(2)} km<br>` +
        `도달가능점수: ${score.toFixed(1)}점<br>` +
        `일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>` +
        `영향 노인: 약 ${impact.toLocaleString()}명` +
        slopeTip
      )
      .addTo(dongCircleGroup);

    // 중심점 핀
    L.circleMarker(centroid, {
      radius: 3,
      color: col,
      weight: 1,
      fillColor: col,
      fillOpacity: 0.9
    }).addTo(dongCircleGroup);
  });
});
```

### Effect 5: 차트 갱신 (기존 유지)
```js
$effect(() => { void cB; void cT; void cF; void cSlope; /* 차트 update */ });
$effect(() => { void cTop; void cB; ...; if (ChartLib) buildTopChart(); });
```

---

## 6. `onDestroy` 변경

```js
onDestroy(() => {
  if (map) { try { map.remove(); } catch (e) {} }
  [scChart, gcChart, icChart].forEach((c) => c?.destroy?.());
});
```

---

## 7. 컨트롤 패널 HTML 변경

### 기존 "시설 레이어" crow 교체

**기존:**
```svelte
<div class="crow">
  <span class="lbl">시설 레이어</span>
  <button ... showHosp>병의원</button>
  <button ... showPharm>약국</button>
</div>
```

**변경 후:**
```svelte
<div class="crow">
  <span class="lbl">지도 레이어</span>
  <button type="button" class="chk-btn choropleth" class:on={showChoropleth}
          onclick={() => (showChoropleth = !showChoropleth)}>
    <span class="chk-dot" style="background:#fee08b"></span>점수 채색
  </button>
  <button type="button" class="chk-btn" class:on={showHosp}
          onclick={() => (showHosp = !showHosp)}>
    <span class="chk-dot" style="background:#f472b6"></span>병의원
  </button>
  <button type="button" class="chk-btn" class:on={showPharm}
          onclick={() => (showPharm = !showPharm)}>
    <span class="chk-dot" style="background:#10b981"></span>약국
  </button>
  <button type="button" class="chk-btn dong" class:on={showDongCircle}
          onclick={() => (showDongCircle = !showDongCircle)}>
    <span class="chk-dot" style="background:#ff6f00"></span>동 반경 원
  </button>
</div>
```

---

## 8. HTML 지도 섹션 변경

### mapEl2 → mapEl

```svelte
<!-- POI 지도: 병의원·약국 위치 + 도달가능점수 -->
<div class="mt-3.5">
  <Card title="병의원·약국 위치 및 의료 도달가능점수 (서울시)">
    <MapShell
      height="460px"
      legend={facilityLegend}
      source="병의원 {facilities.HOSP.length.toLocaleString()}개 · 약국 {facilities.PHARM.length.toLocaleString()}개"
    >
      <div bind:this={mapEl} class="absolute inset-0 h-full w-full"></div>
    </MapShell>
  </Card>
</div>
```

(`mapEl2` → `mapEl`로 변경, 제목 업데이트)

---

## 9. CSS 추가 (style 블록)

```css
/* 점수 채색 토글 버튼 ON 상태 */
.chk-btn.choropleth.on { background: #fce7f3; border-color: #f472b6; color: #9d174d; }

/* 동 반경 원 토글 버튼 ON 상태 (bokji에서 그대로) */
.chk-btn.dong.on { background: #fff4e5; border-color: #ff6f00; color: #c05000; }
```

---

## 10. facilityLegend 업데이트

범례에 choropleth 점수 색상 추가:

```js
const facilityLegend = [
  { color: '#1a9850', label: '90점+ (의료접근 양호)' },
  { color: '#fdae61', label: '50–70점 (보통)' },
  { color: '#d73027', label: '50점 미만 (취약)' },
  { color: '#f472b6', label: '의원' },
  { color: '#e11d48', label: '병원' },
  { color: '#7c3aed', label: '보건소' },
  { color: '#1d4ed8', label: '종합병원' },
  { color: '#10b981', label: '약국' }
];
```

---

## 11. 주석 처리된 choropleth 아카이브 정리

현재 `/* CHOROPLETH_MAP_ARCHIVED ... */` 블록에서 필요한 코드를 복원:
- `styleFeature(feat)` 함수 → 주석 해제하여 실제 함수로 복원
- `tooltipContent(feat)` 함수 → 주석 해제하여 실제 함수로 복원
- `let mapEl`, `let leafletMap`, `let geoLayer` 관련 변수 → 삭제 (새 이름으로 대체)

복원할 함수들:
```js
function styleFeature(feat) {
  return {
    fillColor: scoreColor(dongScore(feat.properties.dc)),
    color: 'rgba(80,80,80,0.25)',
    weight: 0.5,
    fillOpacity: 0.72   // 0.82 → 0.72로 약간 줄여서 POI 마커 가시성 확보
  };
}

function tooltipContent(feat) {
  const dc = feat.properties.dc;
  const m = DONG_META[dc];
  if (!m) return '';
  const nYoung = getN('young', cT, cF, dc, cSlope);
  const nB = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
  const score = nYoung > 0 ? (nB / nYoung) * 100 : 100;
  const impact = Math.round((Math.max(0, 100 - score) / 100) * m.el);
  return (
    `<b>${m.fn}</b><br>` +
    `도달가능점수: <b>${score.toFixed(1)}점</b><br>` +
    `일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>` +
    `영향 노인 수: 약 ${impact.toLocaleString()}명`
  );
}
```

---

## 12. 실행 체크리스트

실제 코딩 시 순서:

1. `let mapEl2 = $state()` → `let mapEl = $state()` rename
2. `let facilityMap = null` → `let map = null` rename
3. `const HOSP_COLOR` 이하 이미 있음 — 유지
4. `function polygonCentroid(geometry)` + `const dongCentroids` 추가 (module scope)
5. `function styleFeature(feat)` + `function tooltipContent(feat)` 복원 (주석 해제 후 정리)
6. `onMount` 재작성 (Section 4 그대로)
7. `onDestroy` 변경 (map → facilityMap 삭제)
8. `$effect` × 4개 재작성 (Section 5 그대로)
9. `let showChoropleth`, `let showDongCircle` 상태 추가
10. 컨트롤 패널 HTML 변경 (Section 7)
11. 지도 div `mapEl2` → `mapEl` rename (HTML)
12. CSS `.chk-btn.choropleth.on`, `.chk-btn.dong.on` 추가
13. `facilityLegend` 업데이트 (Section 10)
14. 아카이브 주석 블록 삭제 (Section 11 완료 후)

---

## 13. 엣지 케이스 & 주의사항

### Choropleth + POI 마커 레이어 순서
- Leaflet은 나중에 addTo한 레이어가 위에 렌더링됨
- 순서: geoLayer → hospGroup → pharmGroup → dongCircleGroup
- POI 마커가 choropleth 위에 표시되어야 하므로 geoLayer를 먼저 초기화 ✅

### dongCircleGroup $effect에서 `dongScore(dc)` 호출
- `dongScore(dc)`는 `cB`, `cT`, `cF`, `cSlope`에 의존
- `$effect` 의존성에 `void cB; void cT; ...` 명시적으로 추가해야 Svelte가 추적 가능
- `DONG_META`를 `Object.entries()` 순회 시 426개 × L.circle/circleMarker = ~852 DOM 요소 — 허용 범위

### Choropleth fillOpacity 조정
- 기존 archived 코드는 0.82 — POI 마커가 그 위에 표시되므로 0.72로 낮춤
- 동 반경 원 fillOpacity는 0.06 (bokji와 동일) — 배경 가시성 확보

### HOSP_COLOR 타입 경고
- 이미 `/** @type {Record<string, string>} */` JSDoc 추가되어 있음 — 유지

### MultiPolygon 대응
- `polygonCentroid(geometry)` 에서 `MultiPolygon` 분기 처리 필수
- 서울 행정동 중 도서 지역(노원구 일부 등)이 MultiPolygon일 수 있음

### 변수 이름 충돌
- `map`이라는 이름은 JS 내장 `Array.prototype.map`과 다른 스코프이므로 무방
- 단, `map.remove()` 같은 호출이 `Map` 객체와 혼동되지 않도록 주의
- 필요 시 `leafMap` 또는 `lmap`으로 명명 가능

---

## 14. 완성 후 시각적 결과 예상

```
[지도 레이어] [점수 채색 ON] [병의원 ON] [약국 ON] [동 반경 원 OFF]
                     ↑
             컨트롤 패널 crow

지도:
- 행정동 polygon이 도달가능점수로 색칠 (초록/노랑/빨강 그라데이션)
- 그 위에 병의원(핑크/로즈/바이올렛/블루) + 약국(에메랄드) 점들
- "동 반경 원" 켜면 각 동 중심에서 점선 원 426개 + 중심 핀 표시
- Tooltip: 동 이름 + 점수 + 영향 노인 수
```
