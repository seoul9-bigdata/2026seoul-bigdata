"""
06_medical_dashboard.py  ·  D3 의료 통합 대시보드 v2 (팀 SHIM 스타일)
──────────────────────────────────────────────────────────────────
4개 보행속도 × 3시간 × 2시설 유형을 Python에서 사전 계산.
JS에서 임의의 두 속도(A vs B)를 선택해 손실률을 동적 계산.

팀 표준 속도 (한음 외 2020):
  일반인              1.28 m/s
  일반 노인           1.12 m/s
  보행보조 노인 평균  0.88 m/s  ← 메인 비교 대상
  보행보조 노인 하위15%  0.70 m/s  ← 최약계층

출력: ../outputs/medical_dashboard.html
"""

import warnings, sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
import osmnx as ox
import networkx as nx

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

# ── 경로 ──────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parents[1]
DATA_DIR  = ROOT / "data"
OUT_DIR   = ROOT / "outputs"
PROJ_ROOT = ROOT.parent

SHP_PATH  = PROJ_ROOT / "prototype" / "끊어진서울(가제)" / "data" \
            / "bnd_oa_11_2025_2Q" / "bnd_oa_11_2025_2Q.shp"
HOSP_CSV  = DATA_DIR / "서울시 병의원 위치 정보.csv"
PHARM_CSV = DATA_DIR / "서울시 약국 인허가 정보.csv"
ELEV_SHP  = DATA_DIR / "서울시 경사도" / "표고 5000" / "N3P_F002.shp"
KIM_CACHE = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"
BOKJI_POP = PROJ_ROOT / "Bokji" / "고령자현황_20260421103806.csv"
OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── 팀 표준 파라미터 ──────────────────────────────────────────────
SPEEDS = [
    {"id": "young",  "label": "일반인",               "speed": 1.28, "color": "#1D9E75"},
    {"id": "snr0",   "label": "일반 노인",             "speed": 1.12, "color": "#185FA5"},
    {"id": "snr1",   "label": "보행보조 노인",          "speed": 0.88, "color": "#E8A838"},
    {"id": "snr2",   "label": "보행보조 노인 하위15%",  "speed": 0.70, "color": "#D85A30"},
]
TIMES  = [15, 30, 45]        # 분
FTYPES = ["hosp", "pharm"]   # all = hosp + pharm (JS에서 합산)

TOBLER_FLAT = 6.0 * np.exp(-3.5 * 0.05)

def tobler_ratio(slope: float) -> float:
    return (6.0 * np.exp(-3.5 * abs(slope + 0.05))) / TOBLER_FLAT

GU_MAP = {
    "11010": "종로구", "11020": "중구",    "11030": "용산구",
    "11040": "성동구", "11050": "광진구",  "11060": "동대문구",
    "11070": "중랑구", "11080": "성북구",  "11090": "강북구",
    "11100": "도봉구", "11110": "노원구",  "11120": "은평구",
    "11130": "서대문구","11140": "마포구", "11150": "양천구",
    "11160": "강서구", "11170": "구로구",  "11180": "금천구",
    "11190": "영등포구","11200": "동작구", "11210": "관악구",
    "11220": "서초구", "11230": "강남구",  "11240": "송파구",
    "11250": "강동구",
}

print("=" * 60)
print("D3 의료 통합 대시보드 v2")
for s in SPEEDS:
    print(f"  {s['label']}: {s['speed']} m/s")
print(f"  시간: {TIMES}분  |  시설: hosp / pharm (all=hosp+pharm)")
print("=" * 60)

# ── 1. 행정동 경계 ────────────────────────────────────────────────
print("\n[1/5] 행정동 경계 로드...")
_kim = pd.read_csv(KIM_CACHE, dtype={"dong_code": str})
DONG_NAME_MAP = dict(zip(_kim["dong_code"], _kim["dong_name"]))

gdf_oa   = gpd.read_file(str(SHP_PATH))
gdf_dong = (
    gdf_oa.dissolve(by="ADM_CD", as_index=False)
           .rename(columns={"ADM_CD": "dong_code"})
)
gdf_dong["dong_code"] = gdf_dong["dong_code"].astype(str)
gdf_dong["gu_code"]   = gdf_dong["dong_code"].str[:5]
gdf_dong["gu_name"]   = gdf_dong["gu_code"].map(GU_MAP).fillna("")
gdf_dong["dong_name"] = gdf_dong["dong_code"].map(DONG_NAME_MAP).fillna(gdf_dong["dong_code"])
gdf_dong["full_name"] = gdf_dong["gu_name"] + " " + gdf_dong["dong_name"]
gdf_dong = gdf_dong.to_crs("EPSG:5179")
gdf_dong["area_m2"] = gdf_dong.geometry.area
gdf_dong["cx"] = gdf_dong.geometry.centroid.x
gdf_dong["cy"] = gdf_dong.geometry.centroid.y
print(f"  {len(gdf_dong)}개 행정동")

