# TODO

전수 점검 (2026-05-11) 기반 작업 목록. 5월 13일 마감.

## ✅ 진행 상황 (2026-05-12 업데이트)

**완료**: G1, G2, G3, G4, G5, G6, G7, G8 (Phase 1+2+3 + anchors 빈값 fill + ODTab 전체 유지+강조), G10, G12, G13

**미완료**: G9 (복지 도로망), G11 (제설함 OFF 브라우저 디버그)

## 🟢 빠른 수정 (각 5~15분)

### G1. 디폴트 값 통일
- [ ] `src/routes/infra/+page.svelte:23` — `cT = $state(15)` → `30`
- [ ] `src/routes/infra/+page.svelte:24` — `cG = $state('중구')` → `'종로구'`
- [ ] 기준 자치구 = `종로구` (법정동 1111000000) 전 페이지 통일 확인

### G2. "건강 노인" → "일반 노인" 라벨 통일
theme.js (`WALK_TYPES`) 가 "일반 노인" 이므로 다른 곳을 맞춤.
- [ ] `src/routes/+page.svelte:25, 38`
- [ ] `src/routes/+page.svelte:107, 123` 본문 텍스트 ("건강한 노인")
- [ ] `src/routes/introduce/+page.svelte:139`
- [ ] `src/routes/conclusion/+page.svelte:34, 118, 345, 367, 624, 699`
- [ ] `src/routes/medical/+page.svelte:736`
- [ ] `src/routes/infra/+page.svelte:1046`
- [ ] `src/lib/components/climate/ShelterTab.svelte:925`
- [ ] `src/lib/data/climate.json:189` — JSON 재생성 필요할 수 있음 (파이프라인 확인)

### G3. 기후 "접근성" → "도달가능" 라벨 통일
- [ ] `ShelterTab.svelte:1010` "더위쉼터 접근성" → "더위쉼터 도달가능"
- [ ] `ShelterTab.svelte:1017` "한파쉼터 접근성" → "한파쉼터 도달가능"
- [ ] `ShelterTab.svelte:1023, 1083, 1089` "합산 접근성 점수" → "합산 도달가능 점수"
- [ ] `ShelterTab.svelte:831` 차트 축 "접근성 점수 (0-100)" → "도달가능 점수 (0-100)"

### G4. 기후 점수 글씨 크기 통일
inline `style:font-size=` 제거 → `.sv { font-size: 22px }` 일관 (의료와 동일).
- [ ] `ShelterTab.svelte:1024` `style:font-size="28px"` 제거
- [ ] `ShelterTab.svelte:1046` `style:font-size="18px"` 제거
- [ ] `ShelterTab.svelte:1065` `style:font-size="18px"` 제거

