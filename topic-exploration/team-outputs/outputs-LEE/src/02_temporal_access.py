"""
02_temporal_access.py  ·  D3 의료 — 시간대별 접근성 분석
──────────────────────────────────────────────────────────
아이디어: "주말과 야간의 30분은 다르게 흐른다"

노인 보행속도(0.88 m/s) 기준 30분권 내에서,
평일 낮 / 평일 저녁 / 토요일 / 일요일 각 시간대에
실제로 열려 있는 의료시설 수를 동 단위로 비교.

출력:
  ../outputs/05_temporal_map.html       ← 시간대별 코로플레스 지도 (4개 레이어)
  ../outputs/06_temporal_compare.html   ← 평일 낮 vs 각 시간대 손실률 바차트
  ../outputs/07_temporal_scatter.html   ← 평일 낮 vs 일요일 산점도
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

SHP_PATH   = PROJ_ROOT / "prototype" / "끊어진서울(가제)" / "data" \
             / "bnd_oa_11_2025_2Q" / "bnd_oa_11_2025_2Q.shp"
HOSP_CSV   = DATA_DIR / "서울시 병의원 위치 정보.csv"
PHARM_CSV  = DATA_DIR / "서울시 약국 운영시간  정보.csv"
KIM_CACHE  = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"
OUT_DIR.mkdir(exist_ok=True)

# ── 파라미터 (팀 표준: 한음 외 2020) ────────────────────────────
SPEED_SENIOR = 0.88
DIST_SENIOR  = SPEED_SENIOR * 30 * 60   # 1,584 m

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

# 분석할 시간대 (label, 요일컬럼 접미사, HHMM)
TIME_SLOTS = [
    ("평일_낮",   "월요일", 1400),
    ("평일_저녁", "월요일", 2000),
    ("토요일",    "토요일", 1400),
    ("일요일",    "일요일", 1200),
]

print("=" * 60)
print("시간대별 의료 접근성 분석 시작")
print("=" * 60)


# ── 영업시간 판단 유틸 ─────────────────────────────────────────────
def to_minutes(t):
    """HHMM 정수 → 분 (예: 1930 → 1170)"""
    t = int(t)
    return (t // 100) * 60 + (t % 100)


def open_mask(df: pd.DataFrame, day: str, time_hhmm: int) -> np.ndarray:
    """요일·시각에 열려 있는 시설 불리언 배열 반환"""
    s_col = f"진료시간({day})S"
    c_col = f"진료시간({day})C"
    if s_col not in df.columns or c_col not in df.columns:
        return np.zeros(len(df), dtype=bool)
    s_vals = pd.to_numeric(df[s_col], errors="coerce")
    c_vals = pd.to_numeric(df[c_col], errors="coerce")
    q = to_minutes(time_hhmm)
    mask = (
        s_vals.notna() & c_vals.notna() &
        (s_vals.apply(lambda v: to_minutes(v) if pd.notna(v) else 9999) <= q) &
        (c_vals.apply(lambda v: to_minutes(v) if pd.notna(v) else 0)   >= q)
    )
    return mask.values


# ═══════════════════════════════════════════════════════════════
# 1. 행정동 경계 로드
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
print(f"  행정동 {len(gdf_dong)}개 로드 완료")


# ═══════════════════════════════════════════════════════════════
# 2. 의료시설 로드 (위치 + 진료시간)
# ═══════════════════════════════════════════════════════════════
print("\n[2/5] 의료시설 데이터 로드 중…")
t_wgs = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

# 2-a. 병의원
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

# 2-b. 약국 (운영시간 파일 — WGS84 좌표 포함)
pharm_raw = pd.read_csv(PHARM_CSV, encoding="cp949")
pharm = pharm_raw.dropna(subset=["병원경도", "병원위도"]).copy()
pharm["병원경도"] = pd.to_numeric(pharm["병원경도"], errors="coerce")
pharm["병원위도"] = pd.to_numeric(pharm["병원위도"], errors="coerce")
pharm = pharm.dropna(subset=["병원경도", "병원위도"])
pharm = pharm[(pharm["병원경도"] > 120) & (pharm["병원위도"] > 35)]
pharm["x5179"], pharm["y5179"] = t_wgs.transform(
    pharm["병원경도"].values, pharm["병원위도"].values
)
print(f"  약국: {len(pharm)}개")


# ═══════════════════════════════════════════════════════════════
# 3. 시간대별 접근 가능 시설 수 계산
# ═══════════════════════════════════════════════════════════════
print("\n[3/5] 시간대별 접근 가능 시설 수 계산 중…")

xy_hosp  = np.column_stack([hosp["x5179"].values,  hosp["y5179"].values])
xy_pharm = np.column_stack([pharm["x5179"].values, pharm["y5179"].values])


def count_open_in_radius(xy: np.ndarray, mask: np.ndarray,
                         cx: float, cy: float) -> int:
    d = np.sqrt((xy[:, 0] - cx) ** 2 + (xy[:, 1] - cy) ** 2)
    return int(((d <= DIST_SENIOR) & mask).sum())


for label, day, time_hhmm in TIME_SLOTS:
    h_mask = open_mask(hosp,  day, time_hhmm)
    p_mask = open_mask(pharm, day, time_hhmm)
    n_col  = f"n_{label}"

    counts = []
    for _, row in gdf_dong.iterrows():
        cx, cy = row["cx"], row["cy"]
        n_h = count_open_in_radius(xy_hosp,  h_mask, cx, cy)
        n_p = count_open_in_radius(xy_pharm, p_mask, cx, cy)
        counts.append(n_h + n_p)
    gdf_dong[n_col] = counts
    print(f"  [{label}] 동 평균 접근 가능 시설 수: "
          f"{gdf_dong[n_col].mean():.1f}개  "
          f"(0개 동: {(gdf_dong[n_col] == 0).sum()}개)")

# 손실률 계산 (기준: 평일 낮)
base = "n_평일_낮"
for label, _, _ in TIME_SLOTS[1:]:
    n_col   = f"n_{label}"
    l_col   = f"loss_{label}_pct"
    gdf_dong[l_col] = np.where(
        gdf_dong[base] > 0,
        (1 - gdf_dong[n_col] / gdf_dong[base]) * 100, 0.0,
    ).round(1)

print(f"\n  평일 저녁 평균 손실률: {gdf_dong['loss_평일_저녁_pct'].mean():.1f}%")
print(f"  토요일    평균 손실률: {gdf_dong['loss_토요일_pct'].mean():.1f}%")
print(f"  일요일    평균 손실률: {gdf_dong['loss_일요일_pct'].mean():.1f}%")


# ═══════════════════════════════════════════════════════════════
# 4. 지도 시각화 (Folium — 4개 레이어)
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] 지도 시각화 생성 중…")
gdf_wgs      = gdf_dong.to_crs("EPSG:4326")
gdf_wgs["cx_wgs"] = gdf_wgs.geometry.centroid.x
gdf_wgs["cy_wgs"] = gdf_wgs.geometry.centroid.y

m = folium.Map(location=[37.5665, 126.978], zoom_start=11,
               tiles=None, prefer_canvas=True)
folium.TileLayer("CartoDB dark_matter", name="Dark Map").add_to(m)
folium.TileLayer("OpenStreetMap", name="일반 지도").add_to(m)

LAYER_CFG = [
    ("n_평일_낮",   "평일 낮 (14시)",   "#4292C6", True),
    ("n_평일_저녁", "평일 저녁 (20시)", "#D73027", False),
    ("n_토요일",    "토요일 (14시)",    "#F4A460", False),
    ("n_일요일",    "일요일 (12시)",    "#808080", False),
]

for n_col, layer_name, _, show in LAYER_CFG:
    sub = gdf_wgs[gdf_wgs[n_col] >= 0]
    p10 = float(sub[n_col].quantile(0.05))
    p90 = float(sub[n_col].quantile(0.95))
    cmap = cm.LinearColormap(
        colors=["#67000D", "#D73027", "#FC7050", "#FCBBA1", "#FFF5F0"],
        vmin=max(p10, 0), vmax=max(p90, 1),
        caption=f"{layer_name} — 노인 30분권 내 의료시설 수",
    )
    geojson_data = json.loads(
        gdf_wgs[["dong_code", "gu_name", "full_name", n_col, "geometry"]].to_json()
    )

    def _style(feat, col=n_col, cmap=cmap, p10=p10, p90=p90):
        v = feat["properties"].get(col) or 0
        return {
            "fillColor":   cmap(min(max(v, p10), p90)),
            "color":       "rgba(80,80,80,0.3)",
            "weight":      0.5,
            "fillOpacity": 0.82,
        }

    fg = folium.FeatureGroup(name=layer_name, show=show)
    folium.GeoJson(
        data=geojson_data,
        style_function=_style,
        highlight_function=lambda x: {"fillOpacity": 0.95, "weight": 2, "color": "#FFD700"},
        tooltip=folium.GeoJsonTooltip(
            fields=["full_name", n_col],
            aliases=["행정동", "접근 가능 시설 수"],
            localize=True, sticky=True,
            style="font-family:'Malgun Gothic',sans-serif;font-size:13px;",
        ),
    ).add_to(fg)
    fg.add_to(m)
    cmap.add_to(m)

# 일요일 0개 동 마커
zero_sunday = gdf_wgs[gdf_wgs["n_일요일"] == 0]
fg_zero = folium.FeatureGroup(name="일요일 완전 차단 동", show=False)
for _, row in zero_sunday.iterrows():
    folium.CircleMarker(
        location=[row["cy_wgs"], row["cx_wgs"]],
        radius=6, color="#FF0000", weight=2,
        fill=True, fill_color="#FF0000", fill_opacity=0.9,
        tooltip=folium.Tooltip(
            f"<b>{row['full_name']}</b><br>일요일 접근 가능 시설: 0개",
            sticky=True,
        ),
    ).add_to(fg_zero)
fg_zero.add_to(m)

folium.LayerControl(collapsed=False, position="topright").add_to(m)

# 제목 패널
loss_eve = float(gdf_dong["loss_평일_저녁_pct"].mean())
loss_sat = float(gdf_dong["loss_토요일_pct"].mean())
loss_sun = float(gdf_dong["loss_일요일_pct"].mean())
n_zero_sun = int((gdf_dong["n_일요일"] == 0).sum())

title_html = f"""
<div style="
    position:fixed; top:10px; left:50%; transform:translateX(-50%);
    z-index:9999; background:rgba(10,10,20,0.92);
    border:1px solid #555; border-radius:8px;
    padding:10px 28px; text-align:center;
    font-family:'Malgun Gothic',sans-serif;
    box-shadow:0 2px 12px rgba(0,0,0,0.5);">
  <div style="font-size:16px;font-weight:bold;color:#fff;">
    시간대별 노인 의료 접근성 (D3. 의료)
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:4px;">
    보행보조 노인(0.88 m/s) 30분권 · 실제 운영 시설 수 기준
  </div>
  <div style="font-size:11px;color:#ddd;margin-top:3px;">
    평일 저녁 손실 <b style="color:#FC7050">{loss_eve:.1f}%</b> &nbsp;|&nbsp;
    토요일 손실 <b style="color:#F4A460">{loss_sat:.1f}%</b> &nbsp;|&nbsp;
    일요일 손실 <b style="color:#aaa">{loss_sun:.1f}%</b>
  </div>
  <div style="font-size:10px;color:#f66;margin-top:2px;">
    ⚠ 일요일 12시 기준 접근 가능 시설 0개 동: <b>{n_zero_sun}개</b>
  </div>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

