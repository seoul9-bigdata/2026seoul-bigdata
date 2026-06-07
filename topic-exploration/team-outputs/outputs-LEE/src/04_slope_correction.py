"""
04_slope_correction.py  ·  D3 의료 — 경사도 보행속도 보정 분석
────────────────────────────────────────────────────────────────
Tobler's Hiking Function 적용:
  V = 6 × exp(−3.5 × |s + 0.05|)  km/h   (s = 경사 기울기, tan θ)

노인(0.78 m/s)의 보행속도를 동별 평균 경사도에 따라 보정하면
실질 30분 도달 거리가 얼마나 더 줄어드는가?

데이터:
  서울시 경사도/표고 5000/N3P_F002.shp  ←  표고점 (EPSG:5174, HEIGHT 컬럼)
  서울시 경사도/등고선 5000/N3L_F001.shp ←  등고선 (HEIGHT 컬럼, 보조)

분석 방법:
  1. 표고점을 행정동에 공간 결합
  2. 동별 HEIGHT: max, min, std, count 집계
  3. 경사 추정: slope ≈ height_range / (sqrt(area_m2) × 1.13)
     (원형 동 가정: 지름 ≈ √area × 1.13)
  4. Tobler 정규화: V_senior_slope = 0.78 × f(slope) / f(0)
  5. 보정 도달 거리 = V_senior_slope × 1800 s

출력:
  ../outputs/10_slope_map.html          ← 동별 경사도 및 보정 속도 지도
  ../outputs/11_slope_adjusted.html     ← 보정 전후 도달 거리 비교
"""

import warnings, sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
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

SHP_PATH      = PROJ_ROOT / "prototype" / "끊어진서울(가제)" / "data" \
                / "bnd_oa_11_2025_2Q" / "bnd_oa_11_2025_2Q.shp"
ELEV_SHP      = DATA_DIR / "서울시 경사도" / "표고 5000" / "N3P_F002.shp"
CONTOUR_SHP   = DATA_DIR / "서울시 경사도" / "등고선 5000" / "N3L_F001.shp"
KIM_CACHE     = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"
OUT_DIR.mkdir(exist_ok=True)

SPEED_YOUNG  = 1.28   # m/s  일반인 (한음 외 2020)
SPEED_SENIOR = 0.88   # m/s  보행보조 노인 평균 (평지 기준)
CUTOFF_MIN   = 30
DIST_YOUNG   = SPEED_YOUNG  * CUTOFF_MIN * 60   # 2,304 m
DIST_SENIOR  = SPEED_SENIOR * CUTOFF_MIN * 60   # 1,584 m

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

# Tobler's Hiking Function 정규화 상수 (평지 s=0에서의 속도)
TOBLER_FLAT = 6.0 * np.exp(-3.5 * abs(0 + 0.05))   # ≈ 5.036 km/h

def tobler_speed_ratio(slope: float) -> float:
    """경사도(s) 기준 Tobler 속도 비율 (평지 대비)"""
    return (6.0 * np.exp(-3.5 * abs(slope + 0.05))) / TOBLER_FLAT

print("=" * 60)
print("경사도 보행속도 보정 분석 시작")
print(f"  Tobler 평지 기준 속도: {TOBLER_FLAT:.3f} km/h")
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
gdf_dong["area_m2"] = gdf_dong.geometry.area
gdf_dong["cx"] = gdf_dong.geometry.centroid.x
gdf_dong["cy"] = gdf_dong.geometry.centroid.y
print(f"  행정동 {len(gdf_dong)}개")


# ═══════════════════════════════════════════════════════════════
# 2. 표고점 로드 및 공간 결합
# ═══════════════════════════════════════════════════════════════
print("\n[2/5] 표고점 데이터 로드 및 공간 결합 중…")
elev = gpd.read_file(str(ELEV_SHP))
elev["HEIGHT"] = pd.to_numeric(elev["HEIGHT"], errors="coerce")
elev = elev.dropna(subset=["HEIGHT"])
elev = elev.to_crs("EPSG:5179")
print(f"  표고점 {len(elev)}개 (유효 HEIGHT)")

# 공간 결합: 표고점 → 행정동
elev_joined = gpd.sjoin(
    elev[["HEIGHT", "geometry"]],
    gdf_dong[["dong_code", "geometry"]],
    how="left",
    predicate="within",
)

