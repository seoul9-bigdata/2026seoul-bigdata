"""
서울시 노인복지 및 녹지 접근성 – 행정동 단위 시각화
======================================================
출력:
  output/park_dong_map.html       ← 행정동 녹지 접근성 지도
  output/welfare_dong_map.html    ← 행정동 복지시설 접근성 지도
  output/dong_vulnerability.png   ← 행정동 TOP10 결핍 지수 바차트
  output/dong_top5_report.csv     ← 행정동 TOP5 확충 시급 리포트

개선사항:
  - 시설 유형 라벨 실제 데이터 기준으로 수정 (노인교실·노인복지관·노인복지관(소규모))
  - 청년/노인 보행 속도 구분 (노인 400m vs 청년 800m)
  - Vulnerability Score 행정동 단위 산출 (보행권 박탈 노인 수 기반)
  - TOP5 행정동 리포트 및 시각화 추가
"""

import warnings; warnings.filterwarnings('ignore')
import io, os, re, json, time
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
import folium
import branca.colormap as bc
import matplotlib.pyplot as plt
import koreanize_matplotlib
import requests
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
CACHE_FILE = os.path.join(OUTPUT_DIR, "geocode_cache.json")

CRS_WGS84 = "EPSG:4326"
CRS_KOREA = "EPSG:5179"

# ── 보행 속도 기준 ────────────────────────────────────────────
ELDERLY_10MIN_M = 400   # 노인 도보 10분 (2.4 km/h)
ELDERLY_20MIN_M = 800
YOUTH_10MIN_M   = 800   # 청년 도보 10분 (4.8 km/h)
YOUTH_20MIN_M   = 1_600

# ── 행정동 이름 정규화 (CSV ↔ GeoJSON 불일치 교정) ────────────
DONG_NAME_MAP = {
    '종로1.2.3.4가동':  '종로1·2·3·4가동',
    '종로5.6가동':      '종로5·6가동',
    '금호2.3가동':      '금호2·3가동',
    '상계3.4동':        '상계3·4동',
    '상계6.7동':        '상계6·7동',
    '중계2.3동':        '중계2·3동',
    '면목3.8동':        '면목3·8동',
    '상일1동': '상일제1동',
    '상일2동': '상일제2동',
    '신설동':  '용신동',
    '용두동':  '용신동',
}

def norm_dong(name):
    return DONG_NAME_MAP.get(name, name)


# ============================================================
# 1. 데이터 로드
# ============================================================
print("=" * 60)
print("1. 데이터 로드")
print("=" * 60)

# ── 행정동 GeoJSON ────────────────────────────────────────────
print("  행정동 GeoJSON 다운로드 중...")
resp = requests.get(
    "https://raw.githubusercontent.com/vuski/admdongkor/master/"
    "ver20230701/HangJeongDong_ver20230701.geojson",
    timeout=60
)
dong_gdf = gpd.GeoDataFrame.from_features(resp.json()['features'], crs=CRS_WGS84)
dong_gdf = dong_gdf[dong_gdf['sido'] == '11'].copy()
dong_gdf['구명'] = dong_gdf['sggnm']
dong_gdf['동명'] = dong_gdf['adm_nm'].str.split(' ').str[-1]
dong_gdf['동_key'] = dong_gdf['구명'] + '_' + dong_gdf['동명']
print(f"  서울 행정동 {len(dong_gdf)}개 로드")

# ── 고령인구 (행정동 단위) ────────────────────────────────────
elderly_raw = pd.read_csv(
    os.path.join(BASE_DIR, "고령자현황_20260421103806.csv"),
    encoding='utf-8-sig', header=None
)
elderly_raw.columns = [
    '구분1','구명','동명',
    '전체인구','전체_남','전체_여',
    '65세이상','65세이상_남','65세이상_여',
    '내국인_65','내국인_65남','내국인_65여',
    '외국인_65','외국인_65남','외국인_65여'
]
elderly = elderly_raw.iloc[4:].copy()
elderly = elderly[(elderly['구명'] != '소계') & (elderly['동명'] != '소계')]
for c in ['전체인구', '65세이상']:
    elderly[c] = pd.to_numeric(
        elderly[c].astype(str).str.replace(',', ''), errors='coerce'
    )
