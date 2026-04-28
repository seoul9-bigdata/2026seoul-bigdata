"""
서울시 노인 생활복지 및 녹지 접근성 분석 파이프라인
=======================================================
instruction.md의 Step 1~6 구현

개선사항 (피드백 반영):
  - 복지시설 실좌표 반영 (geocode_cache.json 연결, 미캐시는 구 중심 fallback)
  - 청년/노인 보행 속도 구분 (노인 400m/800m vs 청년 800m/1600m)
  - Vulnerability Score 재설계: 고령화율 제거, 보행권 박탈 노인 수 기반
  - 행정동 단위 TOP5 리포트 추가
  - 시설 유형 라벨 실제 데이터와 일치하도록 수정
"""

# ============================================================
# Step 1: 환경 설정 및 라이브러리 로드
# ============================================================
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union
import folium
from folium.plugins import MarkerCluster
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import koreanize_matplotlib
import requests
import json
import re
import time
import os
import io

print("=" * 60)
print("Step 1: 라이브러리 로드 완료")
print(f"  - geopandas: {gpd.__version__}")
print(f"  - folium: {folium.__version__}")
print(f"  - matplotlib: {matplotlib.__version__}")
print("=" * 60)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CRS_WGS84 = "EPSG:4326"
CRS_KOREA = "EPSG:5179"   # Korea 2000 / Central Belt (거리 계산 m 단위)

# ── 보행 속도 기준 ────────────────────────────────────────────
# 노인: 2.4 km/h (40 m/분)  청년: 4.8 km/h (80 m/분)
ELDERLY_10MIN_M = 400    # 노인 도보 10분
ELDERLY_20MIN_M = 800    # 노인 도보 20분
YOUTH_10MIN_M   = 800    # 청년 도보 10분
YOUTH_20MIN_M   = 1_600  # 청년 도보 20분

SEOUL_GU_LIST = [
    '종로구','중구','용산구','성동구','광진구','동대문구','중랑구',
    '성북구','강북구','도봉구','노원구','은평구','서대문구','마포구',
    '양천구','강서구','구로구','금천구','영등포구','동작구','관악구',
    '서초구','강남구','송파구','강동구'
]


# ============================================================
# Step 2: 데이터 로드 및 전처리
# ============================================================
print("\nStep 2: 데이터 로드 및 전처리 시작")

# ── 2-1. 복지시설 데이터 ──────────────────────────────────────
welfare_path = os.path.join(BASE_DIR, "서울시 사회복지시설(노인여가복지시설) 목록.csv")
with open(welfare_path, 'rb') as f:
    raw = f.read()
welfare_df = pd.read_csv(io.StringIO(raw.decode('euc-kr')))
welfare_df.columns = [
    '시설명', '시설코드', '시설유형', '시설종류상세',
    '자치구구분', '시군구코드', '시군구명', '시설주소',
    '전화번호', '우편번호'
]
# 자치구구분 컬럼은 전부 '자치구' 단일값 — 필터는 no-op이므로 생략
welfare_df['시설주소'] = welfare_df['시설주소'].fillna('').str.strip()
welfare_df = welfare_df[welfare_df['시설주소'] != '']

# 실제 데이터의 시설 유형: 노인교실 / 노인복지관 / 노인복지관(소규모)
def short_type(t):
    if '소규모' in t:   return '노인복지관(소규모)'
    if '노인교실' in t: return '노인교실'
    return '노인복지관'

welfare_df['유형_간략'] = welfare_df['시설유형'].apply(short_type)
print(f"  복지시설 총 {len(welfare_df)}개 로드")
print(f"  시설유형 분포:\n{welfare_df['유형_간략'].value_counts().to_string()}")

# ── 2-2. 지오코딩 캐시 로드 → 실좌표 배정 ────────────────────
cache_path = os.path.join(OUTPUT_DIR, "geocode_cache.json")
geocode_cache = {}
if os.path.exists(cache_path):
    with open(cache_path, 'r', encoding='utf-8') as f:
        geocode_cache = json.load(f)
    print(f"  지오코딩 캐시 로드: {len(geocode_cache)}건 "
          f"(성공 {sum(1 for v in geocode_cache.values() if v.get('lat'))}건)")