# 동별 표고 통계
elev_stats = (
    elev_joined.dropna(subset=["dong_code"])
    .groupby("dong_code")["HEIGHT"]
    .agg(h_min="min", h_max="max", h_std="std", h_count="count")
    .reset_index()
)
elev_stats["h_range"] = elev_stats["h_max"] - elev_stats["h_min"]
print(f"  표고 데이터 있는 동: {len(elev_stats)}개")

# 행정동과 결합
gdf_dong = gdf_dong.merge(elev_stats, on="dong_code", how="left")

# 표고 데이터 없는 동: 주변 동 평균으로 채움
mean_range = gdf_dong["h_range"].median()
mean_std   = gdf_dong["h_std"].median()
gdf_dong["h_range"]  = gdf_dong["h_range"].fillna(mean_range)
gdf_dong["h_std"]    = gdf_dong["h_std"].fillna(mean_std)
gdf_dong["h_count"]  = gdf_dong["h_count"].fillna(0)
gdf_dong["has_elev"] = gdf_dong["h_count"] > 0
print(f"  표고 데이터 없어 중위값으로 보간한 동: "
      f"{(~gdf_dong['has_elev']).sum()}개")


# ═══════════════════════════════════════════════════════════════
# 3. 경사도 추정 및 Tobler 보정 적용
# ═══════════════════════════════════════════════════════════════
print("\n[3/5] 경사도 추정 및 보행속도 보정 중…")

# 경사 기울기 추정: h_range / 동 지름 (원형 가정)
gdf_dong["dong_diam_m"] = np.sqrt(gdf_dong["area_m2"]) * 1.13
gdf_dong["slope_est"]   = gdf_dong["h_range"] / gdf_dong["dong_diam_m"]

# Tobler 속도 비율 적용
gdf_dong["tobler_ratio"]      = gdf_dong["slope_est"].apply(tobler_speed_ratio)
gdf_dong["speed_slope_ms"]    = SPEED_SENIOR * gdf_dong["tobler_ratio"]
gdf_dong["dist_slope_m"]      = gdf_dong["speed_slope_ms"] * CUTOFF_MIN * 60
gdf_dong["dist_reduction_m"]  = DIST_SENIOR - gdf_dong["dist_slope_m"]
gdf_dong["dist_reduction_pct"]= (gdf_dong["dist_reduction_m"] / DIST_SENIOR * 100).round(1)
gdf_dong["dist_young_m"]      = DIST_YOUNG  # 일반인 참고용

print(f"  경사 추정값 평균: {gdf_dong['slope_est'].mean():.4f}")
print(f"  보정 후 노인 30분 도달 거리 평균: {gdf_dong['dist_slope_m'].mean():.0f}m "
      f"(평지: {DIST_SENIOR:.0f}m)")
print(f"  경사 보정으로 인한 추가 손실 평균: "
      f"{gdf_dong['dist_reduction_pct'].mean():.1f}%")

top5_slope = gdf_dong.nlargest(5, "slope_est")[
    ["full_name", "slope_est", "speed_slope_ms", "dist_slope_m"]
]
print("\n  경사도 상위 5개 동:")
print(top5_slope.to_string(index=False))

# CSV 저장: tobler_ratio_LEE.csv
OUT_CSV = OUT_DIR / "tobler_ratio_LEE.csv"
df_tobler = gdf_dong[["dong_code", "full_name", "tobler_ratio"]].copy()
df_tobler["tobler_ratio"] = df_tobler["tobler_ratio"].round(6)
df_tobler.to_csv(str(OUT_CSV), index=False, encoding="utf-8-sig")
print(f"\n  저장: {OUT_CSV}  ({len(df_tobler)}개 행정동)")


# ═══════════════════════════════════════════════════════════════
# 4. 지도 시각화
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] 지도 시각화 생성 중…")
gdf_wgs = gdf_dong.to_crs("EPSG:4326")
gdf_wgs["cx_wgs"] = gdf_wgs.geometry.centroid.x
gdf_wgs["cy_wgs"] = gdf_wgs.geometry.centroid.y

m = folium.Map(location=[37.5665, 126.978], zoom_start=11,
               tiles=None, prefer_canvas=True)
folium.TileLayer("CartoDB dark_matter", name="Dark Map").add_to(m)
folium.TileLayer("OpenStreetMap", name="일반 지도").add_to(m)

# 레이어 1: 경사도 추정값
p10_s = float(gdf_wgs["slope_est"].quantile(0.10))
p90_s = float(gdf_wgs["slope_est"].quantile(0.90))
cmap_slope = cm.LinearColormap(
    colors=["#F7FCF5", "#A1D99B", "#41AB5D", "#238B45", "#00441B"],
    vmin=p10_s, vmax=p90_s,
    caption="경사도 추정값 (높을수록 가파름)",
)
geojson_slope = json.loads(
    gdf_wgs[["dong_code", "full_name", "slope_est", "dist_slope_m",
             "dist_reduction_pct", "speed_slope_ms", "geometry"]].to_json()
)