out5 = OUT_DIR / "05_temporal_map.html"
m.save(str(out5))
print(f"  저장: {out5}")


# ═══════════════════════════════════════════════════════════════
# 5. 통계 차트 (Plotly)
# ═══════════════════════════════════════════════════════════════
print("\n[5/5] 통계 차트 생성 중…")

# ── 5-a. 구별 시간대별 평균 접근 가능 시설 수 ─────────────────
df_plot = gdf_wgs[["full_name", "gu_name",
                   "n_평일_낮", "n_평일_저녁", "n_토요일", "n_일요일",
                   "loss_평일_저녁_pct", "loss_토요일_pct", "loss_일요일_pct"]].copy()

df_gu = (
    df_plot.groupby("gu_name")
    .agg(
        n_평일낮  =("n_평일_낮",         "mean"),
        n_평일저녁=("n_평일_저녁",        "mean"),
        n_토요일  =("n_토요일",           "mean"),
        n_일요일  =("n_일요일",           "mean"),
        loss_eve  =("loss_평일_저녁_pct", "mean"),
        loss_sat  =("loss_토요일_pct",    "mean"),
        loss_sun  =("loss_일요일_pct",    "mean"),
    )
    .reset_index()
    .sort_values("loss_sun", ascending=False)
)

fig_bar = make_subplots(
    rows=1, cols=2,
    subplot_titles=("구별 평균 접근 가능 시설 수 (4개 시간대)",
                    "구별 평일 낮 대비 손실률 (%)"),
    horizontal_spacing=0.12,
)