# ── 1b. 경사도 보정 ───────────────────────────────────────────────
print("\n[1b] 경사도 보정 (Tobler)...")
SLOPE_OK = False
try:
    elev = gpd.read_file(str(ELEV_SHP))
    elev["HEIGHT"] = pd.to_numeric(elev["HEIGHT"], errors="coerce")
    elev = elev.dropna(subset=["HEIGHT"]).to_crs("EPSG:5179")
    ej = gpd.sjoin(
        elev[["HEIGHT","geometry"]],
        gdf_dong[["dong_code","geometry"]],
        how="left", predicate="within",
    )
    es = (
        ej.dropna(subset=["dong_code"])
          .groupby("dong_code")["HEIGHT"]
          .agg(h_min="min", h_max="max")
          .reset_index()
    )
    es["h_range"] = es["h_max"] - es["h_min"]
    gdf_dong = gdf_dong.merge(es[["dong_code","h_range"]], on="dong_code", how="left")
    gdf_dong["h_range"]   = gdf_dong["h_range"].fillna(gdf_dong["h_range"].median())
    gdf_dong["slope_est"] = gdf_dong["h_range"] / (np.sqrt(gdf_dong["area_m2"]) * 1.13)
    gdf_dong["t_ratio"]   = gdf_dong["slope_est"].apply(tobler_ratio)
    avg_tobler = float(gdf_dong["t_ratio"].mean())
    SLOPE_OK = True
    print(f"  경사 보정 완료 — 평균 ratio: {avg_tobler:.3f}")
except Exception as e:
    print(f"  경사 보정 실패 ({e}) → 평지 사용")
    gdf_dong["t_ratio"] = 1.0
    avg_tobler = 1.0

# ── 1c. 고령 인구 ─────────────────────────────────────────────────
print("\n[1c] 고령 인구 로드...")
try:
    _bdf = pd.read_csv(BOKJI_POP, encoding="utf-8-sig", header=None, skiprows=4, dtype=str)
    _bdf.columns = [
        "level1","gu_name","dong_name","total_pop","m","f",
        "elderly_65","em","ef","ek","ekm","ekf","efg","efm","eff",
    ]
    _bdf = _bdf[_bdf["dong_name"] != "소계"].copy()
    for c in ["total_pop","elderly_65"]:
        _bdf[c] = pd.to_numeric(_bdf[c].str.replace(",",""), errors="coerce")
    _bdf_dong = (
        _bdf.dropna(subset=["elderly_65"])
            .groupby(["gu_name","dong_name"])[["total_pop","elderly_65"]]
            .sum().reset_index()
    )
    gdf_dong = gdf_dong.merge(_bdf_dong, on=["gu_name","dong_name"], how="left")
    gdf_dong["elderly_65"] = gdf_dong["elderly_65"].fillna(
        gdf_dong["gu_name"].map(gdf_dong.groupby("gu_name")["elderly_65"].sum()) /
        gdf_dong["gu_name"].map(gdf_dong.groupby("gu_name")["dong_code"].count())
    )
    print(f"  완료 ({gdf_dong['elderly_65'].notna().sum()}/{len(gdf_dong)}개 동 매칭)")
except Exception as e:
    print(f"  실패 ({e})")
    gdf_dong["elderly_65"] = np.nan

# ── 2. 의료시설 로드 ──────────────────────────────────────────────
print("\n[2/5] 의료시설 로드...")
hosp_raw = pd.read_csv(HOSP_CSV, encoding="cp949")
hosp = hosp_raw[hosp_raw["병원분류명"].isin(["의원","병원","보건소","종합병원"])].copy()
hosp = hosp.dropna(subset=["병원경도","병원위도"])
hosp = hosp[(hosp["병원경도"] > 120) & (hosp["병원위도"] > 35)]
th = Transformer.from_crs("EPSG:4326","EPSG:5179",always_xy=True)
hosp["hx"], hosp["hy"] = th.transform(hosp["병원경도"].values, hosp["병원위도"].values)

pharm_raw = pd.read_csv(PHARM_CSV, encoding="cp949")
pharm = pharm_raw[
    (pharm_raw["영업상태명"] == "영업/정상") &
    pharm_raw["도로명주소"].str.startswith("서울", na=False)
].copy()
pharm["px"] = pd.to_numeric(pharm["좌표정보(X)"].astype(str).str.strip(), errors="coerce")
pharm["py"] = pd.to_numeric(pharm["좌표정보(Y)"].astype(str).str.strip(), errors="coerce")
pharm = pharm.dropna(subset=["px","py"])
pharm = pharm[(pharm["px"] > 100000) & (pharm["py"] > 300000)]
tp = Transformer.from_crs("EPSG:5174","EPSG:5179",always_xy=True)
pharm["hx"], pharm["hy"] = tp.transform(pharm["px"].values, pharm["py"].values)
print(f"  병의원: {len(hosp):,}개, 약국: {len(pharm):,}개")

# ── 3. 거리 행렬 (OSM 보행 네트워크 + 다익스트라) ────────────────────
print("\n[3/5] OSM 보행 네트워크 거리 행렬...")

cx = gdf_dong["cx"].values
cy = gdf_dong["cy"].values
tr = gdf_dong["t_ratio"].values

GRAPH_PATH = CACHE_DIR / "seoul_walk.graphml"
DH_PATH    = CACHE_DIR / "DH_osm.npy"
DP_PATH    = CACHE_DIR / "DP_osm.npy"
MAX_RADIUS = float(1.28 * 45 * 60)   # 3,456 m (최대 반경: 일반인 45분)

# 3a. 그래프 로드 or 다운로드
if GRAPH_PATH.exists():
    print(f"  캐시 로드: {GRAPH_PATH.name}")
    G = ox.load_graphml(str(GRAPH_PATH))
else:
    print("  서울 보행 네트워크 다운로드 (최초 1회, 3~10분 소요)...")
    G = ox.graph_from_place("서울특별시, 대한민국", network_type="walk")
    ox.save_graphml(G, str(GRAPH_PATH))
    print(f"  저장 완료: {GRAPH_PATH.name}")

