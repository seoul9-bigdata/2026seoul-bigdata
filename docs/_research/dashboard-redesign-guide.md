# 대시보드 디자인 통일 작업 가이드

> **목적**: `bokji` 대시보드에 적용한 디자인 개선 방법론을 정리.  
> 다음 작업 세션에서 `medical` 대시보드에 같은 방식을 적용할 때 참조.

---

## 1. 디자인 기준 (Reference)

**기준 파일**: `svelte_output/src/lib/components/climate/ShelterTab.svelte`  
**완성 예시**: `svelte_output/src/routes/bokji/+page.svelte`  
**작업 대상**: `svelte_output/src/routes/medical/+page.svelte`

---

## 2. 버튼 CSS 통일

### 변경 전 (medical 현재 상태)
```svelte
<!-- PillButton 컴포넌트 사용 -->
<PillButton variant="wide" active={cB === c.idx} onclick={() => (cB = c.idx)}>
  {c.emoji} {c.text}
</PillButton>

<!-- .topbtn 커스텀 버튼 -->
<button class="topbtn" class:on={cTop === 'impact'}>영향 노인 수 TOP 10동</button>
```

### 변경 후 (bokji 패턴)
```svelte
<!-- 일반 토글 버튼 -->
<button type="button" class="btn bw" class:on={cB === c.idx} onclick={() => (cB = c.idx)}>
  {c.emoji} {c.text}
</button>

<!-- 체크형 버튼 (경사보정 등 on/off 토글) -->
<button type="button" class="chk-btn slope" class:on={cSlope} onclick={() => (cSlope = !cSlope)}>
  <span class="chk-dot" style="background:#8B5CF6"></span>경사로 보정
</button>
```

### 추가할 CSS (의료 accent = `--color-pink` = `#f472b6`)
```css
.btn {
  font-size: 12px; padding: 5px 14px; border-radius: 20px;
  border: 0.5px solid var(--color-text4); background: transparent;
  color: var(--color-text2); cursor: pointer; transition: all 0.14s;
  font-family: inherit; white-space: nowrap;
}
.btn:hover { border-color: var(--color-text2); color: var(--color-text); }
.btn.on {
  background: var(--pill-accent, var(--color-dark));
  color: var(--pill-on-text, var(--color-dark-text));
  border-color: var(--pill-accent, var(--color-dark));
}
.btn.on:hover { filter: brightness(1.08); }
.btn.bw { border-radius: 8px; }

.chk-btn {
  font-size: 12px; padding: 5px 13px; border-radius: 20px;
  border: 0.5px solid var(--color-text4); background: transparent;
  color: var(--color-text2); cursor: pointer; transition: all 0.14s;
  font-family: inherit; white-space: nowrap; display: flex; align-items: center; gap: 5px;
}
.chk-btn:hover { border-color: var(--color-text2); color: var(--color-text); }
.chk-btn.slope.on { background: #f0eafd; border-color: #8b5cf6; color: #5b21b6; }
.chk-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
```

### 제거할 CSS
```css
/* 삭제 대상 */
.topbtn { ... }
.topbtn:hover { ... }
.topbtn.on { ... }
/* PillButton import도 제거 */
```

---

## 3. 컨트롤 패널 구조

### 변경 전 (medical)
```svelte
<Card class="mb-3.5">
  <div class="flex flex-wrap items-center gap-2 mb-2.5">
    <span class="ct-label" style:width="72px">비교 속도</span>
    {#each compareLabels as c}
      <PillButton ...>{c.emoji} {c.text}</PillButton>
    {/each}
  </div>
  ...
</Card>
```

### 변경 후 (bokji 패턴)
```svelte
<div class="ctrl">
  <div class="crow">
    <span class="lbl">비교 속도</span>
    {#each compareLabels as c (c.idx)}
      <button type="button" class="btn bw" class:on={cB === c.idx} onclick={() => (cB = c.idx)}>
        {c.emoji} {c.text} &nbsp;{c.speed}
      </button>
    {/each}
  </div>
  <div class="crow">
    <span class="lbl">경사 보정</span>
    <button type="button" class="chk-btn slope" class:on={cSlope} onclick={() => (cSlope = !cSlope)}>
      <span class="chk-dot" style="background:#8B5CF6"></span>경사로 보정 (Tobler · NASA SRTM)
    </button>
  </div>
  <div class="crow">
    <span class="lbl">보행 시간</span>
    {#each [15, 30, 45] as t (t)}
      <button type="button" class="btn" class:on={cT === t} onclick={() => (cT = t)}>{t}분</button>
    {/each}
    <span class="lbl" style="margin-left:12px">시설 유형</span>
    {#each [{v:'all',l:'전체'},{v:'hosp',l:'병의원'},{v:'pharm',l:'약국'}] as f (f.v)}
      <button type="button" class="btn" class:on={cF === f.v} onclick={() => (cF = f.v)}>{f.l}</button>
    {/each}
  </div>
  <!-- 통계 카드는 ctrl 내부에 유지 -->
</div>
```

