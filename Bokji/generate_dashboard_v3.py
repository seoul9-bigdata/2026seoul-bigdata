#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_dashboard_v3.py — 복지·녹지 접근성 대시보드 생성"""

import os, sys, io, json, re
import pandas as pd

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_v3')
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("Bokji 복지·녹지 접근성 대시보드 생성기 v3")
print("=" * 60)

# ── 1. DONG 데이터 ────────────────────────────────────────────────────────────
print("\n1. DONG 데이터 로드")
df = pd.read_csv(
    os.path.join(BASE_DIR, 'output_v2', 'dong_reachability_v2.csv'),
    encoding='utf-8-sig'
)
df.columns = [c.strip() for c in df.columns]

def safe_int(v):
    try: return int(float(v))
    except: return 0

def safe_float(v, d=2):
    try: return round(float(v), d)
    except: return 0.0

DONG = []
for _, r in df.iterrows():
    DONG.append({
        'key':  r['동_key'],
        'gu':   r['구명'],
        'dong': r['동명'],
        'pop65': safe_int(r['65세이상인구']),
        'aging': safe_float(r.get('고령화율', 0)),
        'w': [
            safe_int(r['복지_일반인']),
            safe_int(r['복지_일반노인']),
            safe_int(r['복지_보조기기']),
            safe_int(r['복지_보조하위15p']),
        ],
        'p': [
            safe_int(r['공원_일반인']),
            safe_int(r['공원_일반노인']),
            safe_int(r['공원_보조기기']),
            safe_int(r['공원_보조하위15p']),
        ],
        'vuln': safe_float(r['vulnerability_v2'], 4),
    })
print(f"  DONG: {len(DONG)}개 행정동")

# ── 2. WELFARE 데이터 ─────────────────────────────────────────────────────────
print("\n2. WELFARE 데이터 로드")
with open(os.path.join(BASE_DIR, '서울시 사회복지시설(노인여가복지시설) 목록.csv'), 'rb') as f:
    wdf = pd.read_csv(io.StringIO(f.read().decode('euc-kr')), header=0)
wdf.columns = [
    '시설명', '시설코드', '시설유형', '시설종류상세',
    '자치구구분', '시군구코드', '시군구명', '시설주소',
    '전화번호', '우편번호'
]
wdf['시설주소'] = wdf['시설주소'].fillna('').str.strip()
wdf = wdf[wdf['시설주소'] != ''].copy()

def short_type(t):
    t = str(t)
    if '소규모' in t:   return '노인복지관(소규모)'
    if '노인교실' in t: return '노인교실'
    return '노인복지관'
wdf['유형'] = wdf['시설유형'].apply(short_type)

with open(os.path.join(BASE_DIR, 'output', 'geocode_cache.json'), 'rb') as f:
    cache = json.loads(f.read().decode('utf-8'))

WELFARE = []
for _, row in wdf.iterrows():
    v = cache.get(row['시설주소'], {})
    if v.get('lat') and v.get('lng'):
        WELFARE.append({
            'name': row['시설명'],
            'gu':   row['시군구명'],
            'type': row['유형'],
            'lat':  round(float(v['lat']), 6),
            'lng':  round(float(v['lng']), 6),
        })
print(f"  WELFARE: {len(WELFARE)}개 (좌표 확보)")

# ── 3. PARK 데이터 ────────────────────────────────────────────────────────────
print("\n3. PARK 데이터 로드")
parks_raw = pd.read_excel(
    os.path.join(BASE_DIR, '서울시 주요 공원현황(2026 상반기).xlsx')
)
parks_raw.columns = [
    '연번', '관리부서', '전화번호', '공원명', '공원개요',
    '면적', '개원일', '주요시설', '주요식물', '안내도',
    '오시는길', '이용시참고사항', '이미지', '지역', '공원주소',
    'X_GRS80', 'Y_GRS80', 'X_WGS84', 'Y_WGS84', '바로가기'
]

def parse_area(v):
    m = re.search(r'[\d]+', str(v).replace(',', ''))
    return float(m.group()) if m else 0.0