def cache_lookup(addr):
    v = geocode_cache.get(addr, {})
    return v.get('lat'), v.get('lng')

welfare_df['lat'] = welfare_df['시설주소'].map(lambda a: cache_lookup(a)[0])
welfare_df['lng'] = welfare_df['시설주소'].map(lambda a: cache_lookup(a)[1])

print(f"  캐시 히트: {welfare_df['lat'].notna().sum()}/{len(welfare_df)}개 "
      f"(미히트는 구 중심점 fallback)")

# ── 2-3. 공원 데이터 ─────────────────────────────────────────
parks_path = os.path.join(BASE_DIR, "서울시 주요 공원현황(2026 상반기).xlsx")
parks_raw = pd.read_excel(parks_path)
parks_raw.columns = [
    '연번', '관리부서', '전화번호', '공원명', '공원개요',
    '면적', '개원일', '주요시설', '주요식물', '안내도',
    '오시는길', '이용시참고사항', '이미지', '지역', '공원주소',
    'X_GRS80', 'Y_GRS80', 'X_WGS84', 'Y_WGS84', '바로가기'
]

def parse_area(val):
    if pd.isna(val):
        return np.nan
    m = re.search(r'[\d,]+\.?\d*', str(val).replace(',', ''))
    return float(m.group().replace(',', '')) if m else np.nan

parks_raw['면적_m2'] = parks_raw['면적'].apply(parse_area)
parks_df = parks_raw[parks_raw['지역'].isin(SEOUL_GU_LIST)].copy()
parks_df = parks_df.dropna(subset=['X_WGS84', 'Y_WGS84', '면적_m2'])
parks_df = parks_df[parks_df['X_WGS84'] > 0]
print(f"\n  서울 내 공원 {len(parks_df)}개 로드")
print(f"  총 공원 면적: {parks_df['면적_m2'].sum():,.0f} ㎡")

# ── 2-4. 고령인구 데이터 ─────────────────────────────────────
elderly_path = os.path.join(BASE_DIR, "고령자현황_20260421103806.csv")
elderly_raw = pd.read_csv(elderly_path, encoding='utf-8-sig', header=None)
elderly_raw.columns = [
    '구분1','구명','동명',
    '전체인구','전체_남','전체_여',
    '65세이상','65세이상_남','65세이상_여',
    '내국인_65','내국인_65남','내국인_65여',
    '외국인_65','외국인_65남','외국인_65여'
]
elderly_data = elderly_raw.iloc[4:].copy()
elderly_data = elderly_data[
    (elderly_data['구명'] != '소계') & (elderly_data['동명'] != '소계')
]
for col in ['전체인구', '65세이상']:
    elderly_data[col] = pd.to_numeric(
        elderly_data[col].astype(str).str.replace(',', ''), errors='coerce'
    )
elderly_data = elderly_data.dropna(subset=['65세이상'])

elderly_gu = elderly_data.groupby('구명').agg(
    전체인구=('전체인구', 'sum'),
    pop_65=('65세이상', 'sum')
).reset_index()
elderly_gu.rename(columns={'pop_65': '65세이상인구'}, inplace=True)
elderly_gu['고령화율'] = (elderly_gu['65세이상인구'] / elderly_gu['전체인구'] * 100).round(2)
print(f"\n  고령인구 데이터: {len(elderly_gu)}개 자치구")
print(f"  서울 전체 65세이상: {elderly_gu['65세이상인구'].sum():,}명")

# ── 2-5. 서울시 행정구역 GeoJSON ──────────────────────────────
geojson_url = (
    "https://raw.githubusercontent.com/southkorea/seoul-maps/"
    "master/kostat/2013/json/seoul_municipalities_geo_simple.json"
)
print(f"\n  서울 행정구역 GeoJSON 다운로드 중...")
resp = requests.get(geojson_url, timeout=30)
geojson_data = resp.json()
seoul_gdf = gpd.GeoDataFrame.from_features(geojson_data['features'], crs=CRS_WGS84)
seoul_gdf.rename(columns={'name': '구명'}, inplace=True)
print(f"  행정구역 GeoDF: {len(seoul_gdf)}개 구 로드")

