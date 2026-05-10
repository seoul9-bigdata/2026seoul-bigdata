# 절반의 서울 — 대시보드 스타일 가이드

> 메인 페이지(`+page.svelte`) 리뉴얼을 기준으로 작성.  
> 나머지 5개 도메인 대시보드를 수정할 때 이 가이드를 따른다.

---

## 1. 폰트 시스템

### 적용 완료 (`app.html` + `layout.css`)

| 역할        | 폰트               | CSS 변수         | 비고                          |
| ----------- | ------------------ | ---------------- | ----------------------------- |
| 본문 전체   | **Gothic A1**      | `--font-sans`    | Google Fonts, weight 100–700  |
| 제목·헤더   | **Black Han Sans** | `--font-display` | Google Fonts, weight 900 단일 |
| 세리프 강조 | Noto Serif KR      | `--font-serif`   | 유지 (필요 시 사용)           |
| 숫자·코드   | IBM Plex Mono      | `--font-mono`    | 유지                          |

### 각 도메인 대시보드에서 확인할 것

- 인라인 `font-family: "Noto Sans KR"` 하드코딩 → `var(--font-sans)` 또는 `inherit`으로 교체
- Chart.js `fontFamily` 설정 → `"Gothic A1"` 또는 `var(--font-sans)` 참조
- 섹션 제목(`<h2>`, `.section-title` 등)에 `font-family: var(--font-serif)` 남아 있으면 → `var(--font-sans)`로 통일
- **단, 메인 히어로 제목 한 줄짜리 강조 문구**는 `var(--font-display)` (Black Han Sans) 사용 가능

### Font-weight 매핑

Black Han Sans는 weight가 900 하나뿐이므로 `font-weight` 유틸리티를 추가로 쓸 필요 없음.  
Gothic A1은 100~700 모두 지원 — 기존 `font-light`, `font-medium`, `font-semibold` 클래스 그대로 동작.

---

## 2. 컬러 시스템

### 글자 색 사용 원칙

| 대상                             | 색 변수          | hex       |
| -------------------------------- | ---------------- | --------- |
| 건강 노인 관련 수치·키워드       | `--color-blue`   | `#5aadff` |
| 보행보조기 노인 관련 수치·키워드 | `--color-accent` | `#d85a30` |
| 강조 수치 (일반)                 | `--color-accent` | `#d85a30` |
| 보조 텍스트                      | `--color-text2`  | `#5f5e5a` |
| 라벨·메타                        | `--color-text3`  | `#888780` |

### 도메인 액센트 색

| 도메인    | 변수             | hex       |
| --------- | ---------------- | --------- |
| 교통      | `--color-blue`   | `#5aadff` |
| 기후      | `--color-amber`  | `#f5b740` |
| 인프라    | `--color-teal`   | `#3ecfa0` |
| 복지/녹지 | `--color-purple` | `#b48ef4` |
| 의료      | `--color-pink`   | `#f472b6` |

### 컬러 강조 패턴 (본문 텍스트)

핵심 수치나 대비되는 키워드는 `<span>` 으로 감싸 색 구분:

```svelte
건강한 노인(<span class="font-medium" style:color="var(--color-blue)">1.12&nbsp;m/s</span>)은
청년 도달 구역의 <span class="font-semibold" style:color="var(--color-blue)">76.7%</span>를,
보행보조기를 사용하는 노인(<span class="font-medium" style:color="var(--color-accent)">0.88&nbsp;m/s</span>)은
<span class="font-semibold" style:color="var(--color-accent)">46.9%</span>를 이동할 수 있습니다.
```

---

## 3. 어휘 통일표

반드시 아래 표현으로 통일한다.

| 이전 표현                              | 교체 표현                                                                                    |
| -------------------------------------- | -------------------------------------------------------------------------------------------- |
| 일반 노인                              | **건강 노인**                                                                                |
| 보행보조 노인 / 보행보조기를 쓰는 노인 | **보행보조 노인** / **보행보조기를 사용하는 노인**                                           |
| 5축                                    | **교통 심층 분석 1축 + 기후·인프라·복지·의료 도달 분석 4축** (문맥에 따라 "1+4축" 단축 가능) |
| Seoul Elder Mobility                   | **Seoul Elder Walkability**                                                                  |
| 분(分)의 격차                          | **절반의 서울** (프로젝트 공식 제목)                                                         |
| 복지                                   | **복지/녹지**                                                                                |
| 1차 진료·응급 도달 시간                | **병의원·약국 접근성**                                                                       |
| 폭염·한파쉼터 접근성                   | **폭염쉼터·한파쉼터·결빙위험구역**                                                           |

