#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_dashboard_v4.py — 복지·녹지 접근성 대시보드 생성 v4

변경 사항 (vs v3):
  - 도달가능점수 = (선택속도 도달 수 / 일반인 도달 수) * 100
  - 일반인 선택 시 점수 패널 숨김 (항상 100)
  - 경사로 보정 토글: ON 시 tobler 보정 Dijkstra 값 사용
  - 분모(일반인 도달 수) = 0 → N/A 처리
"""

import os, sys, io, json, re
import pandas as pd
import requests
import geopandas as gpd

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_v4')
os.makedirs(OUTPUT_DIR, exist_ok=True)

DONG_NAME_MAP = {
    '종로1.2.3.4가동': '종로1·2·3·4가동', '종로5.6가동': '종로5·6가동',
    '금호2.3가동': '금호2·3가동', '상계3.4동': '상계3·4동',
    '상계6.7동': '상계6·7동', '중계2.3동': '중계2·3동',
    '면목3.8동': '면목3·8동', '상일1동': '상일제1동', '상일2동': '상일제2동',
    '신설동': '용신동', '용두동': '용신동',
}
def norm_dong(name):
    return DONG_NAME_MAP.get(str(name).strip(), str(name).strip())

print("=" * 60)
print("Bokji 복지·녹지 접근성 대시보드 생성기 v4")
print("=" * 60)

# ── 0. 행정동 중심점 로드 (동 단위 지도 반경용) ───────────────────────────────
print("\n0. 행정동 중심점 로드")
centroid_map = {}
try:
    resp = requests.get(
        "https://raw.githubusercontent.com/vuski/admdongkor/master/"
        "ver20230701/HangJeongDong_ver20230701.geojson", timeout=30
    )
    dong_gdf = gpd.GeoDataFrame.from_features(resp.json()['features'], crs='EPSG:4326')
    dong_gdf  = dong_gdf[dong_gdf['sido'] == '11'].copy()
    dong_gdf['동명']  = dong_gdf['adm_nm'].str.split(' ').str[-1].apply(norm_dong)
    dong_gdf['동_key'] = dong_gdf['sggnm'] + '_' + dong_gdf['동명']
    for _, row in dong_gdf.drop_duplicates('동_key').iterrows():
        centroid_map[row['동_key']] = (
            round(row.geometry.centroid.y, 5),
            round(row.geometry.centroid.x, 5),
        )
    print(f"  중심점 {len(centroid_map)}개 로드")
except Exception as e:
    print(f"  중심점 로드 실패 → 동 단위 반경 비활성화: {e}")

# ── 1. DONG 데이터 ────────────────────────────────────────────────────────────
print("\n1. DONG 데이터 로드")
df = pd.read_csv(
    os.path.join(BASE_DIR, 'output_v4', 'dong_reachability_v4.csv'),
    encoding='utf-8-sig'
)
df.columns = [c.strip() for c in df.columns]

def safe_int(v):
    try:    return int(float(v))
    except: return 0

def safe_float(v, d=2):
    try:    return round(float(v), d)
    except: return 0.0

DONG = []
for _, r in df.iterrows():
    # 원본 도달 수 [일반인, 노인, 보조기기, 하위15p]
    w_orig = [
        safe_int(r['복지_일반인']),
        safe_int(r['복지_일반노인']),
        safe_int(r['복지_보조기기']),
        safe_int(r['복지_보조하위15p']),
    ]
    p_orig = [
        safe_int(r['공원_일반인']),
        safe_int(r['공원_일반노인']),
        safe_int(r['공원_보조기기']),
        safe_int(r['공원_보조하위15p']),
    ]
    # 보정 도달 수 [일반인(원본 유지), 노인보정, 보조기기보정, 하위15p보정]
    w_corr = [
        w_orig[0],
        safe_int(r.get('복지_일반노인보정',    r['복지_일반노인'])),
        safe_int(r.get('복지_보조기기보정',     r['복지_보조기기'])),
        safe_int(r.get('복지_보조하위15p보정',  r['복지_보조하위15p'])),
    ]
    p_corr = [
        p_orig[0],
        safe_int(r.get('공원_일반노인보정',    r['공원_일반노인'])),
        safe_int(r.get('공원_보조기기보정',     r['공원_보조기기'])),
        safe_int(r.get('공원_보조하위15p보정',  r['공원_보조하위15p'])),
    ]
    DONG.append({
        'key':    r['동_key'],
        'gu':     r['구명'],
        'dong':   r['동명'],
        'pop65':  safe_int(r['65세이상인구']),
        'aging':  safe_float(r.get('고령화율', 0)),
        'w':      w_orig,
        'p':      p_orig,
        'wc':     w_corr,
        'pc':     p_corr,
        'tobler': safe_float(r.get('tobler_ratio', 1.0), 4),
        'vuln':   safe_float(r['vulnerability_v2'], 4),
        'clat':   centroid_map.get(r['동_key'], (None, None))[0],
        'clng':   centroid_map.get(r['동_key'], (None, None))[1],
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
<title>노인 보행일상권 — ② 복지·녹지 인프라 v4</title>
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
.btn.slope-on{background:#2E5A88;color:#f1efe8;border-color:#2E5A88}
.bw{border-radius:8px}
select{font-size:12px;padding:5px 10px;border-radius:8px;border:0.5px solid #b4b2a9;background:#fff;color:#2c2c2a;font-family:inherit}
.sgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}
.sc{background:#f5f4f0;border-radius:8px;padding:12px 14px}
.sl{font-size:11px;color:#888780;margin-bottom:3px}
.sv{font-size:22px;font-weight:500}
.ss{font-size:11px;color:#888780;margin-top:2px}
.sc.score-card{background:#eef3fa}
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
.pna{background:#ebebeb;color:#666}
.src{font-size:11px;color:#888780;margin-top:8px;line-height:1.7}
.tabs{display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap}
.tab{font-size:12px;padding:4px 12px;border-radius:6px;border:0.5px solid transparent;background:transparent;color:#888780;cursor:pointer;font-family:inherit}
.tab:hover{background:#f5f4f0}
.tab.on{background:#f1efe8;color:#2c2c2a;font-weight:500;border-color:#d3d1c7}
.chart-wrap{position:relative;height:300px;width:100%}
.tbl-wrap{overflow-x:auto;max-height:400px;overflow-y:auto}
.canvas-label{font-size:11px;color:#888780;margin-bottom:6px}
.slope-badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:10px;background:#dbe8f8;color:#1a4a80;margin-left:6px;vertical-align:middle}
@media(max-width:900px){.r2,.r2b,.sgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>② 복지·녹지 인프라 — 노인 보행일상권 분석</h1>
  <p>OSM 보행 네트워크 기반 · 노인여가복지시설 185개소 + 공원 132개소 · 30분 기준 · 서울시 2026 · Tobler 경사 보정 v4</p>
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
      <span class="lbl">경사로 보정</span>
      <button class="btn" id="slopeBtn" onclick="toggleSlope(this)">경사로 보정 적용</button>
      <span style="font-size:11px;color:#888780;margin-left:4px">
        · Tobler 보행속도 모델 · OSM 기반 동별 경사도 반영 · 일반인 속도 제외
      </span>
    </div>
    <div class="crow">
      <span class="lbl">동 단위 반경</span>
      <button class="btn" id="dongBtn" onclick="toggleDong(this)">동별 반경 표시</button>
      <span style="font-size:11px;color:#888780;margin-left:4px">
        · 선택 자치구 내 각 행정동 중심점 기준 · 점수 색상 반영
      </span>
    </div>
    <div class="crow">
      <span class="lbl">기준 자치구</span>
      <select id="guSel" onchange="setG(this.value)"></select>
      <span style="font-size:11px;color:#888780;margin-left:6px">자치구 중심점 기준 · 점선 원은 30분 내 도달 가능 범위</span>
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
      <p class="src" style="margin-top:6px">30분 기준 · 행정동 평균 도달 시설 수 · 복지시설(파랑) / 공원(초록)<br>경사 보정 ON 시 노인·보조기기·하위15% 속도에 동별 Tobler 비율 적용</p>
    </div>
  </div>

  <!-- ── 구별 차트 + TOP10 ── -->
  <div class="r2b">
    <div class="card">
      <div class="ct">자치구별 평균 도달 시설 수 (현재 보행자·시설 기준)</div>
      <div class="chart-wrap"><canvas id="guChart"></canvas></div>
    </div>
    <div class="card">
      <div class="ct" id="top10Title">도달가능점수 하위 10 행정동</div>
      <div class="chart-wrap"><canvas id="top10Chart"></canvas></div>
    </div>
  </div>

  <!-- ── 상세 테이블 ── -->
  <div class="card">
    <div class="ct">행정동별 복지·녹지 접근성 상세표</div>
    <p class="canvas-label" id="tblLabel">도달가능점수 오름차순 · 일반인 대비 보조하위15% 기준 · 0점=일반인도 도달 불가</p>
    <div class="tbl-wrap"><table id="tbl"></table></div>
  </div>

  <div class="note">
    ※ 도달가능점수 = (선택 속도로 도달 가능한 시설 수 / 일반인 속도로 도달 가능한 시설 수) × 100<br>
    ※ 일반인 선택 시 점수는 항상 100이므로 숨김 처리 · 분모(일반인 도달 수) = 0이면 N/A 표시<br>
    ※ 경사로 보정: Tobler 보행속도 모델 적용 · 동별 OSM 경사도 기반 · 일반인 속도는 보정 대상 제외<br>
    ※ 분석 기준: OSM 보행 네트워크 · 30분 보행 · 행정동 중심점 출발 · 서울시 2026
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
let cW=0, cF='both', cLayer='both', cG='종로구', cSlope=false, cDong=false;
let map_obj, welfareGroup, parkGroup, radiusCircle=null, dongCircleGroup=null;
let guChartObj=null, speedChartObj=null, top10ChartObj=null;

// ── 헬퍼: 현재 설정 기준 도달 수 반환 ────────────────────────────────────
function getW(d){ return (cSlope ? d.wc : d.w)[cW]; }
function getP(d){ return (cSlope ? d.pc : d.p)[cW]; }

// 도달가능점수 계산 (일반인 도달수 = 0이면 null 반환)
function wScore(d){
  const base = d.w[0];
  if(base === 0) return null;
  return Math.round(getW(d) / base * 100);
}
function pScore(d){
  const base = d.p[0];
  if(base === 0) return null;
  return Math.round(getP(d) / base * 100);
}
// 복지+공원 합산 점수 (둘 다 null이면 null)
function combinedScore(d){
  const ws = wScore(d), ps = pScore(d);
  if(ws === null && ps === null) return null;
  if(ws === null) return ps;
  if(ps === null) return ws;
  return Math.round((ws + ps) / 2);
}
// 현재 시설 유형에 따른 점수
function curScore(d){
  if(cF==='welfare') return wScore(d);
  if(cF==='park')    return pScore(d);
  return combinedScore(d);
}

// 점수 → 등급 pill
function scorePill(s){
  if(s === null)  return '<span class="pill pna">N/A</span>';
  if(s >= 80)     return `<span class="pill phi">${s}점</span>`;
  if(s >= 50)     return `<span class="pill pmd">${s}점</span>`;
  return `<span class="pill plo">${s}점</span>`;
}

// ── 초기화 ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initGuSelector();
  initMap();
  initCharts();
  update();
});

function initGuSelector(){
  const sel = document.getElementById('guSel');
  const gus = [...new Set(DONG.map(d=>d.gu))].sort();
  gus.forEach(g=>{
    const opt = document.createElement('option');
    opt.value = g; opt.textContent = g;
    sel.appendChild(opt);
  });
  sel.value = cG;
}

function initMap(){
  map_obj = L.map('map').setView([37.5665,126.9780],11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{
    attribution:'&copy; <a href="https://www.openstreetmap.org">OSM</a> &copy; <a href="https://carto.com">CARTO</a>',
    maxZoom:18
  }).addTo(map_obj);
  welfareGroup = L.layerGroup().addTo(map_obj);
  parkGroup    = L.layerGroup().addTo(map_obj);
  const TC={'노인복지관':'#185FA5','노인교실':'#E8A838','노인복지관(소규모)':'#8AAFD4'};
  WELFARE.forEach(w=>{
    L.circleMarker([w.lat,w.lng],{radius:5,color:TC[w.type]||'#185FA5',weight:1,
      fillColor:TC[w.type]||'#185FA5',fillOpacity:0.85})
      .bindTooltip(`<b>${w.name}</b><br><i style="color:#888">${w.type}</i>`)
      .addTo(welfareGroup);
  });
  PARK.forEach(p=>{
    const r=Math.max(3,Math.min(11,p.area/30000));
    L.circleMarker([p.lat,p.lng],{radius:r,color:'#2E7D32',weight:1,
      fillColor:'#4CAF50',fillOpacity:0.55})
      .bindTooltip(`<b>${p.name}</b><br>${p.area>0?(p.area/10000).toFixed(1)+'ha':''}`)
      .addTo(parkGroup);
  });
}

function initCharts(){
  const defaults={responsive:true,maintainAspectRatio:false,animation:{duration:200}};
  guChartObj = new Chart(document.getElementById('guChart'),{
    type:'bar',data:{labels:[],datasets:[]},
    options:{...defaults,indexAxis:'y',
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>` ${parseFloat(c.raw).toFixed(1)}개 (평균)`}}},
      scales:{x:{grid:{color:'#f1efe8'},title:{display:true,text:'평균 도달 가능 시설 수',font:{size:10}}},
              y:{ticks:{font:{size:9}}}}}
  });
  speedChartObj = new Chart(document.getElementById('speedChart'),{
    type:'bar',data:{labels:[],datasets:[]},
    options:{...defaults,
      plugins:{legend:{position:'top',labels:{font:{size:10},boxWidth:12}},
        tooltip:{callbacks:{label:c=>` ${parseFloat(c.raw).toFixed(2)}개 (평균)`}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:10}}},
              y:{grid:{color:'#f1efe8'},title:{display:true,text:'평균 도달 수',font:{size:10}}}}}
  });
  top10ChartObj = new Chart(document.getElementById('top10Chart'),{
    type:'bar',data:{labels:[],datasets:[]},
    options:{...defaults,indexAxis:'y',
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>{
          const v=parseFloat(c.raw);
          return cW===0?` 취약도: ${v.toFixed(3)}`
                       :` 도달가능점수: ${v}점`;
        }}}},
      scales:{x:{grid:{color:'#f1efe8'},
        title:{display:true,text:'',font:{size:10}}},
              y:{ticks:{font:{size:9}}}}}
  });
}

// ── 이벤트 핸들러 ──────────────────────────────────────────────────────────
function setW(i,btn){
  cW=i;
  document.querySelectorAll('[data-w]').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  update();
}
function setF(f,btn){
  cF=f;
  document.querySelectorAll('[data-f]').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  update();
}
function setLayer(v,btn){
  cLayer=v;
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  updateMap();
}
function setG(gu){
  cG=gu;
  document.getElementById('guLabel').textContent=gu;
  update();
}
function toggleSlope(btn){
  cSlope=!cSlope;
  btn.classList.toggle('slope-on', cSlope);
  btn.textContent = cSlope ? '경사로 보정 적용 중' : '경사로 보정 적용';
  update();
}
function toggleDong(btn){
  cDong=!cDong;
  btn.classList.toggle('slope-on', cDong);
  btn.textContent = cDong ? '동별 반경 표시 중' : '동별 반경 표시';
  updateDongCircles();
}
function update(){
  updateStats();
  updateMap();
  updateDongCircles();
  updateGuChart();
  updateSpeedChart();
  updateTop10Chart();
  updateTable();
}

// ── 동 단위 반경 원 ────────────────────────────────────────────────────────
function scoreColor(s){
  if(s===null)  return '#9E9E9E';
  if(s>=80)     return '#2E7D32';
  if(s>=50)     return '#F57F17';
  return '#C62828';
}
function updateDongCircles(){
  if(dongCircleGroup){ map_obj.removeLayer(dongCircleGroup); dongCircleGroup=null; }
  if(!cDong) return;

  dongCircleGroup = L.layerGroup().addTo(map_obj);
  const gd = DONG.filter(d=>d.gu===cG && d.clat!==null && d.clng!==null);

  gd.forEach(d=>{
    const tobler = (cSlope && cW>0) ? d.tobler : 1.0;
    const radiusM = Math.round(SPEEDS[cW].mps * tobler * 30 * 60);
    const s = curScore(d);
    const col = scoreColor(s);
    const scoreText = s!==null ? s+'점' : 'N/A';
    const slopeTip  = cSlope&&cW>0 ? `<br>Tobler: ${d.tobler.toFixed(3)}` : '';

    // 반경 원
    L.circle([d.clat, d.clng],{
      radius:radiusM, color:col, weight:1.2, dashArray:'5,4',
      fillColor:col, fillOpacity:0.06
    }).bindTooltip(`
      <b>${d.gu} ${d.dong}</b><br>
      보행반경: ~${(radiusM/1000).toFixed(2)} km<br>
      도달가능점수: ${scoreText}<br>
      복지 도달: ${getW(d)}개 · 공원 도달: ${getP(d)}개${slopeTip}
    `).addTo(dongCircleGroup);

    // 동 중심점 마커
    L.circleMarker([d.clat, d.clng],{
      radius:3, color:col, weight:1, fillColor:col, fillOpacity:0.9
    }).addTo(dongCircleGroup);

    // 점수가 낮은 동(50점 미만)은 레이블 표시
    if(s!==null && s<50){
      L.marker([d.clat, d.clng],{
        icon:L.divIcon({
          className:'',
          html:`<div style="font-size:9px;font-weight:600;color:${col};white-space:nowrap;
                text-shadow:0 0 2px #fff">${d.dong}</div>`,
          iconAnchor:[0,0]
        })
      }).addTo(dongCircleGroup);
    }
  });
}

// ── 통계 박스 ──────────────────────────────────────────────────────────────
function updateStats(){
  const gd = DONG.filter(d=>d.gu===cG);
  const n  = gd.length||1;
  const isNormal = (cW===0);

  const avgW = (gd.reduce((s,d)=>s+getW(d),0)/n).toFixed(1);
  const avgP = (gd.reduce((s,d)=>s+getP(d),0)/n).toFixed(1);

  // 도달가능점수 (일반인 제외)
  let scoreWHtml='', scorePHtml='';
  if(!isNormal){
    const validW = gd.filter(d=>d.w[0]>0);
    const validP = gd.filter(d=>d.p[0]>0);
    const avgWS  = validW.length ? Math.round(validW.reduce((s,d)=>s+wScore(d),0)/validW.length) : null;
    const avgPS  = validP.length ? Math.round(validP.reduce((s,d)=>s+pScore(d),0)/validP.length) : null;
    const slopeTag = cSlope ? '<span class="slope-badge">경사 보정</span>' : '';
    scoreWHtml = `
      <div class="sc score-card">
        <div class="sl">복지 도달가능점수 (평균)${slopeTag}</div>
        <div class="sv">${avgWS!==null?avgWS+'<span style="font-size:14px;font-weight:400;margin-left:2px">점</span>':'N/A'}</div>
        <div class="ss">${cG} · ${SPEEDS[cW].key} · 일반인 대비</div>
      </div>`;
    scorePHtml = `
      <div class="sc score-card">
        <div class="sl">공원 도달가능점수 (평균)${slopeTag}</div>
        <div class="sv">${avgPS!==null?avgPS+'<span style="font-size:14px;font-weight:400;margin-left:2px">점</span>':'N/A'}</div>
        <div class="ss">${cG} · ${SPEEDS[cW].key} · 일반인 대비</div>
      </div>`;
  } else {
    scoreWHtml = `
      <div class="sc">
        <div class="sl">복지 도달가능점수</div>
        <div class="sv" style="font-size:15px;color:#888780">일반인 기준</div>
        <div class="ss">일반인 선택 시 항상 100점 (숨김)</div>
      </div>`;
    scorePHtml = `
      <div class="sc">
        <div class="sl">공원 도달가능점수</div>
        <div class="sv" style="font-size:15px;color:#888780">일반인 기준</div>
        <div class="ss">일반인 선택 시 항상 100점 (숨김)</div>
      </div>`;
  }

  document.getElementById('sg').innerHTML = `
    <div class="sc">
      <div class="sl">평균 도달 복지시설 수</div>
      <div class="sv">${avgW}<span style="font-size:14px;font-weight:400;margin-left:4px">개소</span></div>
      <div class="ss">${cG} · ${SPEEDS[cW].key} · 30분${cSlope&&cW>0?' · 경사보정':''}</div>
    </div>
    <div class="sc">
      <div class="sl">평균 도달 공원 수</div>
      <div class="sv">${avgP}<span style="font-size:14px;font-weight:400;margin-left:4px">개소</span></div>
      <div class="ss">${cG} · ${SPEEDS[cW].key} · 30분${cSlope&&cW>0?' · 경사보정':''}</div>
    </div>
    ${scoreWHtml}
    ${scorePHtml}
  `;
}

// ── 지도 업데이트 ──────────────────────────────────────────────────────────
function updateMap(){
  if(cLayer==='welfare'){ map_obj.addLayer(welfareGroup); map_obj.removeLayer(parkGroup); }
  else if(cLayer==='park'){ map_obj.removeLayer(welfareGroup); map_obj.addLayer(parkGroup); }
  else{ map_obj.addLayer(welfareGroup); map_obj.addLayer(parkGroup); }

  if(radiusCircle){ map_obj.removeLayer(radiusCircle); radiusCircle=null; }
  const center=GU_CENTER[cG];
  if(center){
    // 경사 보정 ON + 일반인 제외: 구 내 평균 tobler 적용
    let radiusM = Math.round(SPEEDS[cW].mps * 30 * 60);
    let tooltipExtra = '';
    if(cSlope && cW>0){
      const gd = DONG.filter(d=>d.gu===cG);
      const avgTobler = gd.length ? gd.reduce((s,d)=>s+d.tobler,0)/gd.length : 1.0;
      radiusM = Math.round(SPEEDS[cW].mps * avgTobler * 30 * 60);
      tooltipExtra = ` (경사보정 · 구평균 tobler ${avgTobler.toFixed(3)})`;
    }
    radiusCircle = L.circle(center,{
      radius:radiusM, color:'#FF6F00', weight:2, dashArray:'8,5',
      fillColor:'#FF6F00', fillOpacity:0.04
    }).bindTooltip(`${cG} 중심 · ${SPEEDS[cW].key} 30분 반경 ~${(radiusM/1000).toFixed(2)} km${tooltipExtra}`)
      .addTo(map_obj);
    map_obj.setView(center,12,{animate:true,duration:0.4});
  }
}

// ── 구별 바차트 ────────────────────────────────────────────────────────────
function updateGuChart(){
  const guMap={};
  DONG.forEach(d=>{
    if(!guMap[d.gu]) guMap[d.gu]=[];
    guMap[d.gu].push(d);
  });
  let vals=Object.entries(guMap).map(([g,dongs])=>{
    let v;
    if     (cF==='welfare') v=dongs.reduce((s,d)=>s+getW(d),0)/dongs.length;
    else if(cF==='park')    v=dongs.reduce((s,d)=>s+getP(d),0)/dongs.length;
    else                    v=dongs.reduce((s,d)=>s+getW(d)+getP(d),0)/dongs.length;
    return {gu:g,val:v};
  });
  vals.sort((a,b)=>b.val-a.val);
  guChartObj.data.labels   = vals.map(v=>v.gu);
  guChartObj.data.datasets = [{
    data:            vals.map(v=>v.val.toFixed(2)),
    backgroundColor: vals.map(v=>v.gu===cG?'#D85A30':SPEEDS[cW].color+'aa'),
    borderRadius:3,
  }];
  guChartObj.update('none');
}

// ── 속도 비교 차트 (선택 구) ───────────────────────────────────────────────
function updateSpeedChart(){
  const gd=DONG.filter(d=>d.gu===cG);
  if(!gd.length) return;
  const n=gd.length;
  // 원본 데이터
  const wOrig = SPEEDS.map((_,i)=>(gd.reduce((s,d)=>s+d.w[i],0)/n).toFixed(2));
  const pOrig = SPEEDS.map((_,i)=>(gd.reduce((s,d)=>s+d.p[i],0)/n).toFixed(2));
  // 보정 데이터 (일반인은 원본과 동일)
  const wCorr = SPEEDS.map((_,i)=>(gd.reduce((s,d)=>s+d.wc[i],0)/n).toFixed(2));
  const pCorr = SPEEDS.map((_,i)=>(gd.reduce((s,d)=>s+d.pc[i],0)/n).toFixed(2));

  const wData = cSlope ? wCorr : wOrig;
  const pData = cSlope ? pCorr : pOrig;
  const slopeSuffix = cSlope ? ' (경사보정)' : '';

  speedChartObj.data.labels   = SPEEDS.map(s=>s.key);
  speedChartObj.data.datasets = [
    {label:`복지시설${slopeSuffix}`, data:wData, backgroundColor:'#185FA5cc', borderRadius:4},
    {label:`공원${slopeSuffix}`,     data:pData, backgroundColor:'#2E7D32cc', borderRadius:4},
  ];
  speedChartObj.update('none');
}

// ── TOP10 차트 ─────────────────────────────────────────────────────────────
function updateTop10Chart(){
  const titleEl = document.getElementById('top10Title');
  const xLabel  = document.querySelector('#top10Chart').parentElement
                   .previousElementSibling;

  if(cW===0){
    // 일반인: 도달가능점수 의미 없음 → 취약도 기준으로 fallback
    titleEl.textContent = '취약도 TOP 10 행정동';
    top10ChartObj.options.scales.x.max  = 1.05;
    top10ChartObj.options.scales.x.title.text = '취약도 지수';
    const top10=[...DONG].filter(d=>d.pop65>0)
      .sort((a,b)=>b.vuln-a.vuln).slice(0,10).reverse();
    const colors=top10.map((_,i)=>{
      const t=i/9; const r=Math.round(180+75*t); const g=Math.round(120*(1-t));
      return `rgba(${r},${g},0,0.85)`;
    });
    top10ChartObj.data.labels   = top10.map(d=>`${d.gu} ${d.dong}`);
    top10ChartObj.data.datasets = [{data:top10.map(d=>d.vuln),backgroundColor:colors,borderRadius:3}];
  } else {
    // 노인/보조/하위: 도달가능점수 기준
    const slopeTag = cSlope ? ' (경사보정)' : '';
    titleEl.textContent = `도달가능점수 하위 10 행정동${slopeTag}`;
    top10ChartObj.options.scales.x.max  = undefined;
    top10ChartObj.options.scales.x.title.text = '도달가능점수 (점)';

    // 점수가 null인 동(일반인 도달=0) 제외 후 정렬
    const scored = DONG.filter(d=>d.pop65>0 && curScore(d)!==null)
      .map(d=>({d, s:curScore(d)}))
      .sort((a,b)=>a.s-b.s).slice(0,10);

    const colors = scored.map(({s})=>{
      if(s>=80) return 'rgba(15,110,86,0.8)';
      if(s>=50) return 'rgba(133,79,11,0.8)';
      return 'rgba(163,45,45,0.85)';
    });
    top10ChartObj.data.labels   = scored.map(({d})=>`${d.gu} ${d.dong}`);
    top10ChartObj.data.datasets = [{data:scored.map(({s})=>s),backgroundColor:colors,borderRadius:3}];
  }
  top10ChartObj.update('none');
}

// ── 상세 테이블 ────────────────────────────────────────────────────────────
function updateTable(){
  const isNormal = (cW===0);
  const slopeTag = cSlope&&cW>0 ? '<span class="slope-badge">경사보정</span>' : '';

  // 정렬: 일반인→취약도 내림차순, 그외→도달가능점수 오름차순 (null 맨 끝)
  let sorted;
  if(isNormal){
    sorted = [...DONG].filter(d=>d.pop65>0).sort((a,b)=>b.vuln-a.vuln);
  } else {
    sorted = [...DONG].filter(d=>d.pop65>0).sort((a,b)=>{
      const sa=curScore(a), sb=curScore(b);
      if(sa===null && sb===null) return 0;
      if(sa===null) return 1;
      if(sb===null) return -1;
      return sa-sb;
    });
  }

  const scoreHeader = isNormal
    ? '<th>취약도</th>'
    : `<th>복지점수${slopeTag}</th><th>공원점수${slopeTag}</th>`;

  const rows=sorted.map(d=>{
    const ws=wScore(d), ps=pScore(d);
    const wCnt=getW(d), pCnt=getP(d);
    const w0style = wCnt===0 && d.w[0]>0 ? 'font-weight:600;color:#a32d2d' : '';
    const p0style = pCnt===0 && d.p[0]>0 ? 'font-weight:600;color:#a32d2d' : '';
    const scoreCell = isNormal
      ? `<td><span class="pill ${d.vuln>=0.7?'plo':d.vuln>=0.4?'pmd':'phi'}">${d.vuln.toFixed(3)}</span></td>`
      : `<td>${scorePill(ws)}</td><td>${scorePill(ps)}</td>`;
    return `<tr>
      <td>${d.gu}</td><td>${d.dong}</td>
      <td>${d.pop65.toLocaleString()}</td><td>${d.aging}%</td>
      ${scoreCell}
      <td style="${w0style}">${wCnt}</td>
      <td style="${p0style}">${pCnt}</td>
      <td style="font-size:11px;color:#888780">${d.tobler.toFixed(3)}</td>
    </tr>`;
  }).join('');

  document.getElementById('tbl').innerHTML=`
    <thead><tr>
      <th>구명</th><th>동명</th><th>65세이상</th><th>고령화율</th>
      ${scoreHeader}
      <th>복지 도달수</th><th>공원 도달수</th><th>Tobler</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  `;

  // 레이블 업데이트
  document.getElementById('tblLabel').textContent = isNormal
    ? '취약도 내림차순 · 취약도 = (복지박탈 50% + 공원박탈 50%) Min-Max 정규화'
    : `도달가능점수 오름차순 · ${SPEEDS[cW].key} 기준 · 일반인 도달 수 = 0 시 N/A${cSlope?' · 경사로 보정 적용':''}`;
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