parks_raw['area'] = parks_raw['면적'].apply(parse_area)
parks_ok = parks_raw.dropna(subset=['X_WGS84', 'Y_WGS84']).copy()
parks_ok = parks_ok[parks_ok['X_WGS84'] > 0]

PARK = []
for _, row in parks_ok.iterrows():
    PARK.append({
        'name': str(row['공원명']),
        'gu':   str(row['지역']) if pd.notna(row['지역']) else '',
        'area': int(row['area']) if row['area'] > 0 else 0,
        'lat':  round(float(row['Y_WGS84']), 6),
        'lng':  round(float(row['X_WGS84']), 6),
    })
print(f"  PARK: {len(PARK)}개 (좌표 확보)")

# ── 4. JSON 직렬화 ────────────────────────────────────────────────────────────
print("\n4. 데이터 직렬화")
DONG_JS    = json.dumps(DONG,    ensure_ascii=False, separators=(',', ':'))
WELFARE_JS = json.dumps(WELFARE, ensure_ascii=False, separators=(',', ':'))
PARK_JS    = json.dumps(PARK,    ensure_ascii=False, separators=(',', ':'))
print(f"  DONG    : {len(DONG_JS)//1024} KB")
print(f"  WELFARE : {len(WELFARE_JS)//1024} KB")
print(f"  PARK    : {len(PARK_JS)//1024} KB")