---

## 4. 도메인 메타데이터 (theme.js 기준)

```js
// src/lib/theme.js — DOMAIN_THEME 최신 상태
transit:  { label: '교통·이동',  emoji: '🚇', author: '유호준' }
climate:  { label: '기후',       emoji: '🌡️', author: '김성령' }
infra:    { label: '인프라',     emoji: '🏪', author: '심재현' }
bokji:    { label: '복지/녹지', emoji: '🌳', author: '양석준' }
medical:  { label: '의료',       emoji: '🏥', author: '이정태' }
```

---

## 5. 글쓰기 톤 & 스타일

### 원칙

- **따뜻하고 사실적으로** — 시니컬하거나 비판적인 어조 지양
- **~습니다 체** — 공식 발표 자료 느낌
- **데이터 → 해석 → 맥락** 순서로 서술
- 감탄사·수사적 강조보다 **수치로 말하게** 한다

### 피해야 할 표현

| 피할 표현                       | 대신 사용                                       |
| ------------------------------- | ----------------------------------------------- |
| "고작 X%"                       | "X%를 이동할 수 있습니다"                       |
| "그러나 그 30분은…" (역접 강조) | "그 기준은 청장년의 걸음으로 설계되어 있습니다" |
| "~의 시간이다" (단정)           | "~의 걸음으로 설계되어 있습니다"                |
| "진단한다"                      | "들여다봅니다" / "살펴봅니다"                   |

### 본문 구조 패턴

```
[배경 한 문장] — 서울시의 비전/정책 언급
[문제 정의] — 청장년 기준으로 설계됨을 수치와 함께 제시
[데이터 대비] — 건강 노인 vs 보행보조기 노인 수치 나열 (색 강조)
[전환] — 이 대시보드가 무엇을 다루는지 1축+4축 언급
```

---

## 6. 핵심 수치 (Hero Stat)

메인 페이지 기준. 각 도메인 대시보드의 Hero 수치 카드에도 동일 원칙 적용.

| 항목                        | 건강 노인       | 보행보조기 노인             | 색            |
| --------------------------- | --------------- | --------------------------- | ------------- |
| 보행속도                    | 1.12 m/s        | 0.88 m/s                    | blue / accent |
| 도달 구역 (일반인=100 기준) | 76.7개          | 46.9개                      | blue / accent |
| 서울 고령화율               | 20.7% (2026)    | 29.1% (2040)                | text / accent |
| 분석 구조                   | 1축 (교통 심층) | 4축 (기후·인프라·복지·의료) | blue / accent |

**Dual stat 렌더링 패턴** — 두 수치를 위아래로 쌓고, 상단에 소제목 헤더, 각 수치 아래에 라벨:

```svelte
{#each s.dual as d, j}
  <div class="font-mono text-[20px] sm:text-[22px]" style:color={d.color}>
    <CountUp value={d.num} decimals={d.decimals} ... />
    <span style:color={d.color} style:opacity="0.75">{d.unit}</span>
  </div>
  <div class="text-[10px]" style:color={d.color} style:opacity={j===0 ? '0.55' : '0.75'}>
    {d.label}
  </div>
{/each}
```

---

## 7. 레이아웃 & 여백

- `<main>` 에 `min-h` **금지** — 콘텐츠가 짧은 페이지에서 Footer가 멀어짐
- `<footer>` `margin-top: 12px` (60px → 12px 변경 완료)
- 섹션 하단 패딩: `pb-[16px]` (도메인 대시보드는 콘텐츠가 길어서 크게 문제 없음)

---

## 8. 컴포넌트별 폰트 적용 체크리스트

각 도메인 대시보드 수정 시 아래를 확인:

- [ ] `font-family: "Noto Sans KR"` 하드코딩 → `var(--font-sans)` 또는 `inherit`
- [ ] Chart.js `CHART_THEME.fontFamily` → `"Gothic A1"` (theme.js에서 전역 수정 완료)
- [ ] Leaflet 툴팁 인라인 스타일 `font-family:inherit` → 유지 (이미 올바름)
- [ ] 섹션 제목에 `font-serif` 남아있으면 → `font-sans`로 교체
- [ ] Hero 강조 제목(한 줄) → `style:font-family="var(--font-display)"` 적용 가능
- [ ] `font-weight: 600` + Black Han Sans 조합 → weight 제거 (900 단일이라 무의미)
- [ ] 도메인 author 이름 → theme.js 기준 full name 사용 (위 §4 참조)

