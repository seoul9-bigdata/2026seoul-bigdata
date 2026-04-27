"""
03_trip_chaining.py  ·  D3 의료 — 의료·약국 삼각 동선 분석
──────────────────────────────────────────────────────────
아이디어: "아픈 몸을 이끌고 세 번 걸어야 한다"

핵심 질문:
  집에서 출발해 병원에 들렀다가 약국까지 가는
  '삼각 동선' 총 거리가 노인의 30분 보행 한계(1,404m)를
  초과하는 동이 얼마나 되는가?

분석 방법:
  1. 각 동 중심(집) → 가장 가까운 병의원까지 거리 (d1)
  2. 그 병의원 → 가장 가까운 약국까지 거리 (d2)
  3. 그 약국 → 동 중심(귀가)까지 거리 (d3)
  4. 총 동선 = d1 + d2 + d3
  5. 총 동선 > 1,404m 이면 '30분 내 원스톱 불가'

  추가: 병원+약국 동반 입지(200m 내) '원스톱 클러스터' 파악

출력:
  ../outputs/08_trip_chain_map.html      ← 동별 삼각동선 총거리 코로플레스
  ../outputs/09_trip_chain_bar.html      ← 구별 원스톱 불가 동 비율 바차트
"""

import warnings, sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
from scipy.spatial import cKDTree
import folium
import branca.colormap as cm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
KIM_CACHE = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"
OUT_DIR.mkdir(exist_ok=True)

SPEED_SENIOR       = 0.88
DIST_SENIOR        = SPEED_SENIOR * 30 * 60   # 1,584 m — 단일 편도 30분
ONESTOP_RADIUS_M   = 200                       # 병원+약국 동반 반경

# 동 이름 매핑
_kim = __import__('pandas').read_csv(KIM_CACHE, dtype={"dong_code": str})
DONG_NAME_MAP = dict(zip(_kim["dong_code"], _kim["dong_name"]))

GU_MAP = {
    "11010": "종로구",  "11020": "중구",    "11030": "용산구",
    "11040": "성동구",  "11050": "광진구",  "11060": "동대문구",
    "11070": "중랑구",  "11080": "성북구",  "11090": "강북구",
    "11100": "도봉구",  "11110": "노원구",  "11120": "은평구",
    "11130": "서대문구","11140": "마포구",  "11150": "양천구",
    "11160": "강서구",  "11170": "구로구",  "11180": "금천구",
    "11190": "영등포구","11200": "동작구",  "11210": "관악구",
    "11220": "서초구",  "11230": "강남구",  "11240": "송파구",
    "11250": "강동구",
}

print("=" * 60)
print("의료·약국 삼각 동선 분석 시작")
print(f"  노인 30분 도달 한계: {DIST_SENIOR:.0f} m")
print("=" * 60)


# ═══════════════════════════════════════════════════════════════
# 1. 행정동 경계
# ═══════════════════════════════════════════════════════════════
print("\n[1/5] 행정동 경계 로드 중…")
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
gdf_dong["cx"] = gdf_dong.geometry.centroid.x
gdf_dong["cy"] = gdf_dong.geometry.centroid.y
print(f"  행정동 {len(gdf_dong)}개")


# ═══════════════════════════════════════════════════════════════
# 2. 의료시설 로드
# ═══════════════════════════════════════════════════════════════
print("\n[2/5] 의료시설 로드 중…")
t_wgs  = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
t_5174 = Transformer.from_crs("EPSG:5174", "EPSG:5179", always_xy=True)

# 병의원
hosp_raw = pd.read_csv(HOSP_CSV, encoding="cp949")
hosp = hosp_raw[
    hosp_raw["병원분류명"].isin(["의원", "병원", "보건소", "종합병원"])
].copy()
hosp = hosp.dropna(subset=["병원경도", "병원위도"])
hosp = hosp[(hosp["병원경도"] > 120) & (hosp["병원위도"] > 35)]
hosp["x5179"], hosp["y5179"] = t_wgs.transform(
    hosp["병원경도"].values, hosp["병원위도"].values
)
print(f"  병의원: {len(hosp)}개")