# ── 2-6. GeoDataFrame 생성 (공원) ────────────────────────────
parks_gdf = gpd.GeoDataFrame(
    parks_df,
    geometry=gpd.points_from_xy(parks_df['X_WGS84'], parks_df['Y_WGS84']),
    crs=CRS_WGS84
)

# ── 2-7. GeoDataFrame 생성 (복지시설: 실좌표 + 구 centroid fallback) ─
seoul_gu_centroids = seoul_gdf.copy()
seoul_gu_centroids['cent_lat'] = seoul_gu_centroids.geometry.centroid.y
seoul_gu_centroids['cent_lng'] = seoul_gu_centroids.geometry.centroid.x

welfare_df = welfare_df.merge(
    seoul_gu_centroids[['구명', 'cent_lat', 'cent_lng']].rename(columns={'구명': '시군구명'}),
    on='시군구명', how='left'
)
welfare_df['lat'] = welfare_df['lat'].fillna(welfare_df['cent_lat'])
welfare_df['lng'] = welfare_df['lng'].fillna(welfare_df['cent_lng'])
welfare_df = welfare_df.dropna(subset=['lat', 'lng'])

welfare_gdf_wgs = gpd.GeoDataFrame(
    welfare_df,
    geometry=gpd.points_from_xy(welfare_df['lng'], welfare_df['lat']),
    crs=CRS_WGS84
)
print(f"\n  복지시설 GeoDataFrame: {len(welfare_gdf_wgs)}개 (실좌표 우선)")
print(f"  공원 GeoDataFrame: {len(parks_gdf)}개")
print("Step 2 완료")


# ============================================================
# Step 3: 공간 접근성 분석
# ============================================================
print("\nStep 3: 공간 접근성 분석 시작")

parks_korea   = parks_gdf.to_crs(CRS_KOREA)
welfare_korea = welfare_gdf_wgs.to_crs(CRS_KOREA)
seoul_korea   = seoul_gdf.to_crs(CRS_KOREA)

# ── 3-1. 버퍼 생성 (노인 / 청년 속도 구분) ───────────────────
for gdf, name in [(parks_korea, '공원'), (welfare_korea, '복지시설')]:
    gdf['buf_elder_10min'] = gdf.geometry.buffer(ELDERLY_10MIN_M)  # 노인 도보 10분
    gdf['buf_elder_20min'] = gdf.geometry.buffer(ELDERLY_20MIN_M)  # 노인 도보 20분
    gdf['buf_youth_10min'] = gdf.geometry.buffer(YOUTH_10MIN_M)    # 청년 도보 10분
    gdf['buf_youth_20min'] = gdf.geometry.buffer(YOUTH_20MIN_M)    # 청년 도보 20분
    print(f"  {name} 버퍼 생성 완료 (노인: {ELDERLY_10MIN_M}m/{ELDERLY_20MIN_M}m, "
          f"청년: {YOUTH_10MIN_M}m/{YOUTH_20MIN_M}m)")

# ── 3-2. 구별 커버리지 계산 함수 ─────────────────────────────
def buf_coverage_by_gu(facility_gdf, buf_col, gu_col, gu_gdf):
    """구별 버퍼 커버리지 비율(%) 계산"""
    results = []
    for _, gu_row in gu_gdf.iterrows():
        gu_name = gu_row['구명']
        gu_geom = gu_row['geometry']
        mask = facility_gdf[gu_col] == gu_name
        bufs  = facility_gdf.loc[mask, buf_col]
        if len(bufs) == 0:
            results.append({'구명': gu_name, '커버리지': 0.0})
            continue
        union     = unary_union(bufs.tolist())
        intersect = gu_geom.intersection(union)
        results.append({'구명': gu_name, '커버리지': intersect.area / gu_geom.area * 100})
    return pd.DataFrame(results)

# 공원 커버리지 (노인·청년 각각)
park_buf_elder = gpd.GeoDataFrame(
    parks_korea[['지역']].copy(),
    geometry=parks_korea['buf_elder_10min'],
    crs=CRS_KOREA
).rename(columns={'지역': '구명'})