elderly = elderly.dropna(subset=['65세이상'])
elderly['동명_norm'] = elderly['동명'].apply(norm_dong)
elderly['동_key']    = elderly['구명'] + '_' + elderly['동명_norm']
elderly_dong = elderly[['동_key', '구명', '동명', '전체인구', '65세이상']].copy()
elderly_dong.rename(columns={'65세이상': '65세이상인구'}, inplace=True)
elderly_dong = elderly_dong.groupby('동_key').agg(
    구명=('구명', 'first'),
    동명=('동명', 'first'),
    전체인구=('전체인구', 'sum'),
    pop65=('65세이상인구', 'sum')
).reset_index()
elderly_dong.rename(columns={'pop65': '65세이상인구'}, inplace=True)
elderly_dong['고령화율'] = (elderly_dong['65세이상인구'] / elderly_dong['전체인구'] * 100).round(2)
print(f"  고령인구 행정동 {len(elderly_dong)}개 로드")

# ── 복지시설 ─────────────────────────────────────────────────
with open(os.path.join(BASE_DIR,
          "서울시 사회복지시설(노인여가복지시설) 목록.csv"), 'rb') as f:
    welfare_df = pd.read_csv(io.StringIO(f.read().decode('euc-kr')))
welfare_df.columns = [
    '시설명','시설코드','시설유형','시설종류상세',
    '자치구구분','시군구코드','시군구명','시설주소',
    '전화번호','우편번호'
]
# 자치구구분 컬럼은 전부 '자치구' 단일값 — 필터 생략
welfare_df['시설주소'] = welfare_df['시설주소'].fillna('').str.strip()
welfare_df = welfare_df[welfare_df['시설주소'] != '']

# 실제 데이터 유형: 노인교실 / 노인복지관 / 노인복지관(소규모)
def short_type(t):
    if '소규모' in t:   return '노인복지관(소규모)'
    if '노인교실' in t: return '노인교실'
    return '노인복지관'

welfare_df['유형_간략'] = welfare_df['시설유형'].apply(short_type)
print(f"  복지시설 {len(welfare_df)}개 로드")
print(f"  유형 분포: {welfare_df['유형_간략'].value_counts().to_dict()}")

# ── 공원 ──────────────────────────────────────────────────────
parks_raw = pd.read_excel(
    os.path.join(BASE_DIR, "서울시 주요 공원현황(2026 상반기).xlsx")
)
parks_raw.columns = [
    '연번','관리부서','전화번호','공원명','공원개요',
    '면적','개원일','주요시설','주요식물','안내도',
    '오시는길','이용시참고사항','이미지','지역','공원주소',
    'X_GRS80','Y_GRS80','X_WGS84','Y_WGS84','바로가기'
]
SEOUL_GU = dong_gdf['구명'].unique().tolist()

def parse_area(v):
    m = re.search(r'[\d,]+\.?\d*', str(v).replace(',', ''))
    return float(m.group().replace(',', '')) if m else np.nan

parks_raw['면적_m2'] = parks_raw['면적'].apply(parse_area)
parks_df = parks_raw[parks_raw['지역'].isin(SEOUL_GU)].dropna(
    subset=['X_WGS84', 'Y_WGS84', '면적_m2']
).copy()
parks_df = parks_df[parks_df['X_WGS84'] > 0]
parks_gdf = gpd.GeoDataFrame(
    parks_df,
    geometry=gpd.points_from_xy(parks_df['X_WGS84'], parks_df['Y_WGS84']),
    crs=CRS_WGS84
)
print(f"  공원 {len(parks_gdf)}개 로드")


# ============================================================
# 2. 복지시설 지오코딩 (Nominatim + 캐시)
# ============================================================
print("\n" + "=" * 60)
print("2. 복지시설 지오코딩 (Nominatim + 캐시)")
print("=" * 60)

cache = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    print(f"  캐시 로드: {len(cache)}건 "
          f"(성공 {sum(1 for v in cache.values() if v.get('lat'))}건)")

geolocator = Nominatim(user_agent="seoul_welfare_analysis_v2")
geocode     = RateLimiter(geolocator.geocode, min_delay_seconds=1.2)