# 약국 (인허가 파일 — EPSG:5174 좌표)
pharm_raw = pd.read_csv(PHARM_CSV, encoding="cp949")
pharm = pharm_raw[
    (pharm_raw["영업상태명"] == "영업/정상") &
    (pharm_raw["도로명주소"].str.startswith("서울", na=False))
].copy()
pharm["x"] = pd.to_numeric(pharm["좌표정보(X)"].astype(str).str.strip(), errors="coerce")
pharm["y"] = pd.to_numeric(pharm["좌표정보(Y)"].astype(str).str.strip(), errors="coerce")
pharm = pharm.dropna(subset=["x", "y"])
pharm = pharm[(pharm["x"] > 100000) & (pharm["y"] > 300000)]
pharm["x5179"], pharm["y5179"] = t_5174.transform(pharm["x"].values, pharm["y"].values)
print(f"  약국: {len(pharm)}개")

xy_hosp  = np.column_stack([hosp["x5179"].values,  hosp["y5179"].values])
xy_pharm = np.column_stack([pharm["x5179"].values, pharm["y5179"].values])

tree_hosp  = cKDTree(xy_hosp)
tree_pharm = cKDTree(xy_pharm)


# ═══════════════════════════════════════════════════════════════
# 3. 원스톱 클러스터 파악 (병원 200m 이내 약국 존재)
# ═══════════════════════════════════════════════════════════════
print("\n[3/5] 원스톱 클러스터 파악 중…")
# 각 병원에서 ONESTOP_RADIUS_M 내 약국 존재 여부
hosp_has_near_pharm = np.array([
    len(tree_pharm.query_ball_point(xy_hosp[i], ONESTOP_RADIUS_M)) > 0
    for i in range(len(xy_hosp))
])
xy_onestop = xy_hosp[hosp_has_near_pharm]
n_onestop = int(hosp_has_near_pharm.sum())
print(f"  원스톱 클러스터(병원+약국 {ONESTOP_RADIUS_M}m 내): {n_onestop}개 병원")
tree_onestop = cKDTree(xy_onestop) if n_onestop > 0 else None


# ═══════════════════════════════════════════════════════════════
# 4. 동별 삼각 동선 계산
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] 동별 삼각 동선 계산 중…")

d1_list, d2_list, d3_list, total_list, onestop_dist_list = [], [], [], [], []

for _, row in gdf_dong.iterrows():
    home = np.array([row["cx"], row["cy"]])

    # d1: 집 → 가장 가까운 병원
    d1, idx_h = tree_hosp.query(home)

    # d2: 그 병원 → 가장 가까운 약국
    hospital_pos = xy_hosp[idx_h]
    d2, idx_p = tree_pharm.query(hospital_pos)

    # d3: 그 약국 → 집
    pharm_pos = xy_pharm[idx_p]
    d3 = float(np.linalg.norm(pharm_pos - home))

    total = d1 + d2 + d3

    # 원스톱 클러스터까지 거리 (집 → 클러스터)
    if tree_onestop is not None:
        onestop_d, _ = tree_onestop.query(home)
    else:
        onestop_d = np.inf

    d1_list.append(float(d1))
    d2_list.append(float(d2))
    d3_list.append(float(d3))
    total_list.append(float(total))
    onestop_dist_list.append(float(onestop_d))

gdf_dong["d1_hosp_m"]       = d1_list          # 집→병원
gdf_dong["d2_pharm_m"]      = d2_list          # 병원→약국
gdf_dong["d3_return_m"]     = d3_list          # 약국→집
gdf_dong["trip_total_m"]    = total_list       # 삼각 총 동선
gdf_dong["onestop_dist_m"]  = onestop_dist_list

# 30분 내 왕복 불가 여부 (총 동선 > 노인 30분 한계)
gdf_dong["impossible"]      = gdf_dong["trip_total_m"] > DIST_SENIOR
gdf_dong["onestop_possible"] = gdf_dong["onestop_dist_m"] <= DIST_SENIOR

n_impossible = int(gdf_dong["impossible"].sum())
n_onestop_ok = int(gdf_dong["onestop_possible"].sum())
print(f"  삼각 동선 초과 동 (총 거리 > {DIST_SENIOR:.0f}m): {n_impossible}개 "
      f"({n_impossible/len(gdf_dong)*100:.1f}%)")
print(f"  원스톱 클러스터 30분 내 접근 가능 동: {n_onestop_ok}개 "
      f"({n_onestop_ok/len(gdf_dong)*100:.1f}%)")