def _style_slope(feat):
    v = feat["properties"].get("slope_est") or 0
    return {
        "fillColor":   cmap_slope(min(max(v, p10_s), p90_s)),
        "color":       "rgba(80,80,80,0.3)",
        "weight":      0.5,
        "fillOpacity": 0.82,
    }

fg_slope = folium.FeatureGroup(name="동별 경사도 추정값", show=True)
folium.GeoJson(
    data=geojson_slope,
    style_function=_style_slope,
    highlight_function=lambda x: {"fillOpacity": 0.95, "weight": 2, "color": "#FFD700"},
    tooltip=folium.GeoJsonTooltip(
        fields=["full_name", "slope_est", "speed_slope_ms",
                "dist_slope_m", "dist_reduction_pct"],
        aliases=["행정동", "경사도 추정", "보정 보행속도(m/s)",
                 "보정 도달 거리(m)", "추가 손실(%)"],
        localize=True, sticky=True,
        style="font-family:'Malgun Gothic',sans-serif;font-size:12px;",
    ),
).add_to(fg_slope)
fg_slope.add_to(m)
cmap_slope.add_to(m)

# 레이어 2: 경사 보정 추가 손실률
p10_r = float(gdf_wgs["dist_reduction_pct"].quantile(0.10))
p90_r = float(gdf_wgs["dist_reduction_pct"].quantile(0.90))
cmap_red = cm.LinearColormap(
    colors=["#FFF5F0", "#FCBBA1", "#FC7050", "#D73027", "#67000D"],
    vmin=p10_r, vmax=p90_r,
    caption="경사 보정으로 인한 추가 도달 거리 손실(%)",
)
geojson_red = json.loads(
    gdf_wgs[["dong_code", "full_name", "dist_reduction_pct",
             "dist_slope_m", "geometry"]].to_json()
)

def _style_red(feat):
    v = feat["properties"].get("dist_reduction_pct") or 0
    return {
        "fillColor":   cmap_red(min(max(v, p10_r), p90_r)),
        "color":       "rgba(80,80,80,0.3)",
        "weight":      0.5,
        "fillOpacity": 0.82,
    }

fg_red = folium.FeatureGroup(name="경사 보정 추가 손실률", show=False)
folium.GeoJson(
    data=geojson_red,
    style_function=_style_red,
    highlight_function=lambda x: {"fillOpacity": 0.95, "weight": 2, "color": "#FFD700"},
    tooltip=folium.GeoJsonTooltip(
        fields=["full_name", "dist_reduction_pct", "dist_slope_m"],
        aliases=["행정동", "추가 손실(%)", "보정 도달 거리(m)"],
        localize=True, sticky=True,
        style="font-family:'Malgun Gothic',sans-serif;font-size:12px;",
    ),
).add_to(fg_red)
fg_red.add_to(m)
cmap_red.add_to(m)

# 경사 상위 20개 동 마커
top20 = gdf_wgs.nlargest(20, "slope_est")
fg_top = folium.FeatureGroup(name="경사도 상위 20개 동", show=False)
for _, row in top20.iterrows():
    folium.CircleMarker(
        location=[row["cy_wgs"], row["cx_wgs"]],
        radius=8, color="#FF6600", weight=2,
        fill=True, fill_color="#FF6600", fill_opacity=0.85,
        tooltip=folium.Tooltip(
            f"<b>{row['full_name']}</b><br>"
            f"경사도: {row['slope_est']:.4f}<br>"
            f"보정 속도: {row['speed_slope_ms']:.3f} m/s "
            f"(평지: {SPEED_SENIOR:.3f} m/s)<br>"
            f"보정 도달 거리: {row['dist_slope_m']:.0f}m "
            f"(평지: {DIST_SENIOR:.0f}m)",
            sticky=True,
        ),
    ).add_to(fg_top)
fg_top.add_to(m)

folium.LayerControl(collapsed=False, position="topright").add_to(m)

mean_dist_slope  = float(gdf_dong["dist_slope_m"].mean())
mean_extra_loss  = float(gdf_dong["dist_reduction_pct"].mean())
worst_dong       = gdf_dong.nlargest(1, "slope_est").iloc[0]