lats, lngs = [], []
miss = 0
for i, row in welfare_df.iterrows():
    addr = row['시설주소']
    if addr in cache:
        lats.append(cache[addr]['lat'])
        lngs.append(cache[addr]['lng'])
        continue

    def try_geocode(query):
        try:
            return geocode(query, language='ko', timeout=10)
        except:
            return None

    loc = try_geocode(addr)
    if loc is None:
        short = re.sub(r'\s*\(.*?\)', '', addr).strip()
        loc   = try_geocode(short)

    if loc:
        cache[addr] = {'lat': loc.latitude, 'lng': loc.longitude}
        lats.append(loc.latitude)
        lngs.append(loc.longitude)
    else:
        cache[addr] = {'lat': None, 'lng': None}
        lats.append(None)
        lngs.append(None)
        miss += 1

    done = i - welfare_df.index[0] + 1
    if done % 20 == 0 or done == len(welfare_df):
        print(f"  진행: {done}/{len(welfare_df)}  실패: {miss}")

with open(CACHE_FILE, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

welfare_df = welfare_df.copy()
welfare_df['lat'] = lats
welfare_df['lng'] = lngs
welfare_ok  = welfare_df.dropna(subset=['lat', 'lng']).copy()
welfare_gdf = gpd.GeoDataFrame(
    welfare_ok,
    geometry=gpd.points_from_xy(welfare_ok['lng'], welfare_ok['lat']),
    crs=CRS_WGS84
)
print(f"  지오코딩 완료: {len(welfare_gdf)}/{len(welfare_df)}개 성공")


# ============================================================
# 3. 공간 분석 – 행정동 단위 집계
# ============================================================
print("\n" + "=" * 60)
print("3. 행정동 단위 공간 집계")
print("=" * 60)

dong_korea    = dong_gdf.to_crs(CRS_KOREA)
parks_korea   = parks_gdf.to_crs(CRS_KOREA)
welfare_korea = welfare_gdf.to_crs(CRS_KOREA)

# ── 공원 → 행정동 spatial join ────────────────────────────────
parks_join = gpd.sjoin(
    parks_korea[['공원명', '지역', '면적_m2', 'geometry']],
    dong_korea[['동_key', '구명', '동명', 'geometry']],
    how='left', predicate='within'
).rename(columns={'index_right': 'dong_idx'})

park_dong = parks_join.groupby('동_key').agg(
    공원수=('공원명', 'count'),
    공원면적_m2=('면적_m2', 'sum')
).reset_index()
print(f"  공원-행정동 join: {len(parks_join[parks_join['동_key'].notna()])}개 매칭")

# ── 복지시설 → 행정동 spatial join ──────────────────────────
welfare_join = gpd.sjoin(
    welfare_korea[['시설명', '시설유형', '유형_간략', '시군구명', 'geometry']],
    dong_korea[['동_key', '구명', '동명', 'geometry']],
    how='left', predicate='within'
).rename(columns={'index_right': 'dong_idx'})

welfare_dong = welfare_join.groupby('동_key').agg(
    시설수=('시설명', 'count'),
    노인복지관=('유형_간략', lambda x: (x == '노인복지관').sum()),
    노인교실=('유형_간략', lambda x: (x == '노인교실').sum()),
    노인복지관소규모=('유형_간략', lambda x: (x == '노인복지관(소규모)').sum()),
).reset_index()
print(f"  복지시설-행정동 join: {len(welfare_join[welfare_join['동_key'].notna()])}개 매칭")

# ── 보행권 커버리지 (노인/청년 기준 각각) ─────────────────────
def calc_coverage(facility_gdf_k, dong_k, radius):
    """각 행정동에서 시설 버퍼가 덮는 비율(%)"""
    rows = []
    for _, d in dong_k.iterrows():
        fac = facility_gdf_k[
            facility_gdf_k.geometry.intersects(d.geometry.buffer(radius + 10))
        ]
        if fac.empty:
            rows.append({'동_key': d['동_key'], f'cov_{radius}': 0.0})
            continue
        bufs  = fac.geometry.buffer(radius)
        union = unary_union(bufs.tolist())
        inter = d.geometry.intersection(union)
        rows.append({'동_key': d['동_key'],
                     f'cov_{radius}': inter.area / d.geometry.area * 100})
    return pd.DataFrame(rows)

print("  공원 보행권 커버리지 계산 중...")
park_cov_elder = calc_coverage(parks_korea, dong_korea, ELDERLY_10MIN_M)
park_cov_youth = calc_coverage(parks_korea, dong_korea, YOUTH_10MIN_M)

print("  복지시설 보행권 커버리지 계산 중...")
welf_cov_elder = calc_coverage(welfare_korea, dong_korea, ELDERLY_10MIN_M)
welf_cov_youth = calc_coverage(welfare_korea, dong_korea, YOUTH_10MIN_M)

# ── 마스터 데이터프레임 ───────────────────────────────────────
master = (
    dong_gdf[['동_key', '구명', '동명', 'geometry']]
    .merge(elderly_dong[['동_key', '전체인구', '65세이상인구', '고령화율']], on='동_key', how='left')
    .merge(park_dong, on='동_key', how='left')
    .merge(welfare_dong, on='동_key', how='left')
    .merge(park_cov_elder.rename(columns={f'cov_{ELDERLY_10MIN_M}': 'park_cov_elder'}),
           on='동_key', how='left')
    .merge(park_cov_youth.rename(columns={f'cov_{YOUTH_10MIN_M}': 'park_cov_youth'}),
           on='동_key', how='left')
    .merge(welf_cov_elder.rename(columns={f'cov_{ELDERLY_10MIN_M}': 'welf_cov_elder'}),
           on='동_key', how='left')
    .merge(welf_cov_youth.rename(columns={f'cov_{YOUTH_10MIN_M}': 'welf_cov_youth'}),
           on='동_key', how='left')
)

fill0 = ['공원수', '공원면적_m2', '시설수', '노인복지관', '노인교실', '노인복지관소규모',
         'park_cov_elder', 'park_cov_youth', 'welf_cov_elder', 'welf_cov_youth']
for c in fill0:
    if c in master.columns:
        master[c] = master[c].fillna(0)
master['65세이상인구'] = master['65세이상인구'].fillna(0)

# 지수 계산
master['green_index']   = np.where(
    master['65세이상인구'] > 0,
    (master['공원면적_m2'] / master['65세이상인구']).round(2), 0
)
master['welfare_index'] = np.where(
    master['65세이상인구'] > 0,
    (master['시설수'] / master['65세이상인구'] * 10_000).round(3), 0
)

# 속도 격차 (청년 - 노인)
master['welf_속도격차'] = (master['welf_cov_youth'] - master['welf_cov_elder']).round(2)
master['park_속도격차'] = (master['park_cov_youth'] - master['park_cov_elder']).round(2)

# 영향 노인 수 (보행권 박탈 노인 수, 노인 기준)
master['welf_박탈노인'] = (
    master['65세이상인구'] * (1 - master['welf_cov_elder'] / 100)
).round(0)
master['park_박탈노인'] = (
    master['65세이상인구'] * (1 - master['park_cov_elder'] / 100)
).round(0)

# Vulnerability Score (고령화율 제거, 보행권 박탈 노인 수 기반)
m_valid = master[master['65세이상인구'] > 0].copy()

def minmax(s):
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.0, index=s.index)