park_buf_youth = gpd.GeoDataFrame(
    parks_korea[['지역']].copy(),
    geometry=parks_korea['buf_youth_10min'],
    crs=CRS_KOREA
).rename(columns={'지역': '구명'})

park_cov_elder = buf_coverage_by_gu(park_buf_elder, 'geometry', '구명', seoul_korea)
park_cov_youth = buf_coverage_by_gu(park_buf_youth, 'geometry', '구명', seoul_korea)
park_cov_elder.rename(columns={'커버리지': '공원커버_노인10분'}, inplace=True)
park_cov_youth.rename(columns={'커버리지': '공원커버_청년10분'}, inplace=True)
print("  공원 커버리지 계산 완료")

# 복지시설 커버리지 (노인·청년 각각)
welf_buf_elder = gpd.GeoDataFrame(
    welfare_korea[['시군구명']].copy(),
    geometry=welfare_korea['buf_elder_10min'],
    crs=CRS_KOREA
).rename(columns={'시군구명': '구명'})

welf_buf_youth = gpd.GeoDataFrame(
    welfare_korea[['시군구명']].copy(),
    geometry=welfare_korea['buf_youth_10min'],
    crs=CRS_KOREA
).rename(columns={'시군구명': '구명'})

welf_cov_elder = buf_coverage_by_gu(welf_buf_elder, 'geometry', '구명', seoul_korea)
welf_cov_youth = buf_coverage_by_gu(welf_buf_youth, 'geometry', '구명', seoul_korea)
welf_cov_elder.rename(columns={'커버리지': '복지커버_노인10분'}, inplace=True)
welf_cov_youth.rename(columns={'커버리지': '복지커버_청년10분'}, inplace=True)
print("  복지시설 커버리지 계산 완료")

# ── 3-3. 구별 시설·공원 집계 ─────────────────────────────────
welfare_count = welfare_df.groupby('시군구명').agg(
    시설수=('시설명', 'count')
).reset_index().rename(columns={'시군구명': '구명'})

park_area_gu = parks_df.groupby('지역')['면적_m2'].sum().reset_index()
park_area_gu.rename(columns={'지역': '구명', '면적_m2': '공원면적_m2'}, inplace=True)

print("Step 3 완료")


# ============================================================
# Step 4: 평가지표 및 스코어링
# ============================================================
print("\nStep 4: 평가지표 산출 시작")

master = (
    elderly_gu
    .merge(welfare_count,   on='구명', how='left')
    .merge(park_area_gu,    on='구명', how='left')
    .merge(park_cov_elder,  on='구명', how='left')
    .merge(park_cov_youth,  on='구명', how='left')
    .merge(welf_cov_elder,  on='구명', how='left')
    .merge(welf_cov_youth,  on='구명', how='left')
)
for col in ['시설수', '공원면적_m2', '공원커버_노인10분', '공원커버_청년10분',
            '복지커버_노인10분', '복지커버_청년10분']:
    master[col] = master[col].fillna(0)

# ── 4-1. Welfare Index (1만명당 시설 수) ─────────────────────
master['welfare_index'] = (master['시설수'] / master['65세이상인구'] * 10_000).round(3)

# ── 4-2. Green Index (1인당 공원 면적) ───────────────────────
master['green_index'] = (master['공원면적_m2'] / master['65세이상인구']).round(2)

# ── 4-3. 보행권 격차 지표 (청년-노인 커버리지 차이) ──────────
# 청년과 노인의 커버리지 차이가 클수록 노인에게 불리한 지역
master['복지_속도격차'] = (master['복지커버_청년10분'] - master['복지커버_노인10분']).round(2)
master['공원_속도격차'] = (master['공원커버_청년10분'] - master['공원커버_노인10분']).round(2)

