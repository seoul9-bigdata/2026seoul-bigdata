"""
06_medical_dashboard.py  ·  D3 의료 통합 대시보드 v3
──────────────────────────────────────────────────────────────────
변경사항 (v3):
  - 손실률 → 도달가능점수 (nB / nA × 100)  기준A는 일반인으로 고정
  - 경사 보정 여부 토글 (tobler_ratio_LEE.csv 활용)
  - 기준 A = 일반인 고정 (버튼 제거)
  - conclusion_medical_LEE.csv 생성 (구 단위, 30분 기준)

팀 표준 속도 (한음 외 2020):
  일반인              1.28 m/s
  일반 노인           1.12 m/s
  보행보조 노인 평균  0.88 m/s
  보행보조 노인 하위15%  0.70 m/s

출력:
  ../outputs/medical_dashboard.html
  ../outputs/conclusion_medical_LEE.csv
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
ROOT       = Path(__file__).resolve().parents[1]
DATA_DIR   = ROOT / "data"
OUT_DIR    = ROOT / "outputs"
PROJ_ROOT  = ROOT.parent

SHP_PATH   = PROJ_ROOT / "prototype" / "끊어진서울(가제)" / "data" \
             / "bnd_oa_11_2025_2Q" / "bnd_oa_11_2025_2Q.shp"
HOSP_CSV   = DATA_DIR / "서울시 병의원 위치 정보.csv"
PHARM_CSV  = DATA_DIR / "서울시 약국 인허가 정보.csv"
TOBLER_CSV = OUT_DIR  / "tobler_ratio_LEE.csv"
KIM_CACHE  = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"
BOKJI_POP  = PROJ_ROOT / "Bokji" / "고령자현황_20260421103806.csv"
OUT_DIR.mkdir(exist_ok=True)
CACHE_DIR  = ROOT / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── 팀 표준 파라미터 ──────────────────────────────────────────────
SPEEDS = [
    {"id": "young", "label": "일반인",              "speed": 1.28, "color": "#1D9E75"},
    {"id": "snr0",  "label": "일반 노인",            "speed": 1.12, "color": "#185FA5"},
    {"id": "snr1",  "label": "보행보조 노인",         "speed": 0.88, "color": "#E8A838"},
    {"id": "snr2",  "label": "보행보조 노인 하위15%", "speed": 0.70, "color": "#D85A30"},
]
TIMES  = [15, 30, 45]
FTYPES = ["hosp", "pharm"]

GU_MAP = {
    "11010": "종로구",   "11020": "중구",     "11030": "용산구",
    "11040": "성동구",   "11050": "광진구",   "11060": "동대문구",
    "11070": "중랑구",   "11080": "성북구",   "11090": "강북구",
    "11100": "도봉구",   "11110": "노원구",   "11120": "은평구",
    "11130": "서대문구", "11140": "마포구",   "11150": "양천구",
    "11160": "강서구",   "11170": "구로구",   "11180": "금천구",
    "11190": "영등포구", "11200": "동작구",   "11210": "관악구",
    "11220": "서초구",   "11230": "강남구",   "11240": "송파구",
    "11250": "강동구",
}

print("=" * 60)
print("D3 의료 통합 대시보드 v3")
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


# ── 1b. Tobler 경사 보정 (tobler_ratio_LEE.csv) ───────────────────
print("\n[1b] Tobler 경사 보정 로드 (tobler_ratio_LEE.csv)...")
SLOPE_OK = False
avg_tobler_slope = 1.0
try:
    tr_df = pd.read_csv(str(TOBLER_CSV), dtype={"dong_code": str})
    tr_df["dong_code"] = tr_df["dong_code"].astype(str).str.zfill(8)
    gdf_dong["dong_code_8"] = gdf_dong["dong_code"].str.zfill(8)
    gdf_dong = gdf_dong.merge(
        tr_df[["dong_code", "tobler_ratio"]].rename(columns={"dong_code": "dong_code_8"}),
        on="dong_code_8", how="left"
    )
    gdf_dong["t_ratio"] = gdf_dong["tobler_ratio"].fillna(1.0)
    avg_tobler_slope = float(gdf_dong["t_ratio"].mean())
    matched = gdf_dong["tobler_ratio"].notna().sum()
    SLOPE_OK = matched > 0
    print(f"  완료 — 매칭 {matched}/{len(gdf_dong)}개 동, 평균 ratio: {avg_tobler_slope:.3f}")
except Exception as e:
    print(f"  로드 실패 ({e}) → 경사 보정 없음 (ratio=1.0)")
    gdf_dong["t_ratio"] = 1.0

tr_flat  = np.ones(len(gdf_dong))
tr_slope = gdf_dong["t_ratio"].values


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


# ── 3. OSM 보행 네트워크 거리 행렬 ───────────────────────────────
print("\n[3/5] OSM 보행 네트워크 거리 행렬...")

cx = gdf_dong["cx"].values
cy = gdf_dong["cy"].values

GRAPH_PATH = CACHE_DIR / "seoul_walk.graphml"
DH_PATH    = CACHE_DIR / "DH_osm.npy"
DP_PATH    = CACHE_DIR / "DP_osm.npy"
MAX_RADIUS = float(1.28 * 45 * 60)   # 3,456 m

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

print("  최근접 노드 매핑...")
dong_node_ids  = list(ox.nearest_nodes(G_proj, X=cx,                Y=cy))
hosp_node_ids  = list(ox.nearest_nodes(G_proj, X=hosp["hx"].values, Y=hosp["hy"].values))
pharm_node_ids = list(ox.nearest_nodes(G_proj, X=pharm["hx"].values,Y=pharm["hy"].values))

n_dong, n_hosp, n_pharm = len(cx), len(hosp), len(pharm)

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


# ── 4. 사전 계산: 4속도 × 3시간 × 2시설 × 2경사모드 ─────────────
print("\n[4/5] 시설 도달 수 사전 계산 (flat/slope)...")

dong_codes = gdf_dong["dong_code"].tolist()

COUNTS: dict = {}

for sp in SPEEDS:
    for tmin in TIMES:
        for slope_key, tr_arr in [("flat", tr_flat), ("slope", tr_slope)]:
            r   = sp["speed"] * tmin * 60 * tr_arr
            nh  = (DH <= r[:, None]).sum(axis=1)
            np_ = (DP <= r[:, None]).sum(axis=1)
            for ftype, counts in [("hosp", nh), ("pharm", np_)]:
                key = f"{sp['id']}_{tmin}_{ftype}_{slope_key}"
                COUNTS[key] = {dc: int(counts[i]) for i, dc in enumerate(dong_codes)}
        print(f"  {sp['id']}_{tmin}: flat 병의원 평균 "
              f"{(DH <= sp['speed']*tmin*60).sum(axis=1).mean():.1f}개")


# ── 4b. 행정동 메타데이터 ─────────────────────────────────────────
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
print(f"  avg_tobler: {avg_tobler_slope:.4f}")


# ── 6. 구 단위 집계 CSV (conclusion_medical_LEE.csv) ──────────────
print("\n[6] 구 단위 집계 CSV 생성 (30분 기준)...")

T_CSV = 30
SCORE_SPEEDS = [
    ("snr0",  "노인"),
    ("snr1",  "보행보조"),
    ("snr2",  "하위15"),
]

rows_csv = []
for _, row in gdf_dong.iterrows():
    dc = row["dong_code"]
    gu = row["gu_name"]
    if not gu:
        continue
    for slope_key in ("flat", "slope"):
        n_young = (
            COUNTS.get(f"young_{T_CSV}_hosp_{slope_key}", {}).get(dc, 0) +
            COUNTS.get(f"young_{T_CSV}_pharm_{slope_key}", {}).get(dc, 0)
        )
        for sp_id, sp_label in SCORE_SPEEDS:
            n_b = (
                COUNTS.get(f"{sp_id}_{T_CSV}_hosp_{slope_key}", {}).get(dc, 0) +
                COUNTS.get(f"{sp_id}_{T_CSV}_pharm_{slope_key}", {}).get(dc, 0)
            )
            score = round((n_b / n_young) * 100, 2) if n_young > 0 else 100.0
            rows_csv.append({
                "gu_name":   gu,
                "sp_label":  sp_label,
                "slope_key": slope_key,
                "score":     score,
            })

df_csv = pd.DataFrame(rows_csv)
df_gu  = df_csv.groupby(["gu_name", "sp_label", "slope_key"])["score"].mean().reset_index()

col_rename = {
    ("노인",     "flat"):  "점수_노인_경사X",
    ("노인",     "slope"): "점수_노인_경사O",
    ("보행보조", "flat"):  "점수_보행보조_경사X",
    ("보행보조", "slope"): "점수_보행보조_경사O",
    ("하위15",   "flat"):  "점수_하위15_경사X",
    ("하위15",   "slope"): "점수_하위15_경사O",
}
df_pivot = df_gu.pivot_table(
    index="gu_name", columns=["sp_label","slope_key"], values="score"
).round(1)
df_pivot.columns = [col_rename.get(tuple(c), "_".join(c)) for c in df_pivot.columns]
df_pivot = df_pivot.reset_index().rename(columns={"gu_name": "구명"})

col_order = ["구명",
    "점수_노인_경사X", "점수_노인_경사O",
    "점수_보행보조_경사X", "점수_보행보조_경사O",
    "점수_하위15_경사X", "점수_하위15_경사O",
]
df_pivot = df_pivot[[c for c in col_order if c in df_pivot.columns]]
csv_out = OUT_DIR / "conclusion_medical_LEE.csv"
df_pivot.to_csv(str(csv_out), index=False, encoding="utf-8-sig")
print(f"  저장 완료: {csv_out}")
print(df_pivot.to_string(index=False))


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
.r2{display:grid;grid-template-columns:1.45fr 1fr;gap:14px;margin-bottom:14px}
.r2b{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 18px}
.ct{font-size:11px;font-weight:500;letter-spacing:.06em;color:#888780;text-transform:uppercase;margin-bottom:10px}
#map-wrap{position:relative;height:420px;border-radius:8px;overflow:hidden;background:#e8e4db}
#map{position:absolute;inset:0;height:100%!important}
.leg{display:flex;gap:10px;flex-wrap:wrap;margin-top:9px;align-items:center}
.li{display:flex;align-items:center;gap:5px;font-size:11px;color:#5f5e5a}
.ld{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.note{background:#e8f5f0;border:0.5px solid #1D9E75;border-radius:8px;padding:10px 14px;font-size:12px;color:#0f5e3c;line-height:1.7;margin-top:12px}
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
    <!-- 비교 속도 (A = 일반인 고정) -->
    <div class="crow">
      <span class="lbl" style="width:72px">비교 속도</span>
      <button class="btn bw"      id="b1" onclick="setB(1,this)">🧓 일반 노인 &nbsp;1.12 m/s</button>
      <button class="btn bw on"   id="b2" onclick="setB(2,this)">🦽 보행보조 노인 &nbsp;0.88 m/s</button>
      <button class="btn bw"      id="b3" onclick="setB(3,this)">♿ 보행보조 노인 하위15% &nbsp;0.70 m/s</button>
      <span style="font-size:11px;color:#b4b2a9;margin-left:6px">기준: 일반인 1.28 m/s 고정</span>
    </div>
    <!-- 경사 보정 -->
    <div class="crow">
      <span class="lbl" style="width:72px">경사 보정</span>
      <button class="btn bw on" id="slopeOff" onclick="setSlope(false,this)">경사 없음 (평지)</button>
      <button class="btn bw"    id="slopeOn"  onclick="setSlope(true,this)">경사 보정 (Tobler · NASA SRTM)</button>
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
      <div class="ct" id="mapTitle">행정동별 의료 도달가능점수</div>
      <div id="map-wrap"><div id="map"></div></div>
      <div class="leg" id="mapleg"></div>
      <p class="src">출처: 서울 열린데이터광장 병의원·약국 위치정보<br>
        ※ 도달가능점수(점) = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100 · 동 centroid 기준 OSM 보행 네트워크(다익스트라)</p>
    </div>
    <div class="card">
      <div class="ct" id="scTitle">일반인 vs 비교 속도 접근 가능 시설 수 (행정동별)</div>
      <div class="chart-wrap" style="height:360px"><canvas id="sc"></canvas></div>
      <div class="leg" style="margin-top:8px">
        <div class="li"><div class="ld" style="background:#1a9850;opacity:.8"></div>90점+</div>
        <div class="li"><div class="ld" style="background:#91cf60;opacity:.8"></div>80–90점</div>
        <div class="li"><div class="ld" style="background:#d9ef8b;opacity:.8"></div>70–80점</div>
        <div class="li"><div class="ld" style="background:#fee08b;opacity:.8"></div>60–70점</div>
        <div class="li"><div class="ld" style="background:#fdae61;opacity:.8"></div>50–60점</div>
        <div class="li"><div class="ld" style="background:#d73027;opacity:.8"></div>50점 미만</div>
        <div class="li" style="font-size:10px;color:#888">주황점선=이론선</div>
      </div>
    </div>
  </div>

  <!-- ③ 구별 바차트 + TOP 10 -->
  <div class="r2b">
    <div class="card">
      <div class="ct">구별 평균 의료 도달가능점수</div>
      <div class="chart-wrap" style="height:560px"><canvas id="gc"></canvas></div>
    </div>
    <div class="card">
      <div class="tabs">
        <button class="tab on" onclick="setTopTab('impact',this)">영향 노인 수 TOP 10동</button>
        <button class="tab" onclick="setTopTab('score',this)">도달가능점수 최하위 10동</button>
      </div>
      <div class="chart-wrap" style="height:520px"><canvas id="ic"></canvas></div>
    </div>
  </div>

  <!-- ④ 상세표 -->
  <div class="card">
    <div class="ct">행정동별 의료 접근성 상세 (도달가능점수 낮은 순)</div>
    <div class="tbl-wrap"><table id="tbl"></table></div>
    <p class="src">도달가능점수(점) = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100 &nbsp;|&nbsp;
      영향 노인 수 = (100 − 점수) / 100 × 동별 65세 이상 인구</p>
  </div>

  <div class="note" id="noteBox"></div>
</div>

<script>
/* ───────── 임베드 데이터 ───────── */
const GEOJSON    = __GEOJSON__;
const COUNTS     = __COUNTS__;
const DONG_META  = __DONG_META__;
const SPEEDS     = __SPEEDS__;
const AVG_TOBLER = __AVG_TOBLER__;

/* ───────── 상태 (cA = 0 고정) ───────── */
let cB = 2, cT = 15, cF = 'all', cSlope = false, cTop = 'impact';

/* ───────── 헬퍼: 시설 수 조회 ───────── */
function getN(speedId, time, ftype, dc, isSlope) {
  const s = isSlope ? 'slope' : 'flat';
  if (ftype === 'all') {
    return (COUNTS[speedId+'_'+time+'_hosp_'+s][dc] || 0)
         + (COUNTS[speedId+'_'+time+'_pharm_'+s][dc] || 0);
  }
  return COUNTS[speedId+'_'+time+'_'+ftype+'_'+s][dc] || 0;
}

function dongScore(dc) {
  const nYoung = getN('young', cT, cF, dc, cSlope);
  const nB     = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
  return nYoung > 0 ? (nB / nYoung) * 100 : 100;
}

/* ───────── 컬러 (점수: 높을수록 초록) ───────── */
function scoreColor(v) {
  if (v >= 90) return '#1a9850';
  if (v >= 80) return '#91cf60';
  if (v >= 70) return '#d9ef8b';
  if (v >= 60) return '#fee08b';
  if (v >= 50) return '#fdae61';
  if (v >= 40) return '#d73027';
  return '#a50026';
}
function ptScoreColor(v) {
  if (v >= 90) return 'rgba(26,152,80,.8)';
  if (v >= 80) return 'rgba(145,207,96,.8)';
  if (v >= 70) return 'rgba(217,239,139,.9)';
  if (v >= 60) return 'rgba(254,224,139,.9)';
  if (v >= 50) return 'rgba(253,174,97,.8)';
  if (v >= 40) return 'rgba(215,48,39,.8)';
  return 'rgba(165,0,38,.8)';
}

/* ───────── 전체 동 통계 계산 ───────── */
function allDongStats() {
  return Object.keys(DONG_META).map(dc => {
    const nYoung = getN('young', cT, cF, dc, cSlope);
    const nB     = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
    const score  = nYoung > 0 ? (nB / nYoung) * 100 : 100;
    const m = DONG_META[dc];
    const impact = Math.round(Math.max(0, 100 - score) / 100 * m.el);
    return { dc, fn: m.fn, gu: m.gu, el: m.el, nYoung, nB, score, impact };
  });
}

/* ───────── 구별 집계 ───────── */
function guStats(rows) {
  const byGu = {};
  rows.filter(r => r.nYoung > 0).forEach(r => {
    if (!byGu[r.gu]) byGu[r.gu] = { sum: 0, cnt: 0, impact: 0 };
    byGu[r.gu].sum    += r.score;
    byGu[r.gu].cnt    += 1;
    byGu[r.gu].impact += r.impact;
  });
  return Object.entries(byGu)
    .map(([gu, v]) => ({ gu, sc: v.sum / v.cnt, im: v.impact }))
    .sort((a, b) => a.sc - b.sc);  // 낮은 점수(취약) 먼저
}

/* ───────── Leaflet 지도 ───────── */
const mapEl = L.map('map', {zoomControl:true, attributionControl:false})
  .setView([37.5665, 126.978], 11);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  {maxZoom:18}).addTo(mapEl);

let geoLayer = null;

function styleFeature(feat) {
  return {
    fillColor:   scoreColor(dongScore(feat.properties.dc)),
    color:       'rgba(80,80,80,0.25)',
    weight:      0.5,
    fillOpacity: 0.82,
  };
}

function tooltipContent(feat) {
  const dc = feat.properties.dc;
  const m = DONG_META[dc];
  if (!m) return '';
  const nYoung = getN('young', cT, cF, dc, cSlope);
  const nB     = getN(SPEEDS[cB].id, cT, cF, dc, cSlope);
  const score  = nYoung > 0 ? (nB / nYoung) * 100 : 100;
  const impact = Math.round(Math.max(0, 100 - score) / 100 * m.el);
  return `<b>${m.fn}</b><br>`
       + `도달가능점수: <b>${score.toFixed(1)}점</b><br>`
       + `일반인 ${nYoung}개 → ${SPEEDS[cB].label} ${nB}개<br>`
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
    {v:'90점+',   c:'#1a9850'},
    {v:'80–90점', c:'#91cf60'},
    {v:'70–80점', c:'#d9ef8b', b:'1px solid #ccc'},
    {v:'60–70점', c:'#fee08b', b:'1px solid #ccc'},
    {v:'50–60점', c:'#fdae61'},
    {v:'40–50점', c:'#d73027'},
    {v:'40점 미만',c:'#a50026'},
  ];
  document.getElementById('mapleg').innerHTML =
    steps.map(s =>
      `<div class="li"><div class="ld" style="background:${s.c};${s.b||''}"></div>${s.v}</div>`
    ).join('');
}

/* ───────── 속도 거리 바 ───────── */
function updateDistBars() {
  const tr = cSlope ? AVG_TOBLER : 1.0;
  const rows = SPEEDS.map((s, i) => {
    const dist = Math.round(s.speed * cT * 60 * tr);
    const pct  = dist / (1.28 * cT * 60) * 100;
    const isB  = (i === cB), isYoung = (i === 0);
    const badge = isYoung ? `<span class="dbar-badge" style="background:${s.color}20;color:${s.color}">기준</span>`
                : isB    ? `<span class="dbar-badge" style="background:${s.color}20;color:${s.color}">비교</span>`
                : '';
    const opacity = (isYoung || isB) ? '1' : '0.35';
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
  const valid = rows.filter(r => r.nYoung > 0);
  const meanScore   = valid.length ? valid.reduce((s, r) => s + r.score, 0) / valid.length : 0;
  const totalImpact = rows.reduce((s, r) => s + r.impact, 0);
  const tr = cSlope ? AVG_TOBLER : 1.0;
  const rYoung = Math.round(1.28 * cT * 60 * tr);
  const rB     = Math.round(SPEEDS[cB].speed * cT * 60 * tr);
  const theory = (SPEEDS[cB].speed / 1.28) ** 2 * 100;

  document.getElementById('sg').innerHTML = `
    <div class="sc">
      <div class="sl">일반인(기준) 반경</div>
      <div class="sv" style="color:${SPEEDS[0].color}">${rYoung.toLocaleString()} m</div>
      <div class="ss">1.28 m/s · ${cT}분${cSlope?'·경사보정':''}</div>
    </div>
    <div class="sc">
      <div class="sl">비교 속도 반경</div>
      <div class="sv" style="color:${SPEEDS[cB].color}">${rB.toLocaleString()} m</div>
      <div class="ss">${SPEEDS[cB].speed} m/s · ${cT}분${cSlope?'·경사보정':''}</div>
    </div>
    <div class="sc">
      <div class="sl">평균 도달가능점수</div>
      <div class="sv" style="color:${scoreColor(meanScore)}">${meanScore.toFixed(1)}<span style="font-size:14px;font-weight:400">점</span></div>
      <div class="ss">이론값 ${theory.toFixed(1)}점 (속도비 제곱)</div>
    </div>
    <div class="sc">
      <div class="sl">영향 노인 수 (추정)</div>
      <div class="sv">${(totalImpact / 10000).toFixed(1)}<span style="font-size:14px;font-weight:400">만명</span></div>
      <div class="ss">(100−점수)/100 × 65세 이상 인구</div>
    </div>`;
}

/* ───────── 제목 + 노트 업데이트 ───────── */
function updateLabels() {
  const b = SPEEDS[cB];
  const slopeNote = cSlope ? ' · 경사 보정 적용' : ' · 평지 기준';
  document.getElementById('mapTitle').textContent =
    `행정동별 의료 도달가능점수 — ${b.label} (${b.speed} m/s)${slopeNote}`;
  document.getElementById('scTitle').textContent =
    `일반인 vs ${b.label} 접근 가능 시설 수`;
  const theory = (b.speed / 1.28) ** 2 * 100;
  document.getElementById('noteBox').innerHTML =
    `※ <b>일반인 (1.28 m/s)</b>를 기준으로 <b>${b.label} (${b.speed} m/s)</b>의 도달가능점수를 표시합니다.<br>
     ※ 도달가능점수 = (비교속도 도달 시설 수 / 일반인 도달 시설 수) × 100 — 이론값 <b>${theory.toFixed(1)}점</b><br>
     ※ 경사 보정: ${cSlope ? 'Tobler hiking function 기반 동별 속도 보정 (tobler_ratio_LEE.csv)' : '평지 기준 (보정 없음)'}<br>
     ※ 거리 측정: 동 centroid 기준 OSM 보행 네트워크(다익스트라)`;
}

/* ───────── B 버튼 색 동기화 ───────── */
function syncBtnColors() {
  [1, 2, 3].forEach(i => {
    const btn = document.getElementById('b' + i);
    if (!btn) return;
    if (i === cB) {
      btn.style.background  = SPEEDS[i].color;
      btn.style.borderColor = SPEEDS[i].color;
      btn.classList.add('on');
    } else {
      btn.style.background  = '';
      btn.style.borderColor = '';
      btn.classList.remove('on');
    }
  });
  document.getElementById('slopeOff').classList.toggle('on', !cSlope);
  document.getElementById('slopeOff').style.background  = !cSlope ? '#5f5e5a' : '';
  document.getElementById('slopeOff').style.borderColor = !cSlope ? '#5f5e5a' : '';
  document.getElementById('slopeOn').classList.toggle('on', cSlope);
  document.getElementById('slopeOn').style.background   = cSlope  ? '#5f5e5a' : '';
  document.getElementById('slopeOn').style.borderColor  = cSlope  ? '#5f5e5a' : '';
}

/* ───────── Chart.js ───────── */
let scChart, gcChart, icChart;

function initCharts(rows) {
  const sData = rows.filter(r => r.nYoung > 0);
  const ratio  = SPEEDS[cB].speed / 1.28;
  const maxV   = Math.max(...sData.map(r => r.nYoung), 1) + 5;

  scChart = new Chart(document.getElementById('sc'), {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: '행정동',
          data: sData.map(r => ({x: r.nYoung, y: r.nB, sc: r.score, fn: r.fn})),
          backgroundColor: sData.map(r => ptScoreColor(r.score)),
          pointRadius: 4, pointHoverRadius: 6,
        },
        {
          label: '100점 (y=x)',
          data: [{x:0,y:0},{x:maxV,y:maxV}],
          type:'line', borderColor:'#aaa', borderWidth:1,
          borderDash:[4,4], pointRadius:0, fill:false,
        },
        {
          label: `이론선 (${(ratio*ratio*100).toFixed(0)}점)`,
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
              `일반인 ${p.x}개 → 비교 ${p.y}개`,
              `점수: ${p.sc.toFixed(1)}점`];
            return ctx.dataset.label;
          },
        }},
      },
      scales:{
        x:{title:{display:true,text:'일반인 도달 시설 수',font:{size:11}},grid:{color:'#f0f0ee'}},
        y:{title:{display:true,text:`${SPEEDS[cB].label} 도달 시설 수`,font:{size:11}},grid:{color:'#f0f0ee'}},
      },
    },
  });

  const gl = guStats(rows);
  gcChart = new Chart(document.getElementById('gc'), {
    type:'bar',
    data:{
      labels: gl.map(r=>r.gu),
      datasets:[{
        data: gl.map(r=>r.sc),
        backgroundColor: gl.map(r=>scoreColor(r.sc)),
        borderWidth:0,
      }],
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:ctx=>`도달가능점수: ${ctx.raw.toFixed(1)}점`}}},
      scales:{
        x:{min:0, max:100, grid:{color:'#f0f0ee'},
           ticks:{callback:v=>v+'점'},
           title:{display:true,text:'평균 도달가능점수(점)',font:{size:11}}},
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
    : rows.filter(r=>r.nYoung>0).sort((a,b)=>a.score-b.score).slice(0,10);
  const labels = sorted.map(r=>r.fn);
  const vals   = isImpact ? sorted.map(r=>r.impact) : sorted.map(r=>r.score);
  const colors = isImpact
    ? sorted.map((_,i)=>`hsl(${10+i*4},68%,${42+i*3}%)`)
    : sorted.map(r=>scoreColor(r.score));

  if (icChart) icChart.destroy();
  icChart = new Chart(document.getElementById('ic'), {
    type:'bar',
    data:{
      labels,
      datasets:[{data:vals, backgroundColor:colors, borderWidth:0}],
    },
    options:{
      indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{
          label:ctx=>isImpact?`약 ${ctx.raw.toLocaleString()}명`:`${ctx.raw.toFixed(1)}점`,
        }}},
      scales:{
        x:{grid:{color:'#f0f0ee'},
           min: isImpact ? 0 : 0,
           max: isImpact ? undefined : 100,
           title:{display:true,text:isImpact?'영향 노인 수(명)':'도달가능점수(점)',font:{size:11}}},
        y:{ticks:{font:{size:11}}},
      },
    },
  });
}

function refreshCharts(rows) {
  const sData = rows.filter(r => r.nYoung > 0);
  const ratio  = SPEEDS[cB].speed / 1.28;
  const maxV   = Math.max(...sData.map(r => r.nYoung), 1) + 5;

  scChart.data.datasets[0].data            = sData.map(r=>({x:r.nYoung,y:r.nB,sc:r.score,fn:r.fn}));
  scChart.data.datasets[0].backgroundColor = sData.map(r=>ptScoreColor(r.score));
  scChart.data.datasets[1].data = [{x:0,y:0},{x:maxV,y:maxV}];
  scChart.data.datasets[2].data = [{x:0,y:0},{x:maxV,y:maxV*ratio*ratio}];
  scChart.data.datasets[2].label = `이론선 (${(ratio*ratio*100).toFixed(0)}점)`;
  scChart.options.scales.y.title.text = `${SPEEDS[cB].label} 도달 시설 수`;
  scChart.update('none');

  const gl = guStats(rows);
  gcChart.data.labels                       = gl.map(r=>r.gu);
  gcChart.data.datasets[0].data            = gl.map(r=>r.sc);
  gcChart.data.datasets[0].backgroundColor = gl.map(r=>scoreColor(r.sc));
  gcChart.update('none');

  buildTopChart(rows);
}

/* ───────── 테이블 ───────── */
function updateTable(rows) {
  const sorted = rows.filter(r=>r.nYoung>0).sort((a,b)=>a.score-b.score).slice(0, 100);
  document.getElementById('tbl').innerHTML =
    `<thead><tr>
      <th>행정동</th><th>도달가능점수</th><th>일반인</th><th>비교 속도</th>
      <th>영향 노인 수</th><th>등급</th>
    </tr></thead>
    <tbody>${sorted.map(r=>{
      const g = r.score < 40 ? '<span class="pill plo">취약</span>':
                r.score < 60 ? '<span class="pill pmd">주의</span>':
                r.score >= 90 ? '<span class="pill phi">양호</span>':
                '<span class="pill phi">보통</span>';
      return `<tr>
        <td>${r.fn}</td>
        <td><b>${r.score.toFixed(1)}점</b></td>
        <td>${r.nYoung}</td><td>${r.nB}</td>
        <td>${r.el>0?r.impact.toLocaleString()+'명':'-'}</td>
        <td>${g}</td>
      </tr>`;
    }).join('')}</tbody>`;
}

/* ───────── 컨트롤 핸들러 ───────── */
function setB(idx, btn) {
  cB = idx;
  syncBtnColors();
  update();
}
function setSlope(val, btn) {
  cSlope = val;
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
  buildTopChart(allDongStats());
}

/* ───────── 전체 업데이트 ───────── */
let _initialized = false;

function update() {
  updateLabels();
  updateDistBars();
  const rows = allDongStats();
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
        .replace("__AVG_TOBLER__", str(round(avg_tobler_slope, 4))))

out = OUT_DIR / "medical_dashboard.html"
out.write_text(html, encoding="utf-8")

print("\n" + "=" * 60)
print(f"저장 완료: {out}")
print(f"파일 크기: {out.stat().st_size // 1024} KB")
print(f"conclusion CSV: {csv_out}")
print("=" * 60)