norm_w = minmax(m_valid['welf_박탈노인'])
norm_p = minmax(m_valid['park_박탈노인'])
m_valid['vulnerability_score'] = (norm_w * 0.50 + norm_p * 0.50).round(4)

master = master.merge(m_valid[['동_key', 'vulnerability_score']], on='동_key', how='left')
master['vulnerability_score'] = master['vulnerability_score'].fillna(0)

master_gdf = gpd.GeoDataFrame(master, geometry='geometry', crs=CRS_WGS84)
print(f"  마스터 GDF 완성: {len(master_gdf)}개 행정동")


# ============================================================
# 4-A. 공원·녹지 접근성 지도 (행정동 단위)
# ============================================================
print("\n" + "=" * 60)
print("4-A. 공원·녹지 접근성 지도 생성")
print("=" * 60)

m_park = folium.Map(location=[37.5665, 126.9780], zoom_start=11,
                    tiles='CartoDB positron')

colormap_green = bc.LinearColormap(
    ['#f7fcf5', '#74c476', '#006d2c'],
    vmin=0, vmax=100,
    caption=f'공원 보행권 커버리지 – 노인 {ELDERLY_10MIN_M}m (%)'
)
colormap_green.add_to(m_park)

folium.GeoJson(
    master_gdf[['동_key', '구명', '동명', 'park_cov_elder', 'park_cov_youth',
                '공원수', '공원면적_m2', 'green_index', '65세이상인구', 'park_속도격차',
                'geometry']].to_json(),
    style_function=lambda feat: {
        'fillColor': colormap_green(feat['properties'].get('park_cov_elder') or 0),
        'color': '#555', 'weight': 0.6, 'fillOpacity': 0.75
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['구명', '동명', 'park_cov_elder', 'park_cov_youth',
                '공원수', '공원면적_m2', 'green_index', '65세이상인구', 'park_속도격차'],
        aliases=['자치구', '행정동',
                 f'공원커버(노인{ELDERLY_10MIN_M}m,%)', f'공원커버(청년{YOUTH_10MIN_M}m,%)',
                 '공원수(개)', '공원면적(㎡)', '녹지지수(㎡/인)', '65세이상인구',
                 '속도격차(청-노,%p)'],
        localize=True
    ),
    name='행정동 녹지 커버리지 (노인 기준)'
).add_to(m_park)