G_proj = ox.project_graph(G, to_crs="EPSG:5179")
print(f"  노드 {G_proj.number_of_nodes():,}개 · 엣지 {G_proj.number_of_edges():,}개")

# 3b. 동 centroid + 시설 → 최근접 네트워크 노드
print("  최근접 노드 매핑...")
dong_node_ids  = list(ox.nearest_nodes(G_proj, X=cx,                 Y=cy))
hosp_node_ids  = list(ox.nearest_nodes(G_proj, X=hosp["hx"].values,  Y=hosp["hy"].values))
pharm_node_ids = list(ox.nearest_nodes(G_proj, X=pharm["hx"].values, Y=pharm["hy"].values))

n_dong, n_hosp, n_pharm = len(cx), len(hosp), len(pharm)

# 3c. 거리 행렬 계산 (캐시 우선)
if DH_PATH.exists() and DP_PATH.exists():
    print("  거리 행렬 캐시 로드...")
    DH = np.load(str(DH_PATH))
    DP = np.load(str(DP_PATH))
else:
    print(f"  Dijkstra 계산 중 — {n_dong}개 동 centroid, cutoff {MAX_RADIUS:.0f} m")
    print("  ※ 최초 실행 시 30~60분 소요. 이후 cache에서 즉시 로드됩니다.")
    DH = np.full((n_dong, n_hosp),  MAX_RADIUS + 1, dtype=np.float32)
    DP = np.full((n_dong, n_pharm), MAX_RADIUS + 1, dtype=np.float32)

    t0 = time.time()
    for i, src in enumerate(dong_node_ids):
        try:
            lengths = dict(nx.single_source_dijkstra_path_length(
                G_proj, src, cutoff=MAX_RADIUS, weight="length"
            ))
        except Exception:
            continue
        DH[i] = [lengths.get(n, MAX_RADIUS + 1) for n in hosp_node_ids]
        DP[i] = [lengths.get(n, MAX_RADIUS + 1) for n in pharm_node_ids]
        if (i + 1) % 50 == 0 or i == n_dong - 1:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (n_dong - i - 1)
            print(f"    {i+1}/{n_dong} 완료  경과 {elapsed/60:.1f}분  남은 시간 ~{eta/60:.1f}분")

    np.save(str(DH_PATH), DH)
    np.save(str(DP_PATH), DP)
    print(f"  캐시 저장 완료 (DH {DH_PATH.name}, DP {DP_PATH.name})")

print(f"  DH={DH.shape}, DP={DP.shape}")

# ── 4. 사전 계산: 4속도 × 3시간 × 2시설 ─────────────────────────
print("\n[4/5] 시설 도달 수 사전 계산...")

COUNTS: dict = {}   # {"young_30_hosp": {"1101051500": 45, ...}, ...}

for sp in SPEEDS:
    for tmin in TIMES:
        r = sp["speed"] * tmin * 60 * tr          # 동별 반경 (m)
        nh = (DH <= r[:, None]).sum(axis=1)        # 병의원 카운트
        np_ = (DP <= r[:, None]).sum(axis=1)       # 약국 카운트 (np 충돌 방지)
        for ftype, counts in [("hosp", nh), ("pharm", np_)]:
            key = f"{sp['id']}_{tmin}_{ftype}"
            COUNTS[key] = {
                dc: int(counts[i])
                for i, dc in enumerate(gdf_dong["dong_code"].tolist())
            }
        print(f"  {sp['id']}_{tmin}: 병의원 평균 {nh.mean():.1f}개, 약국 평균 {np_.mean():.1f}개")

# ── 4b. 행정동 메타데이터 (정적) ─────────────────────────────────
DONG_META = {
    row["dong_code"]: {
        "fn": row["full_name"],
        "gu": row["gu_name"],
        "el": int(row["elderly_65"]) if not pd.isna(row.get("elderly_65", float("nan"))) else 0,
    }
    for _, row in gdf_dong.iterrows()
}

# ── 5. GeoJSON ────────────────────────────────────────────────────
print("\n[5/5] GeoJSON 생성...")
gdf_wgs = gdf_dong[["dong_code","geometry"]].to_crs("EPSG:4326").copy()
gdf_wgs["geometry"] = gdf_wgs.geometry.simplify(0.0001)

geo = json.loads(gdf_wgs.to_json())

def _rnd(c):
    if isinstance(c[0], list):
        return [_rnd(x) for x in c]
    return [round(c[0], 5), round(c[1], 5)]

for feat in geo["features"]:
    feat["geometry"]["coordinates"] = _rnd(feat["geometry"]["coordinates"])
    feat["properties"] = {"dc": feat["properties"]["dong_code"]}

geo_str    = json.dumps(geo,       ensure_ascii=False, separators=(',',':'))
counts_str = json.dumps(COUNTS,    ensure_ascii=False, separators=(',',':'))
meta_str   = json.dumps(DONG_META, ensure_ascii=False, separators=(',',':'))
speeds_str = json.dumps(SPEEDS,    ensure_ascii=False, separators=(',',':'))

print(f"  GeoJSON:    {len(geo_str)//1024} KB")
print(f"  COUNTS:     {len(counts_str)//1024} KB")
print(f"  DONG_META:  {len(meta_str)//1024} KB")
print(f"  avg_tobler: {avg_tobler:.4f}")