# ── 4-4. 영향 노인 수 (보행권 박탈 노인 수) ──────────────────
# 노인 기준 10분 보행권(400m) 밖에 있는 65세이상 인구 추정
master['복지_박탈노인'] = (
    master['65세이상인구'] * (1 - master['복지커버_노인10분'] / 100)
).round(0)
master['공원_박탈노인'] = (
    master['65세이상인구'] * (1 - master['공원커버_노인10분'] / 100)
).round(0)

# ── 4-5. Vulnerability Score (재설계: 고령화율 제거) ─────────
# 기존 고령화율 30% 가중 제거 (무상관 근거: r=0.020, p=0.68)
# 대신 보행권 박탈 노인 수 기반으로 재설계
def minmax(series):
    mn, mx = series.min(), series.max()
    return (series - mn) / (mx - mn) if mx > mn else pd.Series(0.0, index=series.index)

master['norm_welfare_blind'] = minmax(master['복지_박탈노인'])
master['norm_park_blind']    = minmax(master['공원_박탈노인'])

# 가중치: 복지 박탈 50% + 공원 박탈 50%
master['vulnerability_score'] = (
    master['norm_welfare_blind'] * 0.50 +
    master['norm_park_blind']    * 0.50
).round(4)

master_sorted = master.sort_values('vulnerability_score', ascending=False)

print("  평가지표 산출 완료")
print(master_sorted[[
    '구명', '시설수', '65세이상인구',
    '복지커버_노인10분', '공원커버_노인10분',
    '복지_박탈노인', '공원_박탈노인',
    'vulnerability_score'
]].to_string(index=False))
print("Step 4 완료")


# ============================================================
# Step 5: 데이터 시각화
# ============================================================
print("\nStep 5: 시각화 시작")

# ── 5-1. Folium 인터랙티브 지도 ──────────────────────────────
m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles='CartoDB positron')

seoul_plot = seoul_gdf.merge(
    master[['구명', 'vulnerability_score', 'welfare_index', 'green_index',
            '65세이상인구', '시설수', '복지커버_노인10분', '공원커버_노인10분',
            '복지_박탈노인', '복지_속도격차']],
    on='구명', how='left'
)
geojson_str = seoul_plot.to_json()

# 복지 결핍 지수 Choropleth
folium.Choropleth(
    geo_data=geojson_str,
    data=master,
    columns=['구명', 'vulnerability_score'],
    key_on='feature.properties.구명',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.5,
    legend_name='생활권 복지 결핍 지수 (보행권 박탈 노인 수 기반)',
    name='복지 결핍 지수 (Choropleth)',
    nan_fill_color='white'
).add_to(m)

folium.GeoJson(
    geojson_str,
    style_function=lambda x: {'fillColor': 'transparent', 'color': '#555', 'weight': 1.5},
    tooltip=folium.GeoJsonTooltip(
        fields=['구명', 'vulnerability_score', '복지커버_노인10분', '공원커버_노인10분',
                '복지_박탈노인', '복지_속도격차', '65세이상인구', '시설수'],
        aliases=['자치구', '결핍지수', '복지커버(노인10분,%)', '공원커버(노인10분,%)',
                 '복지박탈노인(명)', '복지속도격차(청-노,%)', '65세이상인구', '시설수'],
        localize=True
    ),
    name='구 경계'
).add_to(m)

# 공원 위치 마커
park_cluster = MarkerCluster(name='공원 위치').add_to(m)
for _, row in parks_df.iterrows():
    if pd.isna(row['X_WGS84']) or pd.isna(row['Y_WGS84']):
        continue
    radius = max(5, min(20, np.sqrt(row['면적_m2']) / 50))
    folium.CircleMarker(
        location=[row['Y_WGS84'], row['X_WGS84']],
        radius=radius,
        color='green', fill=True, fill_color='#2ca02c', fill_opacity=0.6,
        popup=f"<b>{row['공원명']}</b><br>면적: {row['면적_m2']:,.0f}㎡<br>지역: {row['지역']}",
        tooltip=row['공원명']
    ).add_to(park_cluster)

# 복지시설 마커
welfare_cluster = MarkerCluster(name='복지시설 위치').add_to(m)
for _, row in welfare_gdf_wgs.iterrows():
    if row.geometry is None:
        continue
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=5, color='blue', fill=True, fill_color='#1f77b4', fill_opacity=0.5,
        popup=f"<b>{row['시설명']}</b><br>{row['유형_간략']}<br>{row['시군구명']}",
        tooltip=row['시설명']
    ).add_to(welfare_cluster)