park_layer = folium.FeatureGroup(name='공원 위치 (버블=면적)')
for _, row in parks_df.iterrows():
    r = max(4, min(25, np.sqrt(row['면적_m2']) / 50))
    folium.CircleMarker(
        location=[row['Y_WGS84'], row['X_WGS84']],
        radius=r, color='#1a5e22', weight=1,
        fill=True, fill_color='#2ca02c', fill_opacity=0.75,
        tooltip=f"<b>{row['공원명']}</b><br>면적: {row['면적_m2']:,.0f}㎡",
        popup=f"<b>{row['공원명']}</b><br>면적: {row['면적_m2']:,.0f}㎡<br>지역: {row['지역']}"
    ).add_to(park_layer)
park_layer.add_to(m_park)

top10_parks = parks_gdf.nlargest(10, '면적_m2').to_crs(CRS_KOREA)
elder_buf_layer = folium.FeatureGroup(name=f'공원 노인 보행권 ({ELDERLY_10MIN_M}m)', show=False)
youth_buf_layer = folium.FeatureGroup(name=f'공원 청년 보행권 ({YOUTH_10MIN_M}m)', show=False)

for _, row in top10_parks.iterrows():
    for lyr, rad, col, op in [
        (elder_buf_layer, ELDERLY_10MIN_M, '#d62728', 0.20),
        (youth_buf_layer, YOUTH_10MIN_M,   '#2ca02c', 0.12),
    ]:
        buf = gpd.GeoDataFrame(
            geometry=[row.geometry.buffer(rad)], crs=CRS_KOREA
        ).to_crs(CRS_WGS84)
        folium.GeoJson(
            buf.geometry.__geo_interface__,
            style_function=lambda x, c=col, o=op: {
                'fillColor': c, 'color': c, 'weight': 1, 'fillOpacity': o
            },
            tooltip=f"{row['공원명']} {'노인' if rad==ELDERLY_10MIN_M else '청년'} 10분"
        ).add_to(lyr)

elder_buf_layer.add_to(m_park)
youth_buf_layer.add_to(m_park)
folium.LayerControl(collapsed=False).add_to(m_park)

park_map_path = os.path.join(OUTPUT_DIR, 'park_dong_map.html')
m_park.save(park_map_path)
print(f"  공원 지도 저장: {park_map_path}")


# ============================================================
# 4-B. 복지시설 접근성 지도 (행정동 단위)
# ============================================================
print("\n" + "=" * 60)
print("4-B. 복지시설 접근성 지도 생성")
print("=" * 60)

m_welf = folium.Map(location=[37.5665, 126.9780], zoom_start=11,
                    tiles='CartoDB positron')

# Vulnerability Score 기반 Choropleth
vuln_max = master_gdf['vulnerability_score'].quantile(0.95)
colormap_red = bc.LinearColormap(
    ['#fff5f0', '#fc9272', '#a50f15'],
    vmin=0, vmax=max(vuln_max, 0.01),
    caption='복지 결핍 지수 (보행권 박탈 노인 수 기반)'
)
colormap_red.add_to(m_welf)
master_gdf['vuln_disp'] = master_gdf['vulnerability_score'].clip(upper=vuln_max)