```css
.ctrl {
  background: var(--color-card); border: 0.5px solid var(--color-border);
  border-radius: 12px; padding: 16px 20px; margin-bottom: 14px;
}
.crow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.crow:last-child { margin-bottom: 0; }
.lbl {
  font-size: 11px; font-weight: 500; letter-spacing: 0.06em;
  color: var(--color-text3); white-space: nowrap; margin-right: 2px;
}
```

---

## 4. 레이아웃 그리드

### 현재 medical 레이아웃
```svelte
<!-- 지도 + 산점도: 인라인 grid style -->
<div class="grid gap-3.5 mb-3.5" style:grid-template-columns="1.45fr 1fr">
  <Card>지도</Card>
  <Card>산점도(scChart)</Card>
</div>
<!-- 구별 차트 + top 차트 -->
<div class="grid gap-3.5 mb-3.5" style:grid-template-columns="1fr 1fr">
  <Card>gcChart (560px)</Card>
  <Card>icChart (520px)</Card>
</div>
```

### 변경 후 (bokji 패턴 — CSS 클래스 사용)
```svelte
<!-- 지도 단독 full-width -->
<div class="mt-3.5">
  <Card title="...">지도</Card>
</div>

<!-- 차트 2열 -->
<div class="r2b mt-3.5">
  <Card>gcChart</Card>
  <Card>icChart (top)</Card>
</div>
```

```css
.r2b { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 900px) { .r2b { grid-template-columns: 1fr; } }
```

> **참고**: bokji에는 추가로 `.r3` (3열 신규 차트 섹션)도 있음.  
> medical에서도 비슷한 시각화 확장을 원하면 동일하게 추가 가능.

---

## 5. 테이블 (ktbl 스타일)

### 변경 전 (medical)
```svelte
<div class="overflow-x-auto overflow-y-auto" style:max-height="360px">
  <table class="w-full border-collapse text-[12px]">
    <thead>
      <tr>
        <th>행정동</th>
        <th>도달가능점수</th>
        ...
      </tr>
    </thead>
```
```css
/* th/td 전역 스타일 */
th { padding: 6px 10px; text-align: left; ... }
td { padding: 7px 10px; border-bottom: 0.5px solid #f1efe8; }
```

### 변경 후 (ktbl 패턴)
```svelte
<div class="tbl-wrap">
  <table class="ktbl">
    <thead>
      <tr>
        <th>행정동</th>
        <th>도달가능점수</th>
        ...
        <th>등급</th>   <!-- 마지막은 center -->
      </tr>
    </thead>
    <tbody>
      {#each tableRows as r (r.dc)}
        <tr>
          <td>{r.fn}</td>
          <td>
            <b style="color:{scoreColor(r.score)}">{r.score.toFixed(1)}점</b>
            <span class="score-bar" style={scoreBarStyle(r.score)}></span>
          </td>
          ...
          <td><span class="pill {gradePillClass(r.score)}">{gradeText(r.score)}</span></td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
```

```css
.tbl-wrap { overflow-x: auto; }   /* max-height 제거 — 스크롤 없이 전체 표시 */
.ktbl { width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; }
.ktbl th {
  background: var(--color-card-soft); padding: 8px 10px; text-align: right;
  font-weight: 500; color: var(--color-text2); border-bottom: 1px solid var(--color-border);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ktbl th:first-child { text-align: left; width: 88px; }
.ktbl th:last-child { text-align: center; }
.ktbl td {
  padding: 7px 10px; border-bottom: 0.5px solid var(--color-border-soft);
  color: var(--color-text); text-align: right; white-space: nowrap; overflow: hidden;
}
.ktbl td:first-child { text-align: left; }
.ktbl td:last-child { text-align: center; }
.ktbl tr:hover td { background: #fafaf8; }
.score-bar { display: inline-block; height: 5px; border-radius: 3px; vertical-align: middle; margin-left: 4px; }
```

### 헬퍼 함수 추가
```js
function gradePillClass(sc) {
  if (sc == null) return 'pna';
  if (sc >= 90) return 'phi';
  if (sc >= 60) return 'pmd';
  return 'plo';
}
function gradeText(sc) {
  if (sc == null) return '-';
  if (sc >= 90) return '양호';
  if (sc >= 60) return '보통';
  return '미흡';
}
function scoreBarStyle(sc) {
  if (sc == null) return 'display:none';
  // medical scoreColor 기준 — 70점 이상 녹색, 50~70 노란, 미만 빨강
  const col = sc >= 70 ? '#2E7D32' : sc >= 50 ? '#F57F17' : '#C62828';
  const w = Math.round((sc * 40) / 100);
  return `background:${col};width:${w}px`;
}
```

### 필 색상 (medical 기준 — bokji와 동일)
```css
.pill { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
.phi { background: #d4edda; color: #155724; }
.pmd { background: #fff3cd; color: #856404; }
.plo { background: #f8d7da; color: #721c24; }
.pna { background: #ebebeb; color: #666; }
```