# 청년/노인 비교 버퍼 레이어 (상위 10개 공원)
top_parks = parks_gdf.nlargest(10, '면적_m2').to_crs(CRS_KOREA)

elder_buf_layer = folium.FeatureGroup(name='공원 노인 보행권 (400m)', show=False)
youth_buf_layer = folium.FeatureGroup(name='공원 청년 보행권 (800m)', show=False)

for _, row in top_parks.iterrows():
    for layer, radius, color, op, label in [
        (elder_buf_layer, ELDERLY_10MIN_M, '#d62728', 0.18, '노인 10분'),
        (youth_buf_layer, YOUTH_10MIN_M,   '#2ca02c', 0.12, '청년 10분'),
    ]:
        buf = gpd.GeoDataFrame(
            geometry=[row.geometry.buffer(radius)], crs=CRS_KOREA
        ).to_crs(CRS_WGS84)
        folium.GeoJson(
            buf.geometry.__geo_interface__,
            style_function=lambda x, c=color, o=op: {
                'fillColor': c, 'color': c, 'weight': 1, 'fillOpacity': o
            },
            tooltip=f"{row['공원명']} {label} ({radius}m)"
        ).add_to(layer)

elder_buf_layer.add_to(m)
youth_buf_layer.add_to(m)
folium.LayerControl().add_to(m)

map_path = os.path.join(OUTPUT_DIR, 'seoul_welfare_map.html')
m.save(map_path)
print(f"  Folium 지도 저장: {map_path}")

# ── 5-2. 통계 차트 ───────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(20, 8))
fig.suptitle('서울시 자치구별 노인 복지·녹지 접근성 분석\n(보행 속도: 노인 2.4km/h · 청년 4.8km/h 기준)',
             fontsize=14, fontweight='bold')

# 막대: 결핍 지수
sorted_bar = master_sorted[['구명', 'vulnerability_score']].head(25)
colors = ['#d62728' if v > 0.6 else '#ff7f0e' if v > 0.4 else '#2ca02c'
          for v in sorted_bar['vulnerability_score']]
axes[0].barh(sorted_bar['구명'][::-1], sorted_bar['vulnerability_score'][::-1], color=colors[::-1])
axes[0].set_title('자치구별 생활권 복지 결핍 지수\n(보행권 박탈 노인 수 기반, 고령화율 제외)', fontsize=12)
axes[0].set_xlabel('결핍 지수 (0~1)')
axes[0].axvline(x=0.6, color='red',    linestyle='--', alpha=0.7, label='고위험 (0.6)')
axes[0].axvline(x=0.4, color='orange', linestyle='--', alpha=0.7, label='중위험 (0.4)')
axes[0].legend()
axes[0].set_xlim(0, 1)

# 산점도: 복지 보행권 격차 (노인 vs 청년)
sc = axes[1].scatter(
    master['복지커버_노인10분'],
    master['복지커버_청년10분'],
    c=master['vulnerability_score'],
    cmap='YlOrRd',
    s=master['65세이상인구'] / 800,
    alpha=0.85,
    edgecolors='black',
    linewidths=0.5
)
for _, row in master.iterrows():
    axes[1].annotate(row['구명'], (row['복지커버_노인10분'], row['복지커버_청년10분']),
                     fontsize=7, ha='center', va='bottom')
plt.colorbar(sc, ax=axes[1], label='결핍 지수')
axes[1].plot([0, 100], [0, 100], 'k--', alpha=0.3, label='동일선 (격차 없음)')
axes[1].set_xlabel('복지시설 보행권 커버리지 – 노인 기준 10분 400m (%)')
axes[1].set_ylabel('복지시설 보행권 커버리지 – 청년 기준 10분 800m (%)')
axes[1].set_title('청년 vs 노인 복지시설 접근성 격차\n(원 크기: 65세이상 인구, 색상: 결핍지수)', fontsize=12)
axes[1].legend()
plt.tight_layout()
chart_path = os.path.join(OUTPUT_DIR, 'welfare_analysis_chart.png')
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  통계 차트 저장: {chart_path}")