folium.GeoJson(
    master_gdf[['동_key', '구명', '동명', 'vulnerability_score', 'vuln_disp',
                'welfare_index', '시설수', '노인복지관', '노인교실', '노인복지관소규모',
                'welf_cov_elder', 'welf_cov_youth', 'welf_박탈노인', 'welf_속도격차',
                '65세이상인구', '고령화율', 'geometry']].to_json(),
    style_function=lambda feat: {
        'fillColor': colormap_red(feat['properties'].get('vuln_disp') or 0),
        'color': '#555', 'weight': 0.6, 'fillOpacity': 0.75
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['구명', '동명', 'vulnerability_score', '시설수',
                '노인복지관', '노인교실', '노인복지관소규모',
                'welf_cov_elder', 'welf_cov_youth', 'welf_박탈노인', 'welf_속도격차',
                '65세이상인구', '고령화율'],
        aliases=['자치구', '행정동', '결핍지수', '총시설수',
                 '노인복지관', '노인교실', '노인복지관(소규모)',
                 f'복지커버(노인{ELDERLY_10MIN_M}m,%)', f'복지커버(청년{YOUTH_10MIN_M}m,%)',
                 '박탈노인(명)', '속도격차(청-노,%p)',
                 '65세이상인구', '고령화율(%)'],
        localize=True
    ),
    name='행정동 복지 결핍 지수 (Choropleth)'
).add_to(m_welf)

# 시설 유형별 마커
TYPE_STYLE = {
    '노인복지관':      {'color': '#1f77b4', 'radius': 9},
    '노인교실':        {'color': '#ff7f0e', 'radius': 6},
    '노인복지관(소규모)': {'color': '#aec7e8', 'radius': 5},
}
for wtype, style in TYPE_STYLE.items():
    layer = folium.FeatureGroup(name=f'시설: {wtype}')
    sub = welfare_gdf[welfare_gdf['유형_간략'] == wtype]
    for _, row in sub.iterrows():
        if row.geometry is None:
            continue
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=style['radius'],
            color=style['color'], weight=1.5,
            fill=True, fill_color=style['color'], fill_opacity=0.85,
            tooltip=f"<b>{row['시설명']}</b><br>{wtype}<br>{row['시군구명']}",
            popup=(f"<b>{row['시설명']}</b><br>"
                   f"유형: {wtype}<br>구: {row['시군구명']}<br>주소: {row['시설주소']}")
        ).add_to(layer)
    layer.add_to(m_welf)

# 노인복지관 버퍼 (노인/청년 구분)
wc_elder_layer = folium.FeatureGroup(name=f'노인복지관 노인 보행권 ({ELDERLY_10MIN_M}m)', show=False)
wc_youth_layer = folium.FeatureGroup(name=f'노인복지관 청년 보행권 ({YOUTH_10MIN_M}m)', show=False)
wc_korea = welfare_gdf[welfare_gdf['유형_간략'] == '노인복지관'].to_crs(CRS_KOREA)

for _, row in wc_korea.iterrows():
    for lyr, rad, col, op in [
        (wc_elder_layer, ELDERLY_10MIN_M, '#d62728', 0.18),
        (wc_youth_layer, YOUTH_10MIN_M,   '#1f77b4', 0.10),
    ]:
        buf = gpd.GeoDataFrame(
            geometry=[row.geometry.buffer(rad)], crs=CRS_KOREA
        ).to_crs(CRS_WGS84)
        folium.GeoJson(
            buf.geometry.__geo_interface__,
            style_function=lambda x, c=col, o=op: {
                'fillColor': c, 'color': c, 'weight': 1, 'fillOpacity': o
            },
            tooltip=f"{row['시설명']} {'노인' if rad==ELDERLY_10MIN_M else '청년'} 10분"
        ).add_to(lyr)

wc_elder_layer.add_to(m_welf)
wc_youth_layer.add_to(m_welf)
folium.LayerControl(collapsed=False).add_to(m_welf)

welf_map_path = os.path.join(OUTPUT_DIR, 'welfare_dong_map.html')
m_welf.save(welf_map_path)
print(f"  복지 지도 저장: {welf_map_path}")


# ============================================================
# 5. 행정동 단위 Vulnerability TOP10 바차트 + TOP5 리포트
# ============================================================
print("\n" + "=" * 60)
print("5. 행정동 단위 결핍 지수 리포트")
print("=" * 60)

m_valid = master_gdf[master_gdf['65세이상인구'] > 0].copy()
top10_dong = m_valid.nlargest(10, 'vulnerability_score')[
    ['구명', '동명', 'vulnerability_score', '65세이상인구',
     'welf_cov_elder', 'park_cov_elder', 'welf_박탈노인', 'park_박탈노인',
     'welf_속도격차', 'park_속도격차', '시설수']
].reset_index(drop=True)

# ── 바차트 ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(22, 8))
fig.suptitle('서울시 행정동 단위 복지 결핍 지수 TOP 10\n(보행권 박탈 노인 수 기반)',
             fontsize=14, fontweight='bold')

labels = top10_dong.apply(lambda r: f"{r['구명']}\n{r['동명']}", axis=1)