> **주의**: medical의 기존 `.phi/.pmd/.plo` 색상이 bokji와 약간 다름(`.phi`가 녹-청). 위 값으로 통일.

---

## 6. Chart.js 패턴

### ChartCard 컴포넌트 사용 (bokji 방식)
```svelte
<!-- 변경 전: Card 내부에 canvas 직접 -->
<Card title="구별 평균 의료 도달가능점수">
  <div class="relative w-full" style:height="560px">
    <canvas bind:this={gcCanvas} class="block h-full w-full"></canvas>
  </div>
</Card>

<!-- 변경 후: ChartCard 컴포넌트 -->
<ChartCard title="구별 평균 의료 도달가능점수" height="560px" onmount={setupGcChart} />
```

ChartCard를 쓰면 `bind:this` + canvas 직접 관리가 불필요해짐.  
단, `initCharts()` 구조를 `setup*Chart(canvas)` 패턴으로 분리해야 함:
```js
async function setupGcChart(canvas) {
  const C = await ensureChart();
  gcChart = new C(canvas, { ... });
  updateGcChart();
}
function updateGcChart() { if (!gcChart) return; ... gcChart.update('none'); }
```

### 막대 그래프 whitespace 줄이기
```js
datasets: [{
  data: ...,
  backgroundColor: ...,
  borderRadius: 3,
  minBarLength: 4,      // 0값 막대도 최소 4px 표시
  barPercentage: 0.9,   // 막대 두께 확장
  categoryPercentage: 0.92
}]
```

### 수평 막대 (indexAxis: 'y') layout 패딩 축소
```js
options: {
  layout: { padding: { top: 2, bottom: 2, right: 10 } },
  ...
}
```

---

## 7. medical 전용 고려사항

### 유지해야 할 기능
- `distBars` 보행 가능 거리 비교 막대 UI — 고유 기능, 유지
- `scChart` 산점도 (일반인 vs 비교속도) — 유지, 스타일만 정리
- `buildTopChart` / icChart — 유지, 버튼만 `.topbtn` → `.btn`으로 교체
- GeoJSON choropleth 지도 — 유지

### 변경할 항목 요약
| 항목 | 현재 | 변경 후 |
|---|---|---|
| 컨트롤 컴포넌트 | `<Card>` + `PillButton` | `.ctrl` + `.btn`/`.chk-btn` |
| `.topbtn` | 커스텀 | `.btn.bw` 스타일로 교체 |
| 테이블 | `th`/`td` 전역 CSS | `.ktbl` 클래스 |
| 테이블 스크롤 | `max-height: 360px` | 스크롤 제거, 전체 표시 |
| 점수 셀 | `<b>점수</b>` 만 | `<b>점수</b> + score-bar` |
| 등급 셀 | `.pill plo/pmd/phi` (색다름) | bokji 기준 색으로 통일 |
| 그리드 | `style:grid-template-columns` 인라인 | `.r2b` CSS 클래스 |
| `PillButton` import | 있음 | 제거 |
| `KickerLabel` import | 있음 | 유지 (bokji는 직접 구현, medical은 컴포넌트 써도 무방) |

### medical의 도달가능점수 기준
bokji와 달리 medical은 **100점 초과가 없음** (분모=일반인 도달 수, 분자≤분모 구조).  
그러나 `dongScore` 로직에서 `nYoung === 0`이면 100점 반환 — score-bar 최대값은 100으로 고정.

---

## 8. 작업 순서 (추천)

1. `import PillButton` 제거, `import ChartCard` 추가
2. `<style>` — 기존 `th`/`td`/`.topbtn`/`.pill` 제거, 새 CSS 블록 추가
3. 컨트롤 패널 HTML — `<Card>` → `.ctrl` + `.crow` 구조로 재작성
4. 지도 섹션 — 인라인 grid → 단독 full-width div
5. 차트 카드 — `<Card>` + 직접 canvas → `<ChartCard>` (또는 유지하고 스타일만 정리)
6. 차트 JS 코드 — `initCharts()` → `setup*Chart(canvas)` 패턴 분리
7. 테이블 HTML — `table` → `.ktbl`, score-bar·pill 추가
8. 헬퍼 함수 — `gradePillClass`, `gradeText`, `scoreBarStyle` 추가

---

## 9. 공통 컴포넌트 위치

| 컴포넌트 | 경로 |
|---|---|
| `ChartCard` | `src/lib/components/ChartCard.svelte` |
| `Card` | `src/lib/components/Card.svelte` |
| `MapShell` | `src/lib/components/MapShell.svelte` |
| `StatGrid` / `StatCard` | `src/lib/components/Stat*.svelte` |
| `Note` | `src/lib/components/Note.svelte` |

**`ChartCard` props**: `title: string`, `height: string`, `onmount: (canvas) => void`
