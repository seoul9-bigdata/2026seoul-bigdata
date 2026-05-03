# 보행 반경 모식도 — 하버사인 → OSM 전환 설계

> 작성일: 2026-05-03  
> 대상 파일: `outputs_SHIM/260429/outputs/infra_dashboard_v5.html`

---

## 1. 문제 제기

현재 `infra_dashboard_v5.html`의 **보행 반경 모식도** (우측 Canvas 패널)는 하버사인 기반 유클리드 직선거리로 구현되어 있다.

```
반경 = 보행속도(m/s) × 시간(초)   ← 순수 직선거리
시설 위치 = (각도, 직선거리) 극좌표로 캔버스에 점 표시
```

이 방식은 **완벽한 동심원**을 만들기 때문에 시각적으로 깔끔하다는 장점이 있다.

그러나 다른 섹션의 경우 **OSM 보행 네트워크 + Dijkstra 최단경로**로 계산한다.
OSM 기반 도달 영역을 그대로 그리면 도로망 형태를 따라가는 **찌그러진 컨벡스 헐**이 나올 수밖에 없어, 원형 디자인과 양립이 불가능하다.

**핵심 갈등:**

|                | 하버사인 원형            | OSM Dijkstra                  |
| -------------- | ------------------------ | ----------------------------- |
| 시각적 표현    | 깔끔한 동심원            | 찌그러진 컨벡스 헐            |
| 데이터 정확성  | 실제 도로망 무시         | 실제 보행 반영                |
| 시설 색상 판단 | 직선거리 ≤ 반경이면 초록 | 네트워크 거리 ≤ 반경이면 초록 |

---

## 2. 세 가지 해결 접근법

### A. 원형 유지 + OSM 시설 오버레이 ✅ 채택

원을 **이론적 반경 기준선**으로 유지하고, 시설 점의 **반경 방향 위치를 OSM 네트워크 거리 기준으로 이동**한다.

```
각도(angle)  = 하버사인 방위각 (지리적 방향 유지)
반경(r)      = OSM 네트워크 거리 (실제 보행 거리)
색상 판단    = network_dist ≤ speed × time 이면 초록, 아니면 빨강
```

**직관적 해석:**

- 원 안에 점 → 실제 도보 30분 내 도달 가능
- 직선으로는 가까운데 원 밖에 점 → 도로 단절, 블록 우회 등으로 실거리 초과
- 원 안인데 직선거리보다 안쪽에 점 → 경로가 짧음 (네트워크 효율 높음)

**구현 난이도:** 낮음 (Python 데이터 파이프라인에서 `dist` 필드만 교체)  
**디자인 변경:** 없음 (원형 유지, 레이블 "이론적 반경" 추가 권장)

---

### B. 알파쉐이프 + SVG smoothing

OSM 도달 노드 집합 → Alpha Shape(오목 헐) 계산 → SVG `stroke-linejoin: round` + `filter: blur` 로 부드럽게 렌더링.

- 이소크론 형태 자체를 유지
- 구현 난이도 중간 (Python에서 `alphashape` 라이브러리 필요)
- 찌그러짐은 어느 정도 남음, 원형 디자인 완전 유지 불가

---

### C. 등가 반경 원 (Equivalent Radius)

OSM 도달 영역의 면적을 계산하고, 동일 면적의 원 반지름을 구해 그린다.

```
r_equiv = sqrt(OSM_도달_면적 / π)
```

- 완벽한 원 유지
- "이 원의 넓이 = 실제 걸어서 갈 수 있는 면적"으로 정직한 표현
- 방향 정보 손실 (어느 방향이 막혔는지 표현 불가)
- 구현 난이도 중간

---

## 3. 채택 방안(A안) 상세 구현

### 3-1. 개념도

```
현재 (하버사인)                   변경 후 (OSM 하이브리드)

       ↑                                  ↑
    [원 = 이론적 반경]               [원 = 이론적 반경]  ← 동일
       |                                  |
  ●────┼──── 직선거리로 배치         ●────┼── OSM 네트워크 거리로 배치
  (점의 반경 = haversine_dist)      (점의 반경 = network_dist)
  (각도 = 하버사인 방위각)          (각도 = 하버사인 방위각) ← 동일
```

---

### 3-2. Python 데이터 파이프라인 변경

현재 `NEARBY` JSON 생성 시 `dist` = 하버사인 직선거리.  
이를 `network_dist`(OSM 최단 보행거리)로 교체한다.