print(f"  삼각 동선 평균 총 거리: {gdf_dong['trip_total_m'].mean():.0f}m")


# ═══════════════════════════════════════════════════════════════
# 5. 시각화
# ═══════════════════════════════════════════════════════════════
print("\n[5/5] 시각화 생성 중…")
gdf_wgs = gdf_dong.to_crs("EPSG:4326")
gdf_wgs["cx_wgs"] = gdf_wgs.geometry.centroid.x
gdf_wgs["cy_wgs"] = gdf_wgs.geometry.centroid.y

m = folium.Map(location=[37.5665, 126.978], zoom_start=11,
               tiles=None, prefer_canvas=True)
folium.TileLayer("CartoDB dark_matter", name="Dark Map").add_to(m)
folium.TileLayer("OpenStreetMap", name="일반 지도").add_to(m)

# ── 코로플레스: 삼각 동선 총 거리 ───────────────────────────
sub    = gdf_wgs[gdf_wgs["trip_total_m"] > 0]
vmin   = float(sub["trip_total_m"].quantile(0.05))
vmax   = float(sub["trip_total_m"].quantile(0.95))
cmap_trip = cm.LinearColormap(
    colors=["#FFF5F0", "#FCBBA1", "#FC7050", "#D73027", "#67000D"],
    vmin=vmin, vmax=vmax,
    caption="삼각 동선 총 거리(m) — 집→병원→약국→집",
)
geojson_data = json.loads(
    gdf_wgs[["dong_code", "gu_name", "full_name",
             "trip_total_m", "d1_hosp_m", "d2_pharm_m", "d3_return_m",
             "impossible", "geometry"]].to_json()
)

def _style_trip(feat):
    v = feat["properties"].get("trip_total_m") or 0
    impossible = feat["properties"].get("impossible") or False
    base_color = cmap_trip(min(max(v, vmin), vmax))
    return {
        "fillColor":   base_color,
        "color":       "#FF4444" if impossible else "rgba(80,80,80,0.3)",
        "weight":      1.5 if impossible else 0.5,
        "fillOpacity": 0.85,
    }

fg_trip = folium.FeatureGroup(name="삼각 동선 총 거리", show=True)
folium.GeoJson(
    data=geojson_data,
    style_function=_style_trip,
    highlight_function=lambda x: {"fillOpacity": 0.95, "weight": 2, "color": "#FFD700"},
    tooltip=folium.GeoJsonTooltip(
        fields=["full_name", "trip_total_m", "d1_hosp_m", "d2_pharm_m", "d3_return_m", "impossible"],
        aliases=["행정동", "총 동선(m)", "집→병원(m)", "병원→약국(m)", "약국→집(m)", "30분 초과"],
        localize=True, sticky=True,
        style="font-family:'Malgun Gothic',sans-serif;font-size:12px;",
    ),
).add_to(fg_trip)
fg_trip.add_to(m)
cmap_trip.add_to(m)

# ── 원스톱 클러스터 마커 ─────────────────────────────────────
t_inv = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
lons_os, lats_os = t_inv.transform(xy_onestop[:, 0], xy_onestop[:, 1])
fg_os = folium.FeatureGroup(name=f"원스톱 클러스터 (병원+약국 {ONESTOP_RADIUS_M}m 내)", show=False)
for lat, lon in zip(lats_os[:500], lons_os[:500]):  # 최대 500개
    folium.CircleMarker(
        location=[lat, lon], radius=3,
        color="#00BFFF", weight=1,
        fill=True, fill_color="#00BFFF", fill_opacity=0.6,
    ).add_to(fg_os)
fg_os.add_to(m)

# ── 30분 초과 동 강조 마커 ──────────────────────────────────
impossible_dongs = gdf_wgs[gdf_wgs["impossible"]]
fg_imp = folium.FeatureGroup(name="삼각 동선 30분 초과 동", show=False)
for _, row in impossible_dongs.iterrows():
    folium.CircleMarker(
        location=[row["cy_wgs"], row["cx_wgs"]],
        radius=7, color="#FF0000", weight=2,
        fill=True, fill_color="#FF0000", fill_opacity=0.85,
        tooltip=folium.Tooltip(
            f"<b>{row['full_name']}</b><br>"
            f"총 동선: {row['trip_total_m']:.0f}m (한계: {DIST_SENIOR:.0f}m)<br>"
            f"집→병원: {row['d1_hosp_m']:.0f}m | 병원→약국: {row['d2_pharm_m']:.0f}m",
            sticky=True,
        ),
    ).add_to(fg_imp)