---

## 9. 도메인 대시보드 추가 수정 기준 (2026-05-10 업데이트)

> §1–8은 메인/introduce/conclusion 기준. 아래는 각 도메인 분석 대시보드에 적용한 추가 패턴.

---

### 9-1. 건강 노인 색상 보정

스타일 가이드 §2에서 건강 노인 = `--color-blue` (`#5aadff`)로 정의했으나,  
**일반인(`#4a9eff`)과 시각적으로 구분이 안 됨** → 초록 계열로 변경.

| 대상           | 변경 전                                                           | 변경 후                        |
| -------------- | ----------------------------------------------------------------- | ------------------------------ |
| 건강 노인 색상 | `#5aadff` / `#1D9E75`                                             | **`#3ecfa0`** (`--color-teal`) |
| 적용 범위      | introduce SPEEDS, conclusion speedComparison, climate.json SPEEDS | 동일                           |

`climate.json` SPEEDS 배열도 업데이트 완료 (`g1.color`).

---

### 9-2. 도메인 히어로 섹션 패턴 (기후 기준 → 전체 도메인 준용)

기존 히어로는 다크 배경 + 작은 텍스트만 있었음. 기후 대시보드 기준으로 개선된 패턴:

```svelte
<section class="climate-hero">
  <div class="hero-glow"></div>  <!-- 도메인 액센트 색 radial-gradient -->
  <div class="climate-hero-inner">
    <div class="hero-text">
      <p class="hero-kicker">② 기후 · 김성령</p>  <!-- 번호 · 작성자 -->
      <h1 class="hero-title">
        노인 <em>기후안전권</em> 분석   <!-- em = 도메인 액센트 색 -->
      </h1>
      <div class="hero-chips">
        <span class="chip amber">☀️ 데이터소스 N개</span>
        <span class="chip muted">메타 정보</span>
      </div>
    </div>
  </div>
</section>
```

**히어로 구성 규칙:**

| 요소      | 규칙                                                         |
| --------- | ------------------------------------------------------------ |
| kicker    | `② 도메인명 · 작성자명` (번호는 아래 §9-3 참조)              |
| h1 폰트   | `font-family: var(--font-display)` (Black Han Sans)          |
| h1 강조어 | `<em style="color: var(--color-도메인액센트)">`              |
| 배경 glow | `radial-gradient` — 도메인 액센트색 18% opacity, 우상단 고정 |
| data chip | 데이터 소스·규모를 색 chip으로 표시 (아래 §9-4)              |

---

### 9-3. 도메인 번호 체계

| 도메인            | 번호 |
| ----------------- | ---- |
| transit (교통)    | ①    |
| climate (기후)    | ②    |
| infra (인프라)    | ③    |
| bokji (복지/녹지) | ④    |
| medical (의료)    | ⑤    |

---

### 9-4. 데이터 소스 Chip 패턴

히어로 하단에 데이터 소스·규모를 색 chip으로 표시. 도메인 탭 색과 연동:

```css
.chip {
  background: rgba(255, 255, 255, 0.07);
  color: rgba(241, 239, 232, 0.65);
}
.chip.amber {
  background: rgba(245, 183, 64, 0.15);
  color: #f5b740;
  border: 0.5px solid rgba(245, 183, 64, 0.3);
}
.chip.blue {
  background: rgba(74, 144, 217, 0.15);
  color: #82bcf0;
  border: 0.5px solid rgba(74, 144, 217, 0.3);
}
.chip.ice {
  background: rgba(0, 229, 255, 0.1);
  color: #7fecff;
  border: 0.5px solid rgba(0, 229, 255, 0.25);
}
.chip.muted {
  background: transparent;
  color: rgba(241, 239, 232, 0.35);
}
.chip-sep {
  color: rgba(241, 239, 232, 0.25);
}
```

주요 데이터(시설 수·규모)는 색 chip, 출처·날짜 등 메타는 `.chip.muted` 처리.

---

### 9-6. 기타 수정 사항

| 항목                   | 내용                                                         |
| ---------------------- | ------------------------------------------------------------ |
| Footer 프로젝트명      | `분(分)의 격차` → **`절반의 서울`**                          |
| 결론 Card 제목         | `결론 · 분(分)의 격차` → **`결론 · 절반의 서울`**            |
| climate.json SPEEDS g1 | label `일반 노인` → `건강 노인`, color `#185FA5` → `#3ecfa0` |