colors_slots = ["#4292C6", "#D73027", "#F4A460", "#808080"]
slot_labels  = ["평일 낮(14시)", "평일 저녁(20시)", "토요일(14시)", "일요일(12시)"]
n_cols       = ["n_평일낮", "n_평일저녁", "n_토요일", "n_일요일"]

for i, (nc, sl, col) in enumerate(zip(n_cols, slot_labels, colors_slots)):
    df_s = df_gu.sort_values("n_평일낮", ascending=True)
    fig_bar.add_trace(
        go.Bar(
            y=df_s["gu_name"], x=df_s[nc],
            name=sl, orientation="h",
            marker_color=col, opacity=0.85,
            showlegend=True,
        ),
        row=1, col=1,
    )

loss_cols   = ["loss_eve", "loss_sat", "loss_sun"]
loss_labels = ["평일 저녁(20시)", "토요일(14시)", "일요일(12시)"]
loss_colors = ["#D73027", "#F4A460", "#808080"]
df_loss = df_gu.sort_values("loss_sun", ascending=True)
for lc, ll, lcolor in zip(loss_cols, loss_labels, loss_colors):
    fig_bar.add_trace(
        go.Bar(
            y=df_loss["gu_name"], x=df_loss[lc],
            name=ll, orientation="h",
            marker_color=lcolor, opacity=0.85,
            showlegend=False,
        ),
        row=1, col=2,
    )