```python
import osmnx as ox
import networkx as nx

# G_u: 서울 보행 네트워크 (analysis_v2.py와 동일 그래프 재활용)

def compute_nearby_osm(centroid_lon, centroid_lat, pois, G_u, max_dist_m=3000):
    """
    centroid에서 각 POI까지의 OSM 네트워크 거리 계산.
    각도(angle)는 하버사인 방위각 유지, dist만 network_dist로 교체.
    """
    center_node = ox.nearest_nodes(G_u, centroid_lon, centroid_lat)

    results = []
    for poi in pois:
        poi_node = ox.nearest_nodes(G_u, poi['lng'], poi['lat'])
        try:
            network_dist = nx.shortest_path_length(
                G_u, center_node, poi_node, weight='length'
            )
        except nx.NetworkXNoPath:
            network_dist = 9999  # 도달 불가

        # 방위각은 하버사인으로 유지 (시각적 방향 정보 보존)
        bearing = compute_bearing(centroid_lat, centroid_lon, poi['lat'], poi['lng'])

        results.append({
            'name':  poi['name'],
            'type':  poi['type'],
            'dist':  round(network_dist),   # ← haversine_dist → network_dist
            'angle': round(bearing, 1),     # ← 유지
            'cat':   poi['cat'],
        })

    return sorted(results, key=lambda x: x['dist'])
```

**주의:** `NEARBY` JSON의 키명은 `dist` 그대로 유지. HTML Canvas 코드 변경 불필요.

---

### 3-3. HTML Canvas 코드 변경 사항

`drawCanvas()` 함수에서 변경할 부분은 **레이블 1줄**뿐이다.

```js
// 변경 전
document.getElementById("canvasLabel").textContent =
  (d ? d.dong : cG) + " · 30분 보행반경 · centroid 기준";

// 변경 후
document.getElementById("canvasLabel").textContent =
  (d ? d.dong : cG) + " · 30분 보행반경 (원: 이론, 점: OSM 실거리)";
```

선택적으로, 원에 "이론적 반경" 레이블을 추가할 수 있다:

```js
// WS.forEach 내부, sel === true 구간에 추가
if (sel) {
  ctx.font = "bold 11px sans-serif";
  ctx.fillStyle = ws.color;
  ctx.textAlign = "center";
  ctx.fillText(
    ws.label + " " + Math.round(ws.speed * cT * 60).toLocaleString() + "m",
    cx,
    14,
  );
  // 원 테두리에 "이론적 반경" 주석 (선택)
  ctx.font = "9px sans-serif";
  ctx.fillStyle = ws.color + "99";
  ctx.textAlign = "left";
  ctx.fillText("이론", cx + ra + 3, cy - 3);
}
```

---

### 3-4. 색상 판단 로직

현재 코드 (변경 없음, 그대로 동작):

```js
const reach = m.dist <= r_avg; // network_dist <= 이론반경이면 초록
ctx.fillStyle = reach ? "#1D9E75" : "rgba(200,80,80,0.5)";
```

`m.dist`가 OSM 네트워크 거리로 교체되면 이 판단이 자동으로 정확해진다.

---

### 3-5. 시각적 효과 예시

```
[원 = 1584m (보조기기, 30분)]

    ●  통인시장  ← haversine 1200m이지만 network 1650m → 원 밖 (빨강)
   /             직선으론 가깝지만 언덕/막힌 골목으로 실거리 증가
  O (중심)
   \
    ●  마트X    ← haversine 1600m이지만 network 1400m → 원 안 (초록)
                  거리는 멀어 보이지만 직선 도로로 실거리 단축
```

---

## 4. 구현 우선순위

| 단계 | 작업                                              | 파일                             |
| ---- | ------------------------------------------------- | -------------------------------- |
| 1    | OSM 그래프 재활용 (`seoul_walk.graphml`)          | `analysis_v2.py`                 |
| 2    | `compute_nearby_osm()` 구현 및 NEARBY JSON 재생성 | 별도 `preprocess_nearby.py` 권장 |
| 3    | HTML의 `NEARBY` 변수 교체                         | `infra_dashboard_v5.html`        |
| 4    | `canvasLabel` 텍스트 1줄 수정                     | 동 파일                          |

**전체 디자인 변경 없음. Canvas 원형 구조, 색상 시스템, 레이아웃 모두 그대로.**

---

## 5. 판단 근거

A안을 채택한 이유:

1. **정보량 증가**: 원(이론)과 점(실측)의 괴리가 도로망 공백을 시각화
2. **디자인 무변경**: Canvas 로직, 색상, 레이아웃 모두 그대로
3. **구현 비용 최소**: Python 파이프라인의 `dist` 계산 방식만 교체
4. **일관성**: `analysis_v2.py`와 동일 그래프(`seoul_walk.graphml`) 재활용 가능

B안(알파쉐이프)은 시각적 완성도가 높지만 원형 포기 + 추가 라이브러리 필요.  
C안(등가반경)은 구현 단순하나 방향 정보가 사라져 시각적 서사 약화.