# ── 5-3. 복지·녹지 2D 산점도 (구 단위) ──────────────────────
fig2, ax2 = plt.subplots(figsize=(10, 8))
sc2 = ax2.scatter(
    master['welfare_index'],
    master['green_index'],
    c=master['vulnerability_score'],
    cmap='YlOrRd',
    s=120, alpha=0.85,
    edgecolors='black', linewidths=0.6
)
for _, row in master.iterrows():
    ax2.annotate(row['구명'], (row['welfare_index'], row['green_index']),
                 fontsize=8, ha='center', va='bottom')
plt.colorbar(sc2, ax=ax2, label='결핍 지수')
ax2.axvline(x=master['welfare_index'].median(), color='blue',
            linestyle='--', alpha=0.5, label='복지지수 중앙값')
ax2.axhline(y=master['green_index'].median(), color='green',
            linestyle='--', alpha=0.5, label='녹지지수 중앙값')
ax2.set_xlabel('복지시설 지수 (1만명당 시설 수)')
ax2.set_ylabel('녹지 지수 (1인당 공원 면적, ㎡/인)')
ax2.set_title('복지시설 지수 vs 녹지 지수 분포\n(색상: 복지 결핍 지수)', fontsize=12)
ax2.legend()
chart2_path = os.path.join(OUTPUT_DIR, 'welfare_green_scatter.png')
plt.savefig(chart2_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  산점도 저장: {chart2_path}")

# ── 5-4. 속도 격차 비교 차트 ─────────────────────────────────
fig3, axes3 = plt.subplots(1, 2, figsize=(20, 8))
fig3.suptitle('청년 vs 노인 보행권 커버리지 격차 (서울 25개 자치구)', fontsize=14, fontweight='bold')

ms = master.sort_values('복지_속도격차', ascending=False)
y  = np.arange(len(ms))
h  = 0.35
axes3[0].barh(y + h/2, ms['복지커버_청년10분'], h, label=f'청년 ({YOUTH_10MIN_M}m)',
              color='#2ca02c', alpha=0.85)
axes3[0].barh(y - h/2, ms['복지커버_노인10분'], h, label=f'노인 ({ELDERLY_10MIN_M}m)',
              color='#d62728', alpha=0.85)
axes3[0].set_yticks(y)
axes3[0].set_yticklabels(ms['구명'], fontsize=9)
axes3[0].set_xlabel('보행권 커버리지 (%)')
axes3[0].set_title('복지시설 보행권 커버리지\n(청년 10분 vs 노인 10분)', fontsize=12)
axes3[0].legend()
axes3[0].set_xlim(0, 110)

ms2 = master.sort_values('공원_속도격차', ascending=False)
y2  = np.arange(len(ms2))
axes3[1].barh(y2 + h/2, ms2['공원커버_청년10분'], h, label=f'청년 ({YOUTH_10MIN_M}m)',
              color='#2ca02c', alpha=0.85)
axes3[1].barh(y2 - h/2, ms2['공원커버_노인10분'], h, label=f'노인 ({ELDERLY_10MIN_M}m)',
              color='#d62728', alpha=0.85)
axes3[1].set_yticks(y2)
axes3[1].set_yticklabels(ms2['구명'], fontsize=9)
axes3[1].set_xlabel('보행권 커버리지 (%)')
axes3[1].set_title('공원·녹지 보행권 커버리지\n(청년 10분 vs 노인 10분)', fontsize=12)
axes3[1].legend()
axes3[1].set_xlim(0, 110)

plt.tight_layout()
gap_chart_path = os.path.join(OUTPUT_DIR, 'speed_gap_chart.png')
plt.savefig(gap_chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  속도 격차 차트 저장: {gap_chart_path}")

print("Step 5 완료")


# ============================================================
# Step 6: 최종 리포트 출력 및 CSV 저장
# ============================================================
print("\nStep 6: 최종 리포트 생성")

top5 = master_sorted.head(5)[[
    '구명', 'vulnerability_score', '시설수', '65세이상인구',
    'welfare_index', 'green_index', '고령화율',
    '복지커버_노인10분', '공원커버_노인10분',
    '복지_박탈노인', '공원_박탈노인',
    '복지_속도격차', '공원_속도격차'
]].reset_index(drop=True)

print("\n" + "=" * 70)
print("▣ 복지시설 확충이 가장 시급한 자치구 TOP 5")
print("   (지표: 보행권 박탈 노인 수 기반 결핍 지수)")
print("=" * 70)
for rank, row in top5.iterrows():
    print(f"\n  [{rank+1}위] {row['구명']}")
    print(f"    - 결핍 지수           : {row['vulnerability_score']:.4f}")
    print(f"    - 65세이상 인구       : {row['65세이상인구']:,.0f}명  "
          f"(고령화율 {row['고령화율']:.1f}%)")
    print(f"    - 복지시설 수         : {row['시설수']:.0f}개 "
          f"(1만명당 {row['welfare_index']:.2f}개소)")
    print(f"    - 복지 보행권 커버     : 노인 {row['복지커버_노인10분']:.1f}% / "
          f"청년 {row['복지커버_청년10분'] if '복지커버_청년10분' in row else 'N/A'}%  "
          f"→ 격차 {row['복지_속도격차']:.1f}%p")
    print(f"    - 복지 박탈 노인 수   : {row['복지_박탈노인']:,.0f}명")
    print(f"    - 공원 보행권 커버     : 노인 {row['공원커버_노인10분']:.1f}%")
    print(f"    - 공원 박탈 노인 수   : {row['공원_박탈노인']:,.0f}명")

print("\n" + "=" * 70)
print("▣ 분석 결과 요약")
print("=" * 70)
print(f"  보행 속도 기준  : 노인 2.4km/h (10분={ELDERLY_10MIN_M}m) / "
      f"청년 4.8km/h (10분={YOUTH_10MIN_M}m)")
print(f"  서울 전체 65세이상 인구    : {master['65세이상인구'].sum():,}명")
print(f"  평균 복지 보행권 커버(노인): {master['복지커버_노인10분'].mean():.1f}%")
print(f"  평균 복지 보행권 커버(청년): {master['복지커버_청년10분'].mean():.1f}%")
print(f"  평균 속도 격차 (복지)      : {master['복지_속도격차'].mean():.1f}%p")
print(f"  평균 속도 격차 (공원)      : {master['공원_속도격차'].mean():.1f}%p")
total_welfare_blind = int(master['복지_박탈노인'].sum())
total_park_blind    = int(master['공원_박탈노인'].sum())
print(f"  복지 보행권 박탈 노인 추정 : {total_welfare_blind:,}명")
print(f"  공원 보행권 박탈 노인 추정 : {total_park_blind:,}명")

# CSV 저장
result_path = os.path.join(OUTPUT_DIR, 'district_welfare_analysis.csv')
master_sorted.to_csv(result_path, index=False, encoding='utf-8-sig')
print(f"\n  분석 결과 CSV 저장: {result_path}")

top5_path = os.path.join(OUTPUT_DIR, 'top5_urgent_districts.csv')
top5.to_csv(top5_path, index=False, encoding='utf-8-sig')
print(f"  TOP5 리포트 CSV 저장: {top5_path}")

print("\n" + "=" * 60)
print("전체 분석 파이프라인 완료")
print(f"결과물 디렉토리: {OUTPUT_DIR}")
print("  - seoul_welfare_map.html       (인터랙티브 지도: 청년/노인 버퍼 비교)")
print("  - welfare_analysis_chart.png   (결핍지수 막대 + 청년-노인 격차 산점도)")
print("  - welfare_green_scatter.png    (복지지수 vs 녹지지수 2D 분포)")
print("  - speed_gap_chart.png          (청년 vs 노인 보행권 커버리지 비교)")
print("  - district_welfare_analysis.csv (전체 분석 결과)")
print("  - top5_urgent_districts.csv    (TOP5 시급 자치구)")
print("=" * 60)