fig_bar.update_layout(
    title_text="서울 25개 구 시간대별 의료 접근성 비교",
    font_family="Malgun Gothic",
    height=750,
    barmode="group",
    plot_bgcolor="#f8f8f8",
    legend=dict(orientation="h", y=-0.08),
)
fig_bar.update_xaxes(title_text="평균 접근 가능 시설 수", row=1, col=1)
fig_bar.update_xaxes(title_text="손실률(%)",              row=1, col=2)

out6 = OUT_DIR / "06_temporal_compare.html"
fig_bar.write_html(str(out6))
print(f"  저장: {out6}")

# ── 5-b. 평일 낮 vs 일요일 산점도 ─────────────────────────────
fig_sc = go.Figure()
fig_sc.add_trace(go.Scatter(
    x=df_plot["n_평일_낮"],
    y=df_plot["n_일요일"],
    mode="markers",
    marker=dict(
        color=df_plot["loss_일요일_pct"],
        colorscale="RdYlGn_r",
        size=5, opacity=0.65,
        colorbar=dict(title="일요일 손실률(%)"),
        showscale=True,
    ),
    text=df_plot["full_name"] + "<br>일요일 손실: "
         + df_plot["loss_일요일_pct"].round(1).astype(str) + "%",
    hovertemplate="%{text}<br>평일 낮: %{x}개 / 일요일: %{y}개<extra></extra>",
))
max_v = int(df_plot["n_평일_낮"].max()) + 5
fig_sc.add_trace(go.Scatter(
    x=[0, max_v], y=[0, max_v],
    mode="lines", line=dict(dash="dash", color="gray", width=1),
    name="손실 0% 기준선",
))
fig_sc.update_layout(
    title="평일 낮(14시) vs 일요일(12시) 동별 노인 의료 접근 시설 수",
    xaxis_title="평일 낮 접근 가능 시설 수",
    yaxis_title="일요일 접근 가능 시설 수",
    font_family="Malgun Gothic",
    height=520,
    plot_bgcolor="#f8f8f8",
)
out7 = OUT_DIR / "07_temporal_scatter.html"
fig_sc.write_html(str(out7))
print(f"  저장: {out7}")

print("\n" + "=" * 60)
print("시간대별 접근성 분석 완료!")
print(f"  평일 저녁(20시) 평균 손실률: {loss_eve:.1f}%")
print(f"  토요일(14시)    평균 손실률: {loss_sat:.1f}%")
print(f"  일요일(12시)    평균 손실률: {loss_sun:.1f}%")
print(f"  일요일 완전 차단 동: {n_zero_sun}개")
print("=" * 60)
print("\n출력 파일:")
for f in [out5, out6, out7]:
    print(f"  {f}")