# 결핍 지수 바차트
colors_v = ['#a50f15' if v > 0.7 else '#d62728' if v > 0.4 else '#ff7f0e'
            for v in top10_dong['vulnerability_score']]
bars = axes[0].barh(labels[::-1], top10_dong['vulnerability_score'][::-1], color=colors_v[::-1])
axes[0].set_title('결핍 지수 (Vulnerability Score)', fontsize=12, fontweight='bold')
axes[0].set_xlabel('결핍 지수 (0~1)')
for bar, val in zip(bars, top10_dong['vulnerability_score'][::-1]):
    axes[0].text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                 f'{val:.3f}', va='center', fontsize=9)
axes[0].set_xlim(0, 1.1)

# 박탈 노인 수 이중 바 (복지 vs 공원)
y  = np.arange(len(top10_dong))
h  = 0.35
axes[1].barh(y + h/2, top10_dong['welf_박탈노인'][::-1], h,
             label='복지시설 박탈', color='#d62728', alpha=0.85)
axes[1].barh(y - h/2, top10_dong['park_박탈노인'][::-1], h,
             label='공원 박탈', color='#ff7f0e', alpha=0.85)
axes[1].set_yticks(y)
axes[1].set_yticklabels(labels[::-1], fontsize=9)
axes[1].set_xlabel('보행권 박탈 노인 수 (명, 노인 기준)')
axes[1].set_title('보행권 박탈 노인 수\n(노인 도보 10분 기준)', fontsize=12, fontweight='bold')
axes[1].legend(fontsize=10)

plt.tight_layout()
vuln_chart_path = os.path.join(OUTPUT_DIR, 'dong_vulnerability.png')
plt.savefig(vuln_chart_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"  결핍 지수 차트 저장: {vuln_chart_path}")

# ── TOP5 콘솔 리포트 ────────────────────────────────────────
top5 = top10_dong.head(5)
print("\n" + "=" * 70)
print("▣ 복지시설 확충이 가장 시급한 행정동 TOP 5")
print(f"   (보행 속도 기준: 노인 {ELDERLY_10MIN_M}m / 청년 {YOUTH_10MIN_M}m)")
print("=" * 70)
for rank, row in top5.iterrows():
    print(f"\n  [{rank+1}위] {row['구명']} {row['동명']}")
    print(f"    - 결핍 지수           : {row['vulnerability_score']:.4f}")
    print(f"    - 65세이상 인구       : {row['65세이상인구']:,.0f}명")
    print(f"    - 복지 보행권 커버(노인): {row['welf_cov_elder']:.1f}%  "
          f"(청년-노인 격차: {row['welf_속도격차']:.1f}%p)")
    print(f"    - 공원 보행권 커버(노인): {row['park_cov_elder']:.1f}%  "
          f"(청년-노인 격차: {row['park_속도격차']:.1f}%p)")
    print(f"    - 복지 박탈 노인 수   : {row['welf_박탈노인']:,.0f}명")
    print(f"    - 공원 박탈 노인 수   : {row['park_박탈노인']:,.0f}명")
    print(f"    - 시설 수             : {row['시설수']:.0f}개")

# ── TOP5 CSV 저장 ────────────────────────────────────────────
top5_path = os.path.join(OUTPUT_DIR, 'dong_top5_report.csv')
top5.to_csv(top5_path, index=False, encoding='utf-8-sig')

# ── 전체 동 분석 결과 저장 ──────────────────────────────────
all_dong_path = os.path.join(OUTPUT_DIR, 'dong_vulnerability_all.csv')
m_valid.sort_values('vulnerability_score', ascending=False)[[
    '구명', '동명', 'vulnerability_score', '65세이상인구',
    'welf_cov_elder', 'park_cov_elder',
    'welf_박탈노인', 'park_박탈노인',
    'welf_속도격차', 'park_속도격차',
    'welfare_index', 'green_index', '시설수'
]].to_csv(all_dong_path, index=False, encoding='utf-8-sig')

print("\n" + "=" * 60)
print("완료!")
print(f"  park_dong_map.html      → {park_map_path}")
print(f"  welfare_dong_map.html   → {welf_map_path}")
print(f"  dong_vulnerability.png  → {vuln_chart_path}")
print(f"  dong_top5_report.csv    → {top5_path}")
print(f"  dong_vulnerability_all.csv → {all_dong_path}")
print("=" * 60)
