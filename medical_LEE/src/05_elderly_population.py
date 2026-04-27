"""
05_elderly_population.py  ·  D3 의료 — 고령 인구 이중 취약지 분석
──────────────────────────────────────────────────────────────────
아이디어: "노인이 많은 곳에 의료 공백이 겹친다"

구 단위 주민등록인구 통계(65세 이상)와
기존 동 단위 의료 접근성 손실률을 구 수준에서 결합하여
'고령 인구 밀도 × 의료 접근 손실' 이중 취약 구역을 식별한다.

데이터:
  등록인구(연령별_동별)_20260422233702.csv  ← 서울열린데이터광장 (구 단위)
  01_medical_access.py 재계산 결과 (구 단위 집계)

출력:
  ../outputs/12_elderly_access_bubble.html  ← 구별 버블차트 (이중 취약 사분면)
  ../outputs/13_double_jeopardy_map.html    ← 이중 취약 구 코로플레스 지도
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

SHP_PATH  = PROJ_ROOT / "prototype" / "끊어진서울(가제)" / "data" \
            / "bnd_oa_11_2025_2Q" / "bnd_oa_11_2025_2Q.shp"
HOSP_CSV  = DATA_DIR / "서울시 병의원 위치 정보.csv"
PHARM_CSV = DATA_DIR / "서울시 약국 인허가 정보.csv"
KIM_CACHE = PROJ_ROOT / "outputs-KIM" / "260418_submit" / "cache" / "dong_loss_ratio.csv"

# 인구 CSV — 파일명에 날짜가 포함되므로 glob으로 탐색
POP_FILES = sorted(DATA_DIR.glob("등록인구*.csv"))
POP_CSV   = POP_FILES[0] if POP_FILES else None

OUT_DIR.mkdir(exist_ok=True)

SPEED_YOUNG  = 1.28   # 팀 표준: 한음 외 2020
SPEED_SENIOR = 0.88   # 보행보조 노인 평균
DIST_YOUNG   = SPEED_YOUNG  * 30 * 60   # 2,304 m
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

print("=" * 60)
print("고령 인구 이중 취약지 분석 시작")
print("=" * 60)


# ═══════════════════════════════════════════════════════════════
# 1. 주민등록인구 파싱 (구 단위, 65세 이상)
# ═══════════════════════════════════════════════════════════════
print("\n[1/5] 주민등록인구 데이터 파싱 중…")
assert POP_CSV is not None, f"인구 CSV 파일을 찾을 수 없습니다: {DATA_DIR}/등록인구*.csv"

pop_raw = pd.read_csv(POP_CSV, encoding="utf-8")

# 0번 행이 실제 컬럼명(연령 구간)이므로 제거 후 필터
pop = pop_raw[pop_raw["동별(1)"] != "동별(1)"].copy()
pop = pop[pop["항목"] == "계"].copy()

# 2025 4/4분기 65세 이상 컬럼: suffix .14~.21
# (합계=없는suffix, 0~4세=.1, ..., 65~69세=.14, ..., 100세이상=.21)
age65_cols = [f"2025 4/4.{i}" for i in range(14, 22)]
total_col  = "2025 4/4"

for c in age65_cols + [total_col]:
    pop[c] = pd.to_numeric(
        pop[c].astype(str).str.replace(",", "").str.strip(),
        errors="coerce",
    )

pop["elderly_65plus"] = pop[age65_cols].sum(axis=1)
pop["total_pop"]      = pop[total_col]
pop["elderly_pct"]    = (pop["elderly_65plus"] / pop["total_pop"] * 100).round(2)

# 서울 25개 구만 (합계 행 제외)
seoul_gu_names = list(GU_MAP.values())
pop_gu = pop[pop["동별(1)"].isin(seoul_gu_names)][
    ["동별(1)", "elderly_65plus", "total_pop", "elderly_pct"]
].copy()
pop_gu.columns = ["gu_name", "elderly_65plus", "total_pop", "elderly_pct"]
pop_gu = pop_gu.reset_index(drop=True)

print(f"  구 데이터 {len(pop_gu)}개 파싱 완료")
print(f"  서울 전체 65세 이상 비율: "
      f"{pop_gu['elderly_65plus'].sum() / pop_gu['total_pop'].sum() * 100:.1f}%")
top3 = pop_gu.nlargest(3, "elderly_pct")[["gu_name", "elderly_pct"]]
print(f"  고령화 상위 3개 구: {list(top3.itertuples(index=False, name=None))}")


# ═══════════════════════════════════════════════════════════════
# 2. 의료 접근성 손실률 재계산 (구 단위)
# ═══════════════════════════════════════════════════════════════
print("\n[2/5] 의료 접근성 손실률 재계산 (구 단위) 중…")
t_wgs  = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
t_5174 = Transformer.from_crs("EPSG:5174", "EPSG:5179", always_xy=True)

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

hosp_raw = pd.read_csv(HOSP_CSV, encoding="cp949")
hosp = hosp_raw[
    hosp_raw["병원분류명"].isin(["의원", "병원", "보건소", "종합병원"])
].copy()
hosp = hosp.dropna(subset=["병원경도", "병원위도"])
hosp = hosp[(hosp["병원경도"] > 120) & (hosp["병원위도"] > 35)]
hosp["x5179"], hosp["y5179"] = t_wgs.transform(
    hosp["병원경도"].values, hosp["병원위도"].values
)

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

xy_all = np.vstack([
    np.column_stack([hosp["x5179"].values,  hosp["y5179"].values]),
    np.column_stack([pharm["x5179"].values, pharm["y5179"].values]),
])

def count_radius(xy, cx, cy, dist):
    d = np.sqrt((xy[:, 0] - cx) ** 2 + (xy[:, 1] - cy) ** 2)
    return int((d <= dist).sum())

# Tobler 경사 보정 (일반인/노인 동등 적용)
ELEV_SHP_05 = DATA_DIR / "서울시 경사도" / "표고 5000" / "N3P_F002.shp"
TOBLER_FLAT_05 = 6.0 * np.exp(-3.5 * abs(0 + 0.05))
try:
    _elev = gpd.read_file(str(ELEV_SHP_05))
    _elev["HEIGHT"] = pd.to_numeric(_elev["HEIGHT"], errors="coerce")
    _elev = _elev.dropna(subset=["HEIGHT"]).to_crs("EPSG:5179")
    _ej = gpd.sjoin(_elev[["HEIGHT","geometry"]], gdf_dong[["dong_code","geometry"]],
                    how="left", predicate="within")
    _es = (_ej.dropna(subset=["dong_code"])
           .groupby("dong_code")["HEIGHT"].agg(h_min="min", h_max="max").reset_index())
    _es["h_range"] = _es["h_max"] - _es["h_min"]
    gdf_dong = gdf_dong.merge(_es[["dong_code","h_range"]], on="dong_code", how="left")
    gdf_dong["h_range"] = gdf_dong["h_range"].fillna(gdf_dong["h_range"].median())
    gdf_dong["_diam"] = np.sqrt(gdf_dong.geometry.area) * 1.13
    gdf_dong["_slope"] = gdf_dong["h_range"] / gdf_dong["_diam"]
    gdf_dong["_tobler"] = gdf_dong["_slope"].apply(
        lambda s: (6.0 * np.exp(-3.5 * abs(s + 0.05))) / TOBLER_FLAT_05)
    dist_young_arr_05  = (SPEED_YOUNG  * gdf_dong["_tobler"] * 30 * 60).values
    dist_senior_arr_05 = (SPEED_SENIOR * gdf_dong["_tobler"] * 30 * 60).values
except Exception:
    dist_young_arr_05  = np.full(len(gdf_dong), DIST_YOUNG)
    dist_senior_arr_05 = np.full(len(gdf_dong), DIST_SENIOR)

young_list, senior_list = [], []
for i, (_, row) in enumerate(gdf_dong.iterrows()):
    cx, cy = row["cx"], row["cy"]
    young_list.append(count_radius(xy_all, cx, cy, dist_young_arr_05[i]))
    senior_list.append(count_radius(xy_all, cx, cy, dist_senior_arr_05[i]))

gdf_dong["n_young"]  = young_list
gdf_dong["n_senior"] = senior_list
gdf_dong["loss_pct"] = np.where(
    gdf_dong["n_young"] > 0,
    (1 - gdf_dong["n_senior"] / gdf_dong["n_young"]) * 100, 0.0,
).round(1)

# 구 단위 집계
df_gu_access = (
    gdf_dong.groupby("gu_name")
    .agg(
        loss_pct_mean=("loss_pct", "mean"),
        n_young_mean =("n_young",  "mean"),
        n_senior_mean=("n_senior", "mean"),
        dong_count   =("dong_code","count"),
    )
    .reset_index()
)

print(f"  의료 접근성 집계 완료 (25개 구)")


# ═══════════════════════════════════════════════════════════════
# 3. 통합 데이터 생성 (인구 + 접근성)
# ═══════════════════════════════════════════════════════════════
print("\n[3/5] 인구·접근성 통합 데이터 생성 중…")
df_merged = pd.merge(pop_gu, df_gu_access, on="gu_name", how="inner")

# 이중 취약 지표: z-score 기반 분류
df_merged["elderly_z"] = (
    (df_merged["elderly_pct"] - df_merged["elderly_pct"].mean()) /
    df_merged["elderly_pct"].std()
)
df_merged["loss_z"] = (
    (df_merged["loss_pct_mean"] - df_merged["loss_pct_mean"].mean()) /
    df_merged["loss_pct_mean"].std()
)
df_merged["double_jeopardy_score"] = (df_merged["elderly_z"] + df_merged["loss_z"]) / 2

# 4분면 분류
med_e = df_merged["elderly_pct"].median()
med_l = df_merged["loss_pct_mean"].median()
df_merged["quadrant"] = "기타"
df_merged.loc[
    (df_merged["elderly_pct"] >= med_e) & (df_merged["loss_pct_mean"] >= med_l),
    "quadrant"
] = "이중 취약 (고령↑·손실↑)"
df_merged.loc[
    (df_merged["elderly_pct"] >= med_e) & (df_merged["loss_pct_mean"] < med_l),
    "quadrant"
] = "고령↑·손실↓ (양호)"
df_merged.loc[
    (df_merged["elderly_pct"] < med_e) & (df_merged["loss_pct_mean"] >= med_l),
    "quadrant"
] = "고령↓·손실↑ (시설 과소)"

n_dj = int((df_merged["quadrant"] == "이중 취약 (고령↑·손실↑)").sum())
top3_dj = df_merged.nlargest(3, "double_jeopardy_score")[
    ["gu_name", "elderly_pct", "loss_pct_mean", "double_jeopardy_score"]
]
print(f"  이중 취약 구 (고령↑ & 접근 손실↑): {n_dj}개")
print(f"  이중 취약 점수 상위 3개 구:")
print(top3_dj.to_string(index=False))


# ═══════════════════════════════════════════════════════════════
# 4. 버블차트 (Plotly)
# ═══════════════════════════════════════════════════════════════
print("\n[4/5] 버블차트 생성 중…")

QUAD_COLORS = {
    "이중 취약 (고령↑·손실↑)": "#D73027",
    "고령↑·손실↓ (양호)":      "#4292C6",
    "고령↓·손실↑ (시설 과소)": "#F4A460",
    "기타":                    "#AAAAAA",
}

fig_bubble = go.Figure()
for quad, color in QUAD_COLORS.items():
    sub = df_merged[df_merged["quadrant"] == quad]
    if sub.empty:
        continue
    fig_bubble.add_trace(go.Scatter(
        x=sub["elderly_pct"],
        y=sub["loss_pct_mean"],
        mode="markers+text",
        name=quad,
        marker=dict(
            color=color,
            size=(sub["elderly_65plus"] / 10000).clip(8, 30),
            opacity=0.85,
            line=dict(color="white", width=1),
        ),
        text=sub["gu_name"],
        textposition="top center",
        textfont=dict(size=10),
        customdata=np.column_stack([
            sub["elderly_65plus"], sub["total_pop"],
            sub["n_young_mean"].round(1), sub["n_senior_mean"].round(1),
        ]),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "65세 이상 비율: %{x:.1f}%<br>"
            "의료 접근 손실률: %{y:.1f}%<br>"
            "65세 이상 인구: %{customdata[0]:,}명<br>"
            "전체 인구: %{customdata[1]:,}명<br>"
            "일반인 30분권 평균: %{customdata[2]}개<br>"
            "노인 30분권 평균: %{customdata[3]}개<extra></extra>"
        ),
    ))

# 중앙선 (중위값 기준 4분면 구분선)
fig_bubble.add_vline(x=med_e, line_dash="dash", line_color="gray",
                     annotation_text=f"고령화율 중위: {med_e:.1f}%",
                     annotation_position="top right")
fig_bubble.add_hline(y=med_l, line_dash="dash", line_color="gray",
                     annotation_text=f"손실률 중위: {med_l:.1f}%",
                     annotation_position="right")

# 이중 취약 구역 음영
fig_bubble.add_shape(
    type="rect",
    x0=med_e, x1=df_merged["elderly_pct"].max() + 1,
    y0=med_l, y1=df_merged["loss_pct_mean"].max() + 2,
    fillcolor="#D73027", opacity=0.08,
    line=dict(color="#D73027", width=1, dash="dot"),
)

fig_bubble.update_layout(
    title="서울 25개 구 — 고령 인구 비율 × 의료 접근 손실률 이중 취약 분석<br>"
          "<sup>버블 크기: 65세 이상 인구 수 · 우상단 = 이중 취약 구역</sup>",
    xaxis_title="65세 이상 인구 비율 (%)",
    yaxis_title="노인 의료 접근 손실률 (%, 일반인 대비)",
    font_family="Malgun Gothic",
    height=580,
    plot_bgcolor="#f8f8f8",
    legend=dict(orientation="h", y=-0.15),
)

out12 = OUT_DIR / "12_elderly_access_bubble.html"
fig_bubble.write_html(str(out12))
print(f"  저장: {out12}")


# ═══════════════════════════════════════════════════════════════
# 5. 이중 취약 지도 (Folium)
# ═══════════════════════════════════════════════════════════════
print("\n[5/5] 이중 취약 지도 생성 중…")

# 구 단위 GeoDataFrame 생성
gdf_gu = (
    gdf_dong.dissolve(by="gu_name", as_index=False)
            .rename(columns={"gu_name": "gu_name"})
)
gdf_gu = gdf_gu.merge(df_merged, on="gu_name", how="left")
gdf_gu_wgs = gdf_gu.to_crs("EPSG:4326")
gdf_gu_wgs["cx_wgs"] = gdf_gu_wgs.geometry.centroid.x
gdf_gu_wgs["cy_wgs"] = gdf_gu_wgs.geometry.centroid.y

m = folium.Map(location=[37.5665, 126.978], zoom_start=11,
               tiles=None, prefer_canvas=True)
folium.TileLayer("CartoDB dark_matter", name="Dark Map").add_to(m)
folium.TileLayer("OpenStreetMap", name="일반 지도").add_to(m)

# 코로플레스: 이중 취약 점수
vmin_dj = float(gdf_gu_wgs["double_jeopardy_score"].quantile(0.05))
vmax_dj = float(gdf_gu_wgs["double_jeopardy_score"].quantile(0.95))
cmap_dj = cm.LinearColormap(
    colors=["#FFF5F0", "#FCBBA1", "#FC7050", "#D73027", "#67000D"],
    vmin=vmin_dj, vmax=vmax_dj,
    caption="이중 취약 점수 (고령화율 + 의료 손실률 복합)",
)
geojson_dj = json.loads(
    gdf_gu_wgs[[
        "gu_name", "elderly_pct", "loss_pct_mean",
        "double_jeopardy_score", "quadrant", "geometry"
    ]].to_json()
)

def _style_dj(feat):
    v = feat["properties"].get("double_jeopardy_score") or 0
    return {
        "fillColor":   cmap_dj(min(max(v, vmin_dj), vmax_dj)),
        "color":       "rgba(80,80,80,0.5)",
        "weight":      1,
        "fillOpacity": 0.80,
    }

fg_dj = folium.FeatureGroup(name="이중 취약 점수 코로플레스", show=True)
folium.GeoJson(
    data=geojson_dj,
    style_function=_style_dj,
    highlight_function=lambda x: {"fillOpacity": 0.95, "weight": 2, "color": "#FFD700"},
    tooltip=folium.GeoJsonTooltip(
        fields=["gu_name", "elderly_pct", "loss_pct_mean",
                "double_jeopardy_score", "quadrant"],
        aliases=["구", "65세 이상(%)", "의료 손실(%)",
                 "이중 취약 점수", "분류"],
        localize=True, sticky=True,
        style="font-family:'Malgun Gothic',sans-serif;font-size:12px;",
    ),
).add_to(fg_dj)
fg_dj.add_to(m)
cmap_dj.add_to(m)

# 이중 취약 구 강조 라벨
dj_gu = gdf_gu_wgs[gdf_gu_wgs["quadrant"] == "이중 취약 (고령↑·손실↑)"]
for _, row in dj_gu.iterrows():
    folium.Marker(
        location=[row["cy_wgs"], row["cx_wgs"]],
        icon=folium.DivIcon(
            html=f'<div style="font-family:Malgun Gothic;font-size:11px;'
                 f'font-weight:bold;color:#FF4444;'
                 f'text-shadow:0 0 3px #000,0 0 6px #000;">'
                 f'{row["gu_name"]}<br>'
                 f'<span style="font-size:9px;color:#FFAAAA;">'
                 f'고령 {row["elderly_pct"]:.1f}% / 손실 {row["loss_pct_mean"]:.1f}%</span></div>',
            icon_size=(100, 30),
            icon_anchor=(50, 0),
        ),
    ).add_to(m)

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
    고령 인구 × 의료 접근 손실 이중 취약지 (D3. 의료)
  </div>
  <div style="font-size:11px;color:#aaa;margin-top:4px;">
    2025년 4분기 주민등록인구 (구 단위) × 노인 30분권 의료 접근 손실률
  </div>
  <div style="font-size:11px;color:#FC7050;margin-top:3px;font-weight:bold;">
    이중 취약 구 (고령화↑ + 의료 손실↑): {n_dj}개 구
  </div>
  <div style="font-size:10px;color:#aaa;margin-top:2px;">
    고령화율 중위 {med_e:.1f}% · 의료 손실률 중위 {med_l:.1f}%
  </div>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

out13 = OUT_DIR / "13_double_jeopardy_map.html"
m.save(str(out13))
print(f"  저장: {out13}")

print("\n" + "=" * 60)
print("고령 인구 이중 취약지 분석 완료!")
print(f"  이중 취약 구 수: {n_dj}개")
print(f"  이중 취약 점수 상위 구:")
for _, r in top3_dj.iterrows():
    print(f"    {r['gu_name']}: 고령 {r['elderly_pct']:.1f}% / 손실 {r['loss_pct_mean']:.1f}%")
print("=" * 60)
print("\n출력 파일:")
for f in [out12, out13]:
    print(f"  {f}")