fg_imp.add_to(m)

folium.LayerControl(collapsed=False, position="topright").add_to(m)

title_html = f"""
<div style="
    position:fixed; top:10px; left:50%; transform:translateX(-50%);
    z-index:9999; background:rgba(10,10,20,0.92);
    border:1px solid #555; border-radius:8px;
    padding:10px 28px; text-align:center;
    font-family:'Malgun Gothic',sans-serif;
    box-shadow:0 2px 12px rgba(0,0,0,0.5);">
  <div style="font-size:16px;font-weight:bold;color:#fff;">
    의료·약국 삼각 동선 분석 (D3. 의료)
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:4px;">
    집 → 병원 → 약국 → 집 · 노인(0.78 m/s) 30분 한계: {DIST_SENIOR:.0f}m
  </div>
  <div style="font-size:11px;color:#ddd;margin-top:3px;">
    삼각 동선 30분 초과 동: <b style="color:#FC7050">{n_impossible}개
    ({n_impossible/len(gdf_dong)*100:.1f}%)</b>
  </div>
  <div style="font-size:10px;color:#aaa;margin-top:2px;">
    원스톱 클러스터(병원+약국 {ONESTOP_RADIUS_M}m 내) {n_onestop}개
  </div>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

out8 = OUT_DIR / "08_trip_chain_map.html"
m.save(str(out8))
print(f"  저장: {out8}")

# ── 구별 원스톱 불가 비율 바차트 ─────────────────────────────
df_plot = gdf_wgs[["full_name", "gu_name", "trip_total_m",
                   "impossible", "onestop_possible"]].copy()
df_gu = (
    df_plot.groupby("gu_name")
    .agg(
        impossible_pct=("impossible",      lambda x: x.mean() * 100),
        onestop_pct   =("onestop_possible",lambda x: x.mean() * 100),
        avg_trip_m    =("trip_total_m",    "mean"),
    )
    .reset_index()
    .sort_values("impossible_pct", ascending=True)
)

fig_bar = make_subplots(
    rows=1, cols=2,
    subplot_titles=(
        f"삼각 동선 30분 초과 동 비율 (%)\n(한계: {DIST_SENIOR:.0f}m)",
        "원스톱 클러스터 30분 내 접근 가능 동 비율 (%)",
    ),
    horizontal_spacing=0.12,
)
fig_bar.add_trace(
    go.Bar(y=df_gu["gu_name"], x=df_gu["impossible_pct"],
           orientation="h",
           marker=dict(color=df_gu["impossible_pct"], colorscale="Reds"),
           text=df_gu["impossible_pct"].round(1).astype(str) + "%",
           textposition="outside", showlegend=False),
    row=1, col=1,
)
fig_bar.add_trace(
    go.Bar(y=df_gu["gu_name"], x=df_gu["onestop_pct"],
           orientation="h",
           marker=dict(color=df_gu["onestop_pct"], colorscale="Blues"),
           text=df_gu["onestop_pct"].round(1).astype(str) + "%",
           textposition="outside", showlegend=False),
    row=1, col=2,
)
fig_bar.update_layout(
    title_text="서울 25개 구 삼각 동선 분석 — 병원+약국 원스톱 접근성",
    font_family="Malgun Gothic",
    height=750,
    plot_bgcolor="#f8f8f8",
)
fig_bar.update_xaxes(title_text="동 비율(%)", row=1, col=1)
fig_bar.update_xaxes(title_text="동 비율(%)", row=1, col=2)

out9 = OUT_DIR / "09_trip_chain_bar.html"
fig_bar.write_html(str(out9))
print(f"  저장: {out9}")

print("\n" + "=" * 60)
print("삼각 동선 분석 완료!")
print(f"  삼각 동선 30분 초과 동: {n_impossible}개 ({n_impossible/len(gdf_dong)*100:.1f}%)")
print(f"  원스톱 클러스터 수: {n_onestop}개 (병원+약국 {ONESTOP_RADIUS_M}m 내)")
print("=" * 60)
print("\n출력 파일:")
for f in [out8, out9]:
    print(f"  {f}")