# ─────────────────────────────────────────────────────────────────
# HTML 템플릿
# ─────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>노인 보행일상권 — ③ 의료 접근성</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
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
.btn.on{color:#f1efe8;border-color:transparent}
.bw{border-radius:8px}
.divider{width:100%;height:0.5px;background:#e8e6e0;margin:8px 0}
.sgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:12px}
.sc{background:#f5f4f0;border-radius:8px;padding:12px 14px}
.sl{font-size:11px;color:#888780;margin-bottom:3px}
.sv{font-size:22px;font-weight:500}
.ss{font-size:11px;color:#888780;margin-top:2px}
/* 속도 거리 바 */
.dist-wrap{margin-top:14px;border-top:0.5px solid #e8e6e0;padding-top:12px}
.dist-title{font-size:11px;font-weight:500;letter-spacing:.06em;color:#888780;text-transform:uppercase;margin-bottom:10px}
.dbar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.dbar-row:last-child{margin-bottom:0}
.dbar-meta{width:160px;flex-shrink:0;display:flex;align-items:center;gap:6px}
.dbar-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.dbar-name{font-size:11px;color:#5f5e5a;white-space:nowrap;flex:1}
.dbar-track{flex:1;background:#f0ede8;border-radius:4px;height:10px;overflow:hidden;position:relative}
.dbar-fill{height:100%;border-radius:4px;transition:width .35s ease}
.dbar-badge{font-size:10px;font-weight:500;padding:1px 7px;border-radius:10px;background:#f0ede8;margin-left:4px}
.dbar-val{font-size:11px;color:#5f5e5a;width:72px;text-align:right;flex-shrink:0}
/* 레이아웃 */
.r2{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px}
.r2b{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 18px}
.ct{font-size:11px;font-weight:500;letter-spacing:.06em;color:#888780;text-transform:uppercase;margin-bottom:10px}
#map-wrap{position:relative;height:420px;border-radius:8px;overflow:hidden;background:#e8e4db}
#map{position:absolute;inset:0;height:100%!important}
.leg{display:flex;gap:10px;flex-wrap:wrap;margin-top:9px;align-items:center}
.li{display:flex;align-items:center;gap:5px;font-size:11px;color:#5f5e5a}
.ld{width:10px;height:10px;border-radius:2px;flex-shrink:0}
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
.chart-wrap{position:relative;width:100%}
.tbl-wrap{overflow-x:auto;max-height:360px;overflow-y:auto}
@media(max-width:900px){.r2,.r2b,.sgrid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>③ 의료 — 노인 보행일상권 의료 접근성 분석</h1>
  <p>병의원·보건소·약국 대상 · 서울 426개 행정동 · OSM 보행 네트워크 + Tobler 경사 보정 (EPSG:5179)</p>
</header>

<div class="wrap">

  <!-- ① 컨트롤 패널 -->
  <div class="ctrl">
    <!-- 기준 A -->
    <div class="crow">
      <span class="lbl" style="width:72px">기준 (A)</span>
      <button class="btn bw on" style="--c:#1D9E75" id="a0" onclick="setA(0,this)">🚶 일반인 &nbsp;1.28 m/s</button>
      <button class="btn bw"                        id="a1" onclick="setA(1,this)">🧓 일반 노인 &nbsp;1.12 m/s</button>
      <button class="btn bw"                        id="a2" onclick="setA(2,this)">🦽 보행보조 노인 &nbsp;0.88 m/s</button>
      <button class="btn bw"                        id="a3" onclick="setA(3,this)">♿ 보행보조 노인 하위15% &nbsp;0.70 m/s</button>
    </div>
    <!-- 비교 B -->
    <div class="crow">
      <span class="lbl" style="width:72px">비교 (B)</span>
      <button class="btn bw"                        id="b0" onclick="setB(0,this)">🚶 일반인 &nbsp;1.28 m/s</button>
      <button class="btn bw"                        id="b1" onclick="setB(1,this)">🧓 일반 노인 &nbsp;1.12 m/s</button>
      <button class="btn bw on" style="--c:#E8A838" id="b2" onclick="setB(2,this)">🦽 보행보조 노인 &nbsp;0.88 m/s</button>
      <button class="btn bw"                        id="b3" onclick="setB(3,this)">♿ 보행보조 노인 하위15% &nbsp;0.70 m/s</button>
    </div>
    <div class="divider"></div>
    <!-- 시간 + 시설 -->
    <div class="crow">
      <span class="lbl">보행 시간</span>
      <button class="btn on" data-t="15" onclick="setT(15,this)">15분</button>
      <button class="btn" data-t="30" onclick="setT(30,this)">30분</button>
      <button class="btn" data-t="45" onclick="setT(45,this)">45분</button>
      <span style="flex:1"></span>
      <span class="lbl">시설 유형</span>
      <button class="btn bw on" onclick="setF('all',this)">전체</button>
      <button class="btn bw" onclick="setF('hosp',this)">병의원</button>
      <button class="btn bw" onclick="setF('pharm',this)">약국</button>
    </div>
    <!-- 통계 카드 -->
    <div class="sgrid" id="sg"></div>
    <!-- 속도별 보행 가능 거리 바 -->
    <div class="dist-wrap">
      <div class="dist-title">보행 가능 거리 비교 (경사 보정 평균 기준)</div>
      <div id="dbars"></div>
    </div>
  </div>

  <!-- ② 지도 + 산점도 -->
  <div class="r2">
    <div class="card">
      <div class="ct" id="mapTitle">행정동별 의료 접근성 손실률 (A vs B)</div>
      <div id="map-wrap"><div id="map"></div></div>
      <div class="leg" id="mapleg"></div>
      <p class="src">출처: 서울 열린데이터광장 병의원·약국 위치정보 · 경사도: 국토지리정보원 N3P_F002<br>
        ※ 손실률(%) = (1 − B 도달 수 / A 도달 수) × 100 · 동 centroid 기준 OSM 보행 네트워크(다익스트라) + Tobler 경사 보정</p>
    </div>
    <div class="card">
      <div class="ct" id="scTitle">A vs B 접근 가능 시설 수 (행정동별)</div>
      <div class="chart-wrap" style="height:360px"><canvas id="sc"></canvas></div>
      <div class="leg" style="margin-top:8px">
        <div class="li"><div class="ld" style="background:#d73027;opacity:.7"></div>손실 60%+</div>
        <div class="li"><div class="ld" style="background:#fc7050;opacity:.7"></div>40–60%</div>
        <div class="li"><div class="ld" style="background:#fee08b;opacity:.7"></div>20–40%</div>
        <div class="li"><div class="ld" style="background:#91cf60;opacity:.7"></div>0–20%</div>
        <div class="li"><div class="ld" style="background:#4292c6;opacity:.7"></div>B &gt; A</div>
        <div class="li" style="font-size:10px;color:#888">주황점선=이론선</div>
      </div>
    </div>
  </div>

  <!-- ③ 구별 바차트 + TOP 10 -->
  <div class="r2b">
    <div class="card">
      <div class="ct">구별 평균 의료 접근 손실률 (A vs B)</div>
      <div class="chart-wrap" style="height:560px"><canvas id="gc"></canvas></div>
    </div>
    <div class="card">
      <div class="tabs">
        <button class="tab on" onclick="setTopTab('impact',this)">영향 노인 수 TOP 10동</button>
        <button class="tab" onclick="setTopTab('loss',this)">손실률 TOP 10동</button>
      </div>
      <div class="chart-wrap" style="height:520px"><canvas id="ic"></canvas></div>
    </div>
  </div>

  <!-- ④ 상세표 -->
  <div class="card">
    <div class="ct">행정동별 의료 접근성 상세 (손실률 높은 순)</div>
    <div class="tbl-wrap"><table id="tbl"></table></div>
    <p class="src">손실률(%) = (1 − B 도달 수 / A 도달 수) × 100 &nbsp;|&nbsp;
      영향 노인 수 = 손실률 × 동별 65세 이상 인구 / 100</p>
  </div>

  <div class="note" id="noteBox"></div>
</div>

<script>
/* ───────── 임베드 데이터 ───────── */
const GEOJSON   = __GEOJSON__;
const COUNTS    = __COUNTS__;
const DONG_META = __DONG_META__;
const SPEEDS    = __SPEEDS__;
const AVG_TOBLER = __AVG_TOBLER__;

/* ───────── 상태 ───────── */
let cA = 0, cB = 2, cT = 15, cF = 'all', cTop = 'impact';

/* ───────── 헬퍼: 시설 수 조회 ───────── */
function getN(speedId, time, ftype, dc) {
  if (ftype === 'all') {
    return (COUNTS[speedId+'_'+time+'_hosp'][dc] || 0)
         + (COUNTS[speedId+'_'+time+'_pharm'][dc] || 0);
  }
  return COUNTS[speedId+'_'+time+'_'+ftype][dc] || 0;
}

function dongLoss(dc) {
  const nA = getN(SPEEDS[cA].id, cT, cF, dc);
  const nB = getN(SPEEDS[cB].id, cT, cF, dc);
  return nA > 0 ? (1 - nB / nA) * 100 : 0;
}

/* ───────── 컬러 ───────── */
function lossColor(v) {
  if (v < 0)   return '#4292c6';   // B > A: 파란색
  if (v >= 70) return '#67000D';
  if (v >= 60) return '#a50026';
  if (v >= 50) return '#d73027';
  if (v >= 40) return '#fc7050';
  if (v >= 30) return '#fdbb84';
  if (v >= 20) return '#fee0b6';
  return '#FFF5F0';
}
function ptColor(v) {
  if (v < 0)   return 'rgba(66,146,198,.75)';
  if (v >= 60) return 'rgba(215,48,39,.75)';
  if (v >= 40) return 'rgba(252,112,80,.75)';
  if (v >= 20) return 'rgba(254,224,139,.85)';
  return 'rgba(145,207,96,.75)';
}

/* ───────── 전체 동 손실 계산 ───────── */
function allDongLoss() {
  return Object.keys(DONG_META).map(dc => {
    const nA = getN(SPEEDS[cA].id, cT, cF, dc);
    const nB = getN(SPEEDS[cB].id, cT, cF, dc);
    const loss = nA > 0 ? (1 - nB / nA) * 100 : 0;
    const m = DONG_META[dc];
    return { dc, fn: m.fn, gu: m.gu, el: m.el, nA, nB, loss,
             impact: Math.round(Math.max(0, loss) / 100 * m.el) };
  });
}

/* ───────── 구별 집계 ───────── */
function guStats(rows) {
  const byGu = {};
  rows.filter(r => r.nA > 0).forEach(r => {
    if (!byGu[r.gu]) byGu[r.gu] = { sum: 0, cnt: 0, impact: 0 };
    byGu[r.gu].sum    += r.loss;
    byGu[r.gu].cnt    += 1;
    byGu[r.gu].impact += r.impact;
  });
  return Object.entries(byGu)
    .map(([gu, v]) => ({ gu, lo: v.sum / v.cnt, im: v.impact }))
    .sort((a, b) => b.lo - a.lo);
}

/* ───────── Leaflet 지도 ───────── */
const mapEl = L.map('map', {zoomControl:true, attributionControl:false})
  .setView([37.5665, 126.978], 11);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  {maxZoom:18}).addTo(mapEl);

let geoLayer = null;

function styleFeature(feat) {
  return {
    fillColor:   lossColor(dongLoss(feat.properties.dc)),
    color:       'rgba(80,80,80,0.25)',
    weight:      0.5,
    fillOpacity: 0.82,
  };
}

function tooltipContent(feat) {
  const dc = feat.properties.dc;
  const m = DONG_META[dc];
  if (!m) return '';
  const nA = getN(SPEEDS[cA].id, cT, cF, dc);
  const nB = getN(SPEEDS[cB].id, cT, cF, dc);
  const loss = nA > 0 ? (1 - nB / nA) * 100 : 0;
  const impact = Math.round(Math.max(0, loss) / 100 * m.el);
  return `<b>${m.fn}</b><br>`
       + `손실률: <b>${loss.toFixed(1)}%</b><br>`
       + `A(${SPEEDS[cA].label}) ${nA}개 → B(${SPEEDS[cB].label}) ${nB}개<br>`
       + `영향 노인 수: 약 ${impact.toLocaleString()}명`;
}

function buildMap() {
  if (geoLayer) { refreshMap(); return; }
  geoLayer = L.geoJSON(GEOJSON, {
    style: styleFeature,
    onEachFeature: (feat, layer) => {
      layer.bindTooltip(tooltipContent(feat), {sticky:true});
      layer.on('mouseover', function() {
        this.setStyle({weight:2, color:'#FFD700', fillOpacity:.95});
      });
      layer.on('mouseout', function() { geoLayer.resetStyle(this); });
    },
  }).addTo(mapEl);
}

function refreshMap() {
  if (!geoLayer) { buildMap(); return; }
  geoLayer.setStyle(styleFeature);
  geoLayer.eachLayer(l => l.setTooltipContent(tooltipContent(l.feature)));
}

function buildLegend() {
  const steps = [
    {v:'B > A', c:'#4292c6'},{v:'~20%', c:'#FFF5F0', b:'1px solid #ccc'},
    {v:'20–30%', c:'#fee0b6'},{v:'30–40%', c:'#fdbb84'},
    {v:'40–50%', c:'#fc7050'},{v:'50–60%', c:'#d73027'},
    {v:'60–70%', c:'#a50026'},{v:'70%+', c:'#67000D'},
  ];
  document.getElementById('mapleg').innerHTML =
    steps.map(s =>
      `<div class="li"><div class="ld" style="background:${s.c};${s.b||''}"></div>${s.v}</div>`
    ).join('');
}

/* ───────── 속도 거리 바 ───────── */
function updateDistBars() {
  const maxDist = 1.28 * cT * 60 * AVG_TOBLER;
  const rows = SPEEDS.map((s, i) => {
    const dist = Math.round(s.speed * cT * 60 * AVG_TOBLER);
    const pct  = dist / (1.28 * cT * 60) * 100;  // relative to flat young
    const isA  = (i === cA), isB = (i === cB);
    const badge = isA ? `<span class="dbar-badge" style="background:${s.color}20;color:${s.color}">A</span>`
                : isB ? `<span class="dbar-badge" style="background:${s.color}20;color:${s.color}">B</span>`
                : '';
    const opacity = (isA || isB) ? '1' : '0.4';
    return `<div class="dbar-row" style="opacity:${opacity}">
      <div class="dbar-meta">
        <div class="dbar-dot" style="background:${s.color}"></div>
        <span class="dbar-name">${s.label}</span>
        ${badge}
      </div>
      <div class="dbar-track">
        <div class="dbar-fill" style="width:${pct}%;background:${s.color}"></div>
      </div>
      <span class="dbar-val">${dist.toLocaleString()} m</span>
    </div>`;
  }).join('');
  document.getElementById('dbars').innerHTML = rows;
}

/* ───────── 통계 카드 ───────── */
function updateStats(rows) {
  const valid = rows.filter(r => r.nA > 0);
  const meanLoss   = valid.length ? valid.reduce((s, r) => s + r.loss, 0) / valid.length : 0;
  const totalImpact = rows.reduce((s, r) => s + r.impact, 0);
  const rA = Math.round(SPEEDS[cA].speed * cT * 60 * AVG_TOBLER);
  const rB = Math.round(SPEEDS[cB].speed * cT * 60 * AVG_TOBLER);
  const theory = (1 - (SPEEDS[cB].speed / SPEEDS[cA].speed) ** 2) * 100;

  document.getElementById('sg').innerHTML = `
    <div class="sc">
      <div class="sl">기준 A 평균 반경</div>
      <div class="sv" style="color:${SPEEDS[cA].color}">${rA.toLocaleString()} m</div>
      <div class="ss">${SPEEDS[cA].speed} m/s · ${cT}분 · 경사 보정</div>
    </div>
    <div class="sc">
      <div class="sl">비교 B 평균 반경</div>
      <div class="sv" style="color:${SPEEDS[cB].color}">${rB.toLocaleString()} m</div>
      <div class="ss">${SPEEDS[cB].speed} m/s · ${cT}분 · 경사 보정</div>
    </div>
    <div class="sc">
      <div class="sl">평균 손실률 (A→B)</div>
      <div class="sv" style="color:#d73027">${meanLoss.toFixed(1)}%</div>
      <div class="ss">이론값 ${theory.toFixed(1)}% (속도비 제곱)</div>
    </div>
    <div class="sc">
      <div class="sl">영향 노인 수 (추정)</div>
      <div class="sv">${(totalImpact / 10000).toFixed(1)}<span style="font-size:14px;font-weight:400">만명</span></div>
      <div class="ss">손실률 × 동별 65세 이상 인구</div>
    </div>`;
}

/* ───────── 제목 + 노트 업데이트 ───────── */
function updateLabels() {
  const a = SPEEDS[cA], b = SPEEDS[cB];
  document.getElementById('mapTitle').textContent =
    `행정동별 의료 접근성 손실률 — ${a.label} (A) vs ${b.label} (B)`;
  document.getElementById('scTitle').textContent =
    `A(${a.label}) vs B(${b.label}) 접근 가능 시설 수`;
  const theory = (1 - (b.speed / a.speed) ** 2) * 100;
  document.getElementById('noteBox').innerHTML =
    `※ <b>${a.label} (${a.speed} m/s)</b>를 기준(A)으로,
     <b>${b.label} (${b.speed} m/s)</b>를 비교(B)합니다.<br>
     ※ 이론 손실률 = 1 − (${b.speed} / ${a.speed})² = <b>${theory.toFixed(1)}%</b>
      · 경사 보정(Tobler) 동등 적용 → 실측값이 이론값과 근접하면 모델 정상<br>
     ※ 거리 측정: 동 centroid 기준 OSM 보행 네트워크(다익스트라) + Tobler 경사 보정 (EPSG:5179)`;
}

/* ───────── A/B 버튼 색 동기화 ───────── */
function syncBtnColors() {
  ['a','b'].forEach(prefix => {
    SPEEDS.forEach((s, i) => {
      const btn = document.getElementById(prefix + i);
      const idx = prefix === 'a' ? cA : cB;
      if (i === idx) {
        btn.style.background = s.color;
        btn.style.borderColor = s.color;
        btn.classList.add('on');
      } else {
        btn.style.background = '';
        btn.style.borderColor = '';
        btn.classList.remove('on');
      }
    });
  });
}

/* ───────── Chart.js ───────── */
let scChart, gcChart, icChart;

function initCharts(rows) {
  const sData = rows.filter(r => r.nA > 0 && r.nB >= 0);
  const ratio  = SPEEDS[cB].speed / SPEEDS[cA].speed;
  const maxV   = Math.max(...sData.map(r => r.nA), 1) + 5;

  scChart = new Chart(document.getElementById('sc'), {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: '행정동',
          data: sData.map(r => ({x: r.nA, y: r.nB, lo: r.loss, fn: r.fn})),
          backgroundColor: sData.map(r => ptColor(r.loss)),
          pointRadius: 4, pointHoverRadius: 6,
        },
        {
          label: '손실 0% (y=x)',
          data: [{x:0,y:0},{x:maxV,y:maxV}],
          type:'line', borderColor:'#aaa', borderWidth:1,
          borderDash:[4,4], pointRadius:0, fill:false,
        },
        {
          label: `이론선 (${ratio.toFixed(2)}²)`,
          data: [{x:0,y:0},{x:maxV,y:maxV*ratio*ratio}],
          type:'line', borderColor:'#ff8c00', borderWidth:1.5,
          borderDash:[6,3], pointRadius:0, fill:false,
        },
      ],
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{display:false},
        tooltip:{callbacks:{
          label: ctx => {
            const p = ctx.raw;
            if (p.fn) return [p.fn,
              `A ${p.x}개 → B ${p.y}개`,
              `손실: ${p.lo.toFixed(1)}%`];
            return ctx.dataset.label;
          },
        }},
      },
      scales:{
        x:{title:{display:true,text:`A(${SPEEDS[cA].label}) 도달 시설 수`,font:{size:11}},grid:{color:'#f0f0ee'}},
        y:{title:{display:true,text:`B(${SPEEDS[cB].label}) 도달 시설 수`,font:{size:11}},grid:{color:'#f0f0ee'}},
      },
    },
  });

  const gl = guStats(rows);
  gcChart = new Chart(document.getElementById('gc'), {
    type:'bar',
    data:{
      labels: gl.map(r=>r.gu),
      datasets:[{
        data: gl.map(r=>r.lo),
        backgroundColor: gl.map(r=>lossColor(r.lo)),
        borderWidth:0,
      }],
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:ctx=>`손실률: ${ctx.raw.toFixed(1)}%`}}},
      scales:{
        x:{min:0, max:100, grid:{color:'#f0f0ee'},
           ticks:{callback:v=>v+'%'},
           title:{display:true,text:'평균 손실률(%)',font:{size:11}}},
        y:{ticks:{font:{size:11}}},
      },
    },
  });

  buildTopChart(rows);
}

function buildTopChart(rows) {
  const isImpact = (cTop === 'impact');
  const sorted = isImpact
    ? rows.filter(r=>r.impact>0).sort((a,b)=>b.impact-a.impact).slice(0,10)
    : rows.filter(r=>r.nA>0).sort((a,b)=>b.loss-a.loss).slice(0,10);
  const labels = sorted.map(r=>r.fn);
  const vals   = isImpact ? sorted.map(r=>r.impact) : sorted.map(r=>r.loss);
  const colors = isImpact
    ? sorted.map((_,i)=>`hsl(${10+i*4},68%,${42+i*3}%)`)
    : sorted.map(r=>lossColor(r.loss));

  if (icChart) icChart.destroy();
  icChart = new Chart(document.getElementById('ic'), {
    type:'bar',
    data:{
      labels,
      datasets:[{
        data: vals,
        backgroundColor: colors,
        borderWidth:0,
      }],
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{
          label:ctx=>isImpact?`약 ${ctx.raw.toLocaleString()}명`:`${ctx.raw.toFixed(1)}%`,
        }}},
      scales:{
        x:{grid:{color:'#f0f0ee'},
           title:{display:true,text:isImpact?'영향 노인 수(명)':'손실률(%)',font:{size:11}}},
        y:{ticks:{font:{size:11}}},
      },
    },
  });
}

function refreshCharts(rows) {
  const sData = rows.filter(r => r.nA > 0 && r.nB >= 0);
  const ratio  = SPEEDS[cB].speed / SPEEDS[cA].speed;
  const maxV   = Math.max(...sData.map(r => r.nA), 1) + 5;

  scChart.data.datasets[0].data            = sData.map(r=>({x:r.nA,y:r.nB,lo:r.loss,fn:r.fn}));
  scChart.data.datasets[0].backgroundColor = sData.map(r=>ptColor(r.loss));
  scChart.data.datasets[1].data = [{x:0,y:0},{x:maxV,y:maxV}];
  scChart.data.datasets[2].data = [{x:0,y:0},{x:maxV,y:maxV*ratio*ratio}];
  scChart.data.datasets[2].label = `이론선 (${ratio.toFixed(2)}²)`;
  scChart.options.scales.x.title.text = `A(${SPEEDS[cA].label}) 도달 시설 수`;
  scChart.options.scales.y.title.text = `B(${SPEEDS[cB].label}) 도달 시설 수`;
  scChart.update('none');

  const gl = guStats(rows);
  gcChart.data.labels                       = gl.map(r=>r.gu);
  gcChart.data.datasets[0].data            = gl.map(r=>r.lo);
  gcChart.data.datasets[0].backgroundColor = gl.map(r=>lossColor(r.lo));
  gcChart.update('none');

  buildTopChart(rows);
}

/* ───────── 테이블 ───────── */
function updateTable(rows) {
  const sorted = rows.filter(r=>r.nA>0).sort((a,b)=>b.loss-a.loss).slice(0, 100);
  document.getElementById('tbl').innerHTML =
    `<thead><tr>
      <th>행정동</th><th>손실률(%)</th><th>A(기준)</th><th>B(비교)</th>
      <th>영향 노인 수</th><th>등급</th>
    </tr></thead>
    <tbody>${sorted.map(r=>{
      const g = r.loss>=60?'<span class="pill plo">심각</span>':
                r.loss>=40?'<span class="pill pmd">주의</span>':
                r.loss<0?'<span class="pill phi">B우위</span>':
                '<span class="pill phi">양호</span>';
      return `<tr>
        <td>${r.fn}</td>
        <td><b>${r.loss.toFixed(1)}%</b></td>
        <td>${r.nA}</td><td>${r.nB}</td>
        <td>${r.el>0?r.impact.toLocaleString()+'명':'-'}</td>
        <td>${g}</td>
      </tr>`;
    }).join('')}</tbody>`;
}

/* ───────── 컨트롤 핸들러 ───────── */
function setA(idx, btn) {
  cA = idx;
  if (cA === cB) { cB = cA === SPEEDS.length-1 ? 0 : cA+1; }
  syncBtnColors();
  update();
}
function setB(idx, btn) {
  cB = idx;
  if (cA === cB) { cA = cB === 0 ? SPEEDS.length-1 : cB-1; }
  syncBtnColors();
  update();
}
function setT(t, btn) {
  document.querySelectorAll('.ctrl .crow:nth-child(3) .btn:not(.bw)')
          .forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  cT = t;
  update();
}
function setF(f, btn) {
  document.querySelectorAll('.ctrl .crow:nth-child(3) .btn.bw')
          .forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  cF = f;
  update();
}
function setTopTab(tab, btn) {
  document.querySelectorAll('.tabs .tab').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  cTop = tab;
  buildTopChart(allDongLoss());
}

/* ───────── 전체 업데이트 ───────── */
let _initialized = false;

function update() {
  updateLabels();
  updateDistBars();
  const rows = allDongLoss();
  updateStats(rows);
  refreshMap();
  if (!_initialized) {
    initCharts(rows);
    _initialized = true;
  } else {
    refreshCharts(rows);
  }
  updateTable(rows);
}

/* ───────── 초기화 ───────── */
buildMap();
buildLegend();
syncBtnColors();
update();
</script>
</body>
</html>
"""

html = (HTML_TEMPLATE
        .replace("__GEOJSON__",    geo_str)
        .replace("__COUNTS__",     counts_str)
        .replace("__DONG_META__",  meta_str)
        .replace("__SPEEDS__",     speeds_str)
        .replace("__AVG_TOBLER__", str(round(avg_tobler, 4))))

out = OUT_DIR / "medical_dashboard.html"
out.write_text(html, encoding="utf-8")

print("\n" + "=" * 60)
print(f"저장 완료: {out}")
print(f"파일 크기: {out.stat().st_size // 1024} KB")
print("=" * 60)