# ── 5. HTML 템플릿 ────────────────────────────────────────────────────────────
print("\n5. HTML 생성 중...")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>노인 보행일상권 — ② 복지·녹지 인프라</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;background:#f5f4f0;color:#2c2c2a;font-size:14px;line-height:1.5;overflow-y:scroll}
header{background:#2c2c2a;color:#f1efe8;padding:16px 28px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
header h1{font-size:17px;font-weight:500}
header p{font-size:12px;opacity:.55}
.wrap{max-width:1320px;margin:0 auto;padding:18px 18px 52px}
.ctrl{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 20px;margin-bottom:14px}
.crow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.crow:last-child{margin-bottom:0}
.lbl{font-size:11px;font-weight:500;letter-spacing:.06em;color:#888780;white-space:nowrap;margin-right:2px}
.btn{font-size:12px;padding:5px 14px;border-radius:20px;border:0.5px solid #b4b2a9;background:transparent;color:#5f5e5a;cursor:pointer;transition:all .14s;font-family:inherit;white-space:nowrap}
.btn:hover{border-color:#5f5e5a;color:#2c2c2a}
.btn.on{background:#2c2c2a;color:#f1efe8;border-color:#2c2c2a}
.bw{border-radius:8px}
select{font-size:12px;padding:5px 10px;border-radius:8px;border:0.5px solid #b4b2a9;background:#fff;color:#2c2c2a;font-family:inherit}
.sgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}
.sc{background:#f5f4f0;border-radius:8px;padding:12px 14px}
.sl{font-size:11px;color:#888780;margin-bottom:3px}
.sv{font-size:22px;font-weight:500}
.ss{font-size:11px;color:#888780;margin-top:2px}
.r2{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px}
.r2b{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 18px;margin-bottom:14px}
.r2 .card,.r2b .card{margin-bottom:0}
.ct{font-size:11px;font-weight:500;letter-spacing:.06em;color:#888780;text-transform:uppercase;margin-bottom:10px}
#map-wrap{position:relative;height:420px;border-radius:8px;overflow:hidden;background:#e8e4db}
#map{position:absolute;inset:0;height:100%!important}
.leg{display:flex;gap:12px;flex-wrap:wrap;margin-top:9px}
.li{display:flex;align-items:center;gap:5px;font-size:11px;color:#5f5e5a}
.ld{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.lr{width:14px;height:2px;flex-shrink:0;border-top:2px dashed}
.note{background:#faeeda;border:0.5px solid #ef9f27;border-radius:8px;padding:10px 14px;font-size:12px;color:#633806;line-height:1.7;margin-top:12px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{padding:6px 10px;text-align:left;font-weight:500;color:#888780;border-bottom:0.5px solid #d3d1c7;white-space:nowrap;position:sticky;top:0;background:#fff;z-index:1}
td{padding:7px 10px;border-bottom:0.5px solid #f1efe8}
tr:hover td{background:#fafaf8}
.pill{display:inline-block;font-size:10px;font-weight:500;padding:2px 8px;border-radius:10px}
.phi{background:#e1f5ee;color:#0f6e56}
.pmd{background:#faeeda;color:#854f0b}
.plo{background:#fcebeb;color:#a32d2d}
.src{font-size:11px;color:#888780;margin-top:8px;line-height:1.7}
.tabs{display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap}
.tab{font-size:12px;padding:4px 12px;border-radius:6px;border:0.5px solid transparent;background:transparent;color:#888780;cursor:pointer;font-family:inherit}
.tab:hover{background:#f5f4f0}
.tab.on{background:#f1efe8;color:#2c2c2a;font-weight:500;border-color:#d3d1c7}
.chart-wrap{position:relative;height:300px;width:100%}
.tbl-wrap{overflow-x:auto;max-height:400px;overflow-y:auto}
.canvas-label{font-size:11px;color:#888780;margin-bottom:6px}
@media(max-width:900px){.r2,.r2b,.sgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>② 복지·녹지 인프라 — 노인 보행일상권 분석</h1>
  <p>OSM 보행 네트워크 기반 · 노인여가복지시설 185개소 + 공원 132개소 · 30분 기준 · 서울시 2026</p>
</header>

<div class="wrap">

  <!-- ── 컨트롤 패널 ── -->
  <div class="ctrl">
    <div class="crow">
      <span class="lbl">보행자 유형</span>
      <button class="btn bw on" data-w="0" onclick="setW(0,this)">🚶 일반인 &nbsp;1.28 m/s</button>
      <button class="btn bw"    data-w="1" onclick="setW(1,this)">🧓 일반 노인 &nbsp;1.12 m/s</button>
      <button class="btn bw"    data-w="2" onclick="setW(2,this)">🦽 보조기구 &nbsp;0.88 m/s</button>
      <button class="btn bw"    data-w="3" onclick="setW(3,this)">♿ 보조 하위15% &nbsp;0.70 m/s</button>
      <span style="flex:1"></span>
      <span class="lbl">시설 유형</span>
      <button class="btn on" data-f="both"    onclick="setF('both',this)">복지 + 공원</button>
      <button class="btn"    data-f="welfare" onclick="setF('welfare',this)">복지시설만</button>
      <button class="btn"    data-f="park"    onclick="setF('park',this)">공원만</button>
    </div>
    <div class="crow">
      <span class="lbl">기준 자치구</span>
      <select id="guSel" onchange="setG(this.value)"></select>
      <span style="font-size:11px;color:#888780;margin-left:6px">자치구 중심점 기준 · 점선 원은 현재 보행자가 30분 내 도달 가능 범위입니다</span>
    </div>
    <div class="sgrid" id="sg"></div>
  </div>

  <!-- ── 지도 + 속도 비교 차트 ── -->
  <div class="r2">
    <div class="card">
      <div class="ct">서울시 복지·녹지 시설 분포 지도</div>
      <div class="tabs">
        <button class="tab on" onclick="setLayer('both',this)">복지시설 + 공원</button>
        <button class="tab"    onclick="setLayer('welfare',this)">복지시설만</button>
        <button class="tab"    onclick="setLayer('park',this)">공원만</button>
      </div>
      <div id="map-wrap"><div id="map"></div></div>
      <div class="leg">
        <div class="li"><div class="ld" style="background:#185FA5"></div>노인복지관</div>
        <div class="li"><div class="ld" style="background:#E8A838"></div>노인교실</div>
        <div class="li"><div class="ld" style="background:#8AAFD4"></div>소규모복지관</div>
        <div class="li"><div class="ld" style="background:#4CAF50"></div>공원</div>
        <div class="li"><div class="lr" style="border-color:#FF6F00"></div>30분 보행반경</div>
      </div>
      <p class="src">출처: 서울시 사회복지시설(노인여가복지시설) 목록 · 서울시 주요 공원현황(2026 상반기)<br>
      ※ 복지시설 185개소 지오코딩 · 공원 132개소 좌표 확보 · 반경은 자치구 중심점 기준 직선거리</p>
    </div>

    <div class="card">
      <div class="ct">선택 자치구 4속도 비교 — <span id="guLabel">종로구</span></div>
      <div class="chart-wrap"><canvas id="speedChart"></canvas></div>
      <p class="src" style="margin-top:6px">30분 기준 · 행정동 평균 도달 시설 수 · 복지시설(파랑) / 공원(초록)</p>
    </div>
  </div>

  <!-- ── 구별 차트 + TOP10 ── -->
  <div class="r2b">
    <div class="card">
      <div class="ct">자치구별 평균 도달 시설 수 (현재 보행자·시설 기준)</div>
      <div class="chart-wrap"><canvas id="guChart"></canvas></div>
    </div>
    <div class="card">
      <div class="ct">취약도 TOP 10 행정동</div>
      <div class="chart-wrap"><canvas id="top10Chart"></canvas></div>
    </div>
  </div>

  <!-- ── 상세 테이블 ── -->
  <div class="card">
    <div class="ct">행정동별 복지·녹지 접근성 상세표</div>
    <p class="canvas-label">취약도 지수 내림차순 · 보조 하위 15%(0.70 m/s) 기준 0개 도달 시 적색 표시</p>
    <div class="tbl-wrap"><table id="tbl"></table></div>
  </div>

  <div class="note">
    ※ 보행보조장치 사용 노인 하위 15% 속도(0.70 m/s)는 교통약자 기준(0.80 m/s)보다 낮아 동일 시간 내 도달 범위가 더 좁습니다.<br>
    ※ 분석 기준: OSM 보행 네트워크 · 30분 보행 · 행정동 중심점 출발 · 취약도 = (복지박탈 50% + 공원박탈 50%) Min-Max 정규화<br>
    ※ 복지시설: 노인여가복지시설(노인복지관·노인교실·소규모) 185개소 · 공원: 서울시 주요 공원 132개소
  </div>

</div><!-- /wrap -->

<script>
// ── 임베드 데이터 ──────────────────────────────────────────────────────────
const DONG    = __DONG_DATA__;
const WELFARE = __WELFARE_DATA__;
const PARK    = __PARK_DATA__;

// ── 25개 자치구 중심 좌표 ──────────────────────────────────────────────────
const GU_CENTER = {
  '종로구':[37.5929,126.9768],'중구':[37.5640,126.9976],'용산구':[37.5324,126.9807],
  '성동구':[37.5631,127.0367],'광진구':[37.5390,127.0822],'동대문구':[37.5744,127.0406],
  '중랑구':[37.6063,127.0926],'성북구':[37.5894,127.0167],'강북구':[37.6396,127.0250],
  '도봉구':[37.6688,127.0471],'노원구':[37.6540,127.0736],'은평구':[37.6177,126.9228],
  '서대문구':[37.5791,126.9368],'마포구':[37.5642,126.9016],'양천구':[37.5170,126.8667],
  '강서구':[37.5509,126.8496],'구로구':[37.4955,126.8877],'금천구':[37.4575,126.8952],
  '영등포구':[37.5261,126.8962],'동작구':[37.5122,126.9393],'관악구':[37.4784,126.9516],
  '서초구':[37.4837,127.0324],'강남구':[37.5172,127.0473],'송파구':[37.5145,127.1059],
  '강동구':[37.5301,127.1237]
};

// ── 보행속도 파라미터 ──────────────────────────────────────────────────────
const SPEEDS = [
  {key:'일반인',      mps:1.28, color:'#2196F3'},
  {key:'일반노인',    mps:1.12, color:'#4CAF50'},
  {key:'보조기기',    mps:0.88, color:'#FF9800'},
  {key:'보조하위15%', mps:0.70, color:'#F44336'},
];

// ── 상태 변수 ──────────────────────────────────────────────────────────────
let cW=0, cF='both', cLayer='both', cG='종로구';
let map_obj, welfareGroup, parkGroup, radiusCircle=null;
let guChartObj=null, speedChartObj=null, top10ChartObj=null;

// ── 초기화 ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initGuSelector();
  initMap();
  initCharts();
  update();
});

function initGuSelector() {
  const sel = document.getElementById('guSel');
  const gus = [...new Set(DONG.map(d => d.gu))].sort();
  gus.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g; opt.textContent = g;
    sel.appendChild(opt);
  });
  sel.value = cG;
}

function initMap() {
  map_obj = L.map('map').setView([37.5665, 126.9780], 11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org">OpenStreetMap</a> &copy; <a href="https://carto.com">CARTO</a>',
    maxZoom: 18
  }).addTo(map_obj);

  welfareGroup = L.layerGroup().addTo(map_obj);
  parkGroup    = L.layerGroup().addTo(map_obj);

  const TC = {
    '노인복지관': '#185FA5',
    '노인교실':   '#E8A838',
    '노인복지관(소규모)': '#8AAFD4'
  };
  WELFARE.forEach(w => {
    L.circleMarker([w.lat, w.lng], {
      radius: 5, color: TC[w.type] || '#185FA5', weight: 1,
      fillColor: TC[w.type] || '#185FA5', fillOpacity: 0.85
    }).bindTooltip(`<b>${w.name}</b><br><i style="color:#888">${w.type}</i>`)
      .addTo(welfareGroup);
  });

  PARK.forEach(p => {
    const r = Math.max(3, Math.min(11, p.area / 30000));
    L.circleMarker([p.lat, p.lng], {
      radius: r, color: '#2E7D32', weight: 1,
      fillColor: '#4CAF50', fillOpacity: 0.55
    }).bindTooltip(`<b>${p.name}</b><br>${p.area > 0 ? (p.area/10000).toFixed(1)+'ha' : ''}`)
      .addTo(parkGroup);
  });
}

function initCharts() {
  const defaults = {
    responsive: true, maintainAspectRatio: false,
    animation: { duration: 200 }
  };

  guChartObj = new Chart(document.getElementById('guChart'), {
    type: 'bar',
    data: { labels: [], datasets: [] },
    options: {
      ...defaults,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => ` ${parseFloat(c.raw).toFixed(1)}개 (평균)` } }
      },
      scales: {
        x: { grid: { color: '#f1efe8' }, title: { display: true, text: '평균 도달 가능 시설 수', font: { size: 10 } } },
        y: { ticks: { font: { size: 9 } } }
      }
    }
  });

  speedChartObj = new Chart(document.getElementById('speedChart'), {
    type: 'bar',
    data: { labels: [], datasets: [] },
    options: {
      ...defaults,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, boxWidth: 12 } },
        tooltip: { callbacks: { label: c => ` ${parseFloat(c.raw).toFixed(2)}개 (평균)` } }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        y: { grid: { color: '#f1efe8' }, title: { display: true, text: '평균 도달 수', font: { size: 10 } } }
      }
    }
  });

  top10ChartObj = new Chart(document.getElementById('top10Chart'), {
    type: 'bar',
    data: { labels: [], datasets: [] },
    options: {
      ...defaults,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: c => ` 취약도: ${parseFloat(c.raw).toFixed(3)}` } }
      },
      scales: {
        x: { max: 1.05, grid: { color: '#f1efe8' }, title: { display: true, text: '취약도 지수 v2', font: { size: 10 } } },
        y: { ticks: { font: { size: 9 } } }
      }
    }
  });
}

// ── 이벤트 핸들러 ──────────────────────────────────────────────────────────
function setW(i, btn) {
  cW = i;
  document.querySelectorAll('[data-w]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  update();
}

function setF(f, btn) {
  cF = f;
  document.querySelectorAll('[data-f]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  update();
}

function setLayer(v, btn) {
  cLayer = v;
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  updateMap();
}

function setG(gu) {
  cG = gu;
  document.getElementById('guLabel').textContent = gu;
  update();
}

function update() {
  updateStats();
  updateMap();
  updateGuChart();
  updateSpeedChart();
  updateTop10Chart();
  updateTable();
}

// ── 통계 박스 ──────────────────────────────────────────────────────────────
function updateStats() {
  const gd = DONG.filter(d => d.gu === cG);
  const n  = gd.length || 1;

  const avgW = (gd.reduce((s, d) => s + d.w[cW], 0) / n).toFixed(1);
  const avgP = (gd.reduce((s, d) => s + d.p[cW], 0) / n).toFixed(1);
  const wExc = gd.filter(d => d.w[3] === 0).length;
  const pExc = gd.filter(d => d.p[3] === 0).length;

  const wColor = wExc > 0 ? '#a32d2d' : '#0f6e56';
  const pColor = pExc > 0 ? '#a32d2d' : '#0f6e56';

  document.getElementById('sg').innerHTML = `
    <div class="sc">
      <div class="sl">평균 도달 복지시설 수</div>
      <div class="sv">${avgW}<span style="font-size:14px;font-weight:400;margin-left:4px">개소</span></div>
      <div class="ss">${cG} · ${SPEEDS[cW].key} · 30분</div>
    </div>
    <div class="sc">
      <div class="sl">평균 도달 공원 수</div>
      <div class="sv">${avgP}<span style="font-size:14px;font-weight:400;margin-left:4px">개소</span></div>
      <div class="ss">${cG} · ${SPEEDS[cW].key} · 30분</div>
    </div>
    <div class="sc">
      <div class="sl">복지 접근불가 동 수</div>
      <div class="sv" style="color:${wColor}">${wExc}<span style="font-size:14px;font-weight:400;margin-left:4px">개 동</span></div>
      <div class="ss">보조 하위15% 기준 0개 도달</div>
    </div>
    <div class="sc">
      <div class="sl">공원 접근불가 동 수</div>
      <div class="sv" style="color:${pColor}">${pExc}<span style="font-size:14px;font-weight:400;margin-left:4px">개 동</span></div>
      <div class="ss">보조 하위15% 기준 0개 도달</div>
    </div>
  `;
}

// ── 지도 업데이트 ──────────────────────────────────────────────────────────
function updateMap() {
  if (cLayer === 'welfare') {
    map_obj.addLayer(welfareGroup); map_obj.removeLayer(parkGroup);
  } else if (cLayer === 'park') {
    map_obj.removeLayer(welfareGroup); map_obj.addLayer(parkGroup);
  } else {
    map_obj.addLayer(welfareGroup); map_obj.addLayer(parkGroup);
  }

  if (radiusCircle) { map_obj.removeLayer(radiusCircle); radiusCircle = null; }
  const center = GU_CENTER[cG];
  if (center) {
    const r = Math.round(SPEEDS[cW].mps * 30 * 60);
    radiusCircle = L.circle(center, {
      radius: r, color: '#FF6F00', weight: 2, dashArray: '8,5',
      fillColor: '#FF6F00', fillOpacity: 0.04
    }).bindTooltip(`${cG} 중심 · ${SPEEDS[cW].key} 30분 반경 ~${(r / 1000).toFixed(2)} km`)
      .addTo(map_obj);
    map_obj.setView(center, 12, { animate: true, duration: 0.4 });
  }
}

// ── 구별 바차트 ────────────────────────────────────────────────────────────
function updateGuChart() {
  const guMap = {};
  DONG.forEach(d => {
    if (!guMap[d.gu]) guMap[d.gu] = [];
    guMap[d.gu].push(d);
  });

  let vals = Object.entries(guMap).map(([g, dongs]) => {
    let v;
    if      (cF === 'welfare') v = dongs.reduce((s, d) => s + d.w[cW], 0) / dongs.length;
    else if (cF === 'park')    v = dongs.reduce((s, d) => s + d.p[cW], 0) / dongs.length;
    else                       v = dongs.reduce((s, d) => s + d.w[cW] + d.p[cW], 0) / dongs.length;
    return { gu: g, val: v };
  });
  vals.sort((a, b) => b.val - a.val);

  guChartObj.data.labels   = vals.map(v => v.gu);
  guChartObj.data.datasets = [{
    data:            vals.map(v => v.val.toFixed(2)),
    backgroundColor: vals.map(v => v.gu === cG ? '#D85A30' : SPEEDS[cW].color + 'aa'),
    borderRadius: 3,
  }];
  guChartObj.update('none');
}

// ── 속도 비교 차트 (선택 구) ───────────────────────────────────────────────
function updateSpeedChart() {
  const gd = DONG.filter(d => d.gu === cG);
  if (!gd.length) return;
  const n = gd.length;

  const wData = SPEEDS.map((_, i) => (gd.reduce((s, d) => s + d.w[i], 0) / n).toFixed(2));
  const pData = SPEEDS.map((_, i) => (gd.reduce((s, d) => s + d.p[i], 0) / n).toFixed(2));

  speedChartObj.data.labels   = SPEEDS.map(s => s.key);
  speedChartObj.data.datasets = [
    { label: '복지시설', data: wData, backgroundColor: '#185FA5cc', borderRadius: 4 },
    { label: '공원',     data: pData, backgroundColor: '#2E7D32cc', borderRadius: 4 },
  ];
  speedChartObj.update('none');
}

// ── TOP10 차트 ─────────────────────────────────────────────────────────────
function updateTop10Chart() {
  const top10 = [...DONG]
    .filter(d => d.pop65 > 0)
    .sort((a, b) => b.vuln - a.vuln)
    .slice(0, 10)
    .reverse();

  const colors = top10.map((_, i) => {
    const t = i / 9;
    const r = Math.round(180 + 75 * t);
    const g = Math.round(120 * (1 - t));
    return `rgba(${r},${g},0,0.85)`;
  });

  top10ChartObj.data.labels   = top10.map(d => `${d.gu} ${d.dong}`);
  top10ChartObj.data.datasets = [{
    data:            top10.map(d => d.vuln),
    backgroundColor: colors,
    borderRadius: 3,
  }];
  top10ChartObj.update('none');
}

// ── 상세 테이블 ────────────────────────────────────────────────────────────
function updateTable() {
  const sorted = [...DONG]
    .filter(d => d.pop65 > 0)
    .sort((a, b) => b.vuln - a.vuln);

  const rows = sorted.map(d => {
    const grade     = d.vuln >= 0.7 ? 'plo' : d.vuln >= 0.4 ? 'pmd' : 'phi';
    const gradeText = d.vuln >= 0.7 ? '위험' : d.vuln >= 0.4 ? '주의' : '양호';
    const w3style   = d.w[3] === 0 ? 'font-weight:600;color:#a32d2d' : '';
    const p3style   = d.p[3] === 0 ? 'font-weight:600;color:#a32d2d' : '';
    return `<tr>
      <td>${d.gu}</td><td>${d.dong}</td>
      <td>${d.pop65.toLocaleString()}</td>
      <td>${d.aging}%</td>
      <td><span class="pill ${grade}">${d.vuln.toFixed(3)} ${gradeText}</span></td>
      <td>${d.w[0]}</td><td>${d.w[1]}</td><td>${d.w[2]}</td>
      <td style="${w3style}">${d.w[3]}</td>
      <td>${d.p[0]}</td><td>${d.p[1]}</td><td>${d.p[2]}</td>
      <td style="${p3style}">${d.p[3]}</td>
    </tr>`;
  }).join('');

  document.getElementById('tbl').innerHTML = `
    <thead>
      <tr>
        <th>구명</th><th>동명</th><th>65세이상</th><th>고령화율</th><th>취약도</th>
        <th>복지(일반)</th><th>복지(노인)</th><th>복지(보조)</th><th style="background:#fcebeb">복지(하위15%)</th>
        <th>공원(일반)</th><th>공원(노인)</th><th>공원(보조)</th><th style="background:#fcebeb">공원(하위15%)</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  `;
}
</script>
</body>
</html>"""

HTML = (TEMPLATE
        .replace('__DONG_DATA__',    DONG_JS)
        .replace('__WELFARE_DATA__', WELFARE_JS)
        .replace('__PARK_DATA__',    PARK_JS))

out_path = os.path.join(OUTPUT_DIR, 'infra_dashboard_bokji.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)

size_kb = os.path.getsize(out_path) / 1024
print("\n" + "=" * 60)
print("[OK] 생성 완료!")
print(f"   파일: {out_path}")
print(f"   크기: {size_kb:.0f} KB")
print(f"   DONG {len(DONG)}개 / WELFARE {len(WELFARE)}개 / PARK {len(PARK)}개")
print("=" * 60)