title_html = f"""
<div style="
    position:fixed; top:10px; left:50%; transform:translateX(-50%);
    z-index:9999; background:rgba(10,10,20,0.92);
    border:1px solid #555; border-radius:8px;
    padding:10px 28px; text-align:center;
    font-family:'Malgun Gothic',sans-serif;
    box-shadow:0 2px 12px rgba(0,0,0,0.5);">
  <div style="font-size:16px;font-weight:bold;color:#fff;">
    경사도 보행속도 보정 (D3. 의료) — Tobler's Hiking Function
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:4px;">
    slope_est = h_range / dong_diam · V_adj = 0.88 × Tobler(s) / Tobler(0) m/s
  </div>
  <div style="font-size:11px;color:#ddd;margin-top:3px;">
    보정 후 노인 30분 도달 거리 평균: <b style="color:#FC7050">{mean_dist_slope:.0f}m</b>
    (평지 {DIST_SENIOR:.0f}m, 추가 손실 {mean_extra_loss:.1f}%)
  </div>
  <div style="font-size:10px;color:#aaa;margin-top:2px;">
    가장 가파른 동: {worst_dong['full_name']}
    ({worst_dong['dist_slope_m']:.0f}m까지만 도달 가능)
  </div>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

out10 = OUT_DIR / "10_slope_map.html"
m.save(str(out10))
print(f"  저장: {out10}")


# ═══════════════════════════════════════════════════════════════
# 5. 비교 차트 (보정 전후)
# ═══════════════════════════════════════════════════════════════
print("\n[5/5] 비교 차트 생성 중…")

# 구별 평균 경사도·보정 도달 거리
df_gu = (
    gdf_wgs.groupby("gu_name")
    .agg(
        slope_mean       =("slope_est",          "mean"),
        dist_flat        =("dist_slope_m",        lambda _: DIST_SENIOR),
        dist_slope       =("dist_slope_m",        "mean"),
        extra_loss       =("dist_reduction_pct",  "mean"),
    )
    .reset_index()
    .sort_values("slope_mean", ascending=True)
)
df_gu["dist_flat"] = DIST_SENIOR  # constant

fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=(
        "구별 평균 경사도 추정값",
        f"구별 노인 30분 도달 거리: 평지({DIST_SENIOR:.0f}m) vs 경사 보정",
    ),
    horizontal_spacing=0.12,
)

fig.add_trace(
    go.Bar(
        y=df_gu["gu_name"], x=df_gu["slope_mean"],
        orientation="h",
        marker=dict(color=df_gu["slope_mean"], colorscale="Greens"),
        text=df_gu["slope_mean"].map("{:.4f}".format),
        textposition="outside", showlegend=False,
    ),
    row=1, col=1,
)

fig.add_trace(
    go.Bar(y=df_gu["gu_name"], x=df_gu["dist_flat"],
           name=f"평지 기준 ({DIST_SENIOR:.0f}m)",
           orientation="h", marker_color="#4292C6", opacity=0.6),
    row=1, col=2,
)
fig.add_trace(
    go.Bar(y=df_gu["gu_name"], x=df_gu["dist_slope"],
           name="경사 보정 후",
           orientation="h", marker_color="#D73027", opacity=0.85,
           text=df_gu["dist_slope"].round(0).astype(int).astype(str) + "m",
           textposition="outside"),
    row=1, col=2,
)

fig.update_layout(
    title_text="경사도 보정 전후 노인 30분 도달 거리 비교 — Tobler's Hiking Function",
    font_family="Malgun Gothic",
    height=750,
    barmode="overlay",
    plot_bgcolor="#f8f8f8",
    legend=dict(orientation="h", y=-0.08),
)
fig.update_xaxes(title_text="경사도 추정값", row=1, col=1)
fig.update_xaxes(title_text="30분 도달 거리 (m)", row=1, col=2)

out11 = OUT_DIR / "11_slope_adjusted.html"
fig.write_html(str(out11))
print(f"  저장: {out11}")

print("\n" + "=" * 60)
print("경사도 보정 분석 완료!")
print(f"  평균 경사도 추정값: {gdf_dong['slope_est'].mean():.4f}")
print(f"  평지 노인 도달 거리: {DIST_SENIOR:.0f}m")
print(f"  경사 보정 후 평균: {gdf_dong['dist_slope_m'].mean():.0f}m")
print(f"  경사로 인한 추가 손실 평균: {gdf_dong['dist_reduction_pct'].mean():.1f}%")
print("=" * 60)
print("\n출력 파일:")
for f in [out10, out11, OUT_CSV]:
    print(f"  {f}")