### G5. 거점 시설 ON/OFF 가시성 개선
- [ ] `src/lib/components/transit/AnchorTab.svelte:195-198` — `.chk-btn.on`
  - 현재 `background: var(--color-bg2)` (#f9f8f4) ≒ 페이지 bg (#f5f4f0) 라 변별 안 됨
  - → `var(--pill-accent)` (transit blue) 또는 진한 액센트로 변경, 텍스트 색도 대비 색으로

---

## 🟡 중간 (각 30분~1시간)

### G6. 헤더 클릭 정렬 패턴 — 모든 표 통일
기준 구현: `src/routes/infra/+page.svelte`
- `:29-30` `sortKey` / `sortDir` state
- `:623-634` `setSort()` 함수 (같은 컬럼 = asc↔desc 토글, 다른 컬럼 = 새 정렬 + 디폴트 desc)
- `:1001-1006` `<th class="th-sort" onclick={setSort(col.k)}>` + `▼/▲` 화살표
- `:1247` `.th-sort` CSS

공통 유틸로 추출: **`src/lib/util/tableSort.js`** (createSorter helper).

적용 대상 6개 표:
- [ ] `src/routes/conclusion/+page.svelte:625-661` — 별도 정렬 버튼 6개 제거 후 헤더 클릭으로 통합
- [ ] `src/routes/infra/+page.svelte:957-995` — 자치구 표 (현재 미적용)
- [ ] `src/routes/bokji/+page.svelte:925-940`
- [ ] `src/routes/medical/+page.svelte:992-1002`
- [ ] `src/lib/components/climate/ShelterTab.svelte:1172-1180`
- [ ] `src/lib/components/climate/IceTab.svelte:461-467`

### G7. 막대 디자인 통일
- [ ] `src/lib/theme.js` 에 `BAR_STYLES` 토큰 추가
  ```js
  BAR_STYLES = {
    height: { thin: 5, medium: 8, thick: 12, fat: 18 },
    radius: 3 // 'rounded-full' 금지, 항상 3px
  }
  ```
- [ ] `conclusion/+page.svelte:531` `domain-bar` → `rounded-full` 제거, `rounded-[3px]`
- [ ] 결론 페이지 내 3종 (`bar-fill 18px / 랭킹 12px / domain-bar 8px`) — 의도된 위계면 유지, radius 만 통일
- [ ] `src/routes/infra/+page.svelte:1248` `.score-bar { height: 8px }` → `5px` (다른 페이지와 통일)

---

## 🔴 큰 작업 (각 2~4시간)

### G8. 교통 구단위 필터
- [ ] `src/routes/transit/+page.svelte` 에 `cG` state + dropdown/pill 추가 (헤더 영역)
- [ ] 5탭 컴포넌트에 `cG` prop 전달
  - [ ] `src/lib/components/transit/ConstellationTab.svelte`
  - [ ] `src/lib/components/transit/HeatTab.svelte`
  - [ ] `src/lib/components/transit/AnchorTab.svelte`
  - [ ] `src/lib/components/transit/CrosswalkTab.svelte`
  - [ ] `src/lib/components/transit/ODTab.svelte`
- [ ] 각 탭에서 데이터(`stations`, `anchors`, `od_stations` 등) 를 `cG` 기준 필터링
- [ ] 지도 자동 줌·팬 to 선택 구

### G9. 복지 도로망 기반 도달 범위
- [ ] **G10 (집계 원칙) 확정 후 진행**
- [ ] `src/routes/bokji/+page.svelte:190-221` `L.circle` 직선 반경 → `$lib/util/isochrone.js` (`loadGraph + computeIsochrone`) 로 교체
- [ ] 인프라처럼 지도 클릭 핸들러 + Convex Hull 폴리곤 + 점선 원(참고용)
- [ ] 보행자/시간/경사 토글 변경 시 재계산 (인프라 패턴 그대로)

---

## ❓ 사용자 결정·추가 정보 필요

### G10. 동평균 vs 구단위 집계 — 원칙 확정
- 복지 `bokji/+page.svelte:102-115` 현재 = 동들 평균 → 구로 집계
- 사용자 가이드: *"구단위 집계가 원칙, 데이터가 구단위인 경우에만 부득이하게 구 센트로이드 기준 집계"*
- [ ] 인프라/의료/기후 페이지가 어떻게 집계하는지 비교 → 통일안 결정
- [ ] 결정 후 복지 / 다른 페이지 일괄 적용

### G11. 제설함 OFF 안 됨 — 실제 재현
- 코드(`IceTab.svelte:295-307, 360-368`)는 정상으로 보임
- [ ] 브라우저에서 실제로 안 되는지 step-by-step 디버그
  - ① 단순 클릭으로 OFF 가능한지
  - ② 100m/200m 토글 후 OFF 가능한지
  - ③ `boxesLayer` 가 layerGroup 인지 console.log

### G12. 컨벡스헐 파이썬 코드 업로드
- [ ] `final_output/ENSEMBLE/dashboard/2_Shim_infra.html` 의 GRAPH_GZ 생성 파이프라인 파이썬 코드 위치 찾기
- [ ] `_research/` 또는 `static/scripts/` 에 업로드
- [ ] README 또는 CLAUDE.md 에 위치·실행법 기록

### G13. 카드 디자인 의료 통일 — 추가 점검
- hero 는 이미 통일 (✅)
- [ ] 교통 탭 내부 `.card` / `.sc` (stat card) 스타일과 의료 페이지 비교
- [ ] 차이점 발견 시 통일

---

## 🐛 알려진 작은 이슈 (이미 수정됨)

- ~~CountUp 음수 시작~~ → `Math.max(0, ...)` 클램프 추가 (2026-05-11)
- ~~결론 표 순위 (정렬해도 1,2,3 유지 안 됨)~~ → `i + 1` 로 수정 (2026-05-11)
- ~~애니메이션 duration 불일치~~ → `theme.js` `ANIM` 토큰 + CountUp 디폴트 통일 (2026-05-11)

---

## 🚀 권장 작업 순서

1. **G1 ~ G5 묶음** (1시간 — 모두 단순 라벨/숫자/색 수정)
2. **G6 헤더 클릭 정렬** (공통 유틸 + 6개 표 적용 — 1.5시간)
3. **G7 막대 통일** (1시간)
4. **G8 교통 구 필터** (별도 세션)
5. **G9 복지 도로망** (G10 원칙 확정 후)
6. **G11 ~ G13** 추가 점검 후 진행
