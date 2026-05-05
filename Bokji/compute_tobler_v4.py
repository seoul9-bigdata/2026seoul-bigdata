#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_tobler_v4.py — Tobler 경사 보정 Dijkstra 재계산
==========================================================
각 행정동의 tobler_ratio 를 보행 속도에 곱해 보정된 이동 거리를
Dijkstra cutoff 로 사용, 실제 도달 가능 시설 수를 재계산한다.

입력:
  output_v2/dong_reachability_v2.csv     기존 원본 결과
  output_v2/seoul_walk.graphml           OSM 보행 네트워크 (188 MB 캐시)
  medical_LEE/outputs/tobler_ratio_LEE.csv  동별 Tobler 비율

출력:
  output_v4/dong_reachability_v4.csv
    기존 컬럼 + tobler_ratio
    + 복지_일반노인보정 / 복지_보조기기보정 / 복지_보조하위15p보정
    + 공원_일반노인보정 / 공원_보조기기보정 / 공원_보조하위15p보정
"""

import sys, warnings, io, os, re, json, time
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

import pandas as pd
import geopandas as gpd
import numpy as np
from collections import defaultdict
import networkx as nx
import osmnx as ox
import requests

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUT_V2      = os.path.join(BASE_DIR, 'output_v2')
OUT_V4      = os.path.join(BASE_DIR, 'output_v4')
GRAPH_FILE  = os.path.join(OUT_V2,  'seoul_walk.graphml')
CACHE_FILE  = os.path.join(BASE_DIR, 'output', 'geocode_cache.json')
TOBLER_FILE = os.path.join(BASE_DIR, '..', 'medical_LEE', 'outputs', 'tobler_ratio_LEE.csv')
V2_CSV      = os.path.join(OUT_V2,  'dong_reachability_v2.csv')

os.makedirs(OUT_V4, exist_ok=True)

CRS_WGS84 = 'EPSG:4326'
SECS_30   = 30 * 60   # 1800 초

# 보정 대상 속도 3종 (일반인은 보정 없이 기준값 그대로 사용)
BASE_SPEEDS = {
    '일반노인':    1.12,
    '보조기기':    0.88,
    '보조하위15p': 0.70,
}

# ── 동명 정규화 (analysis_v2.py 와 동일) ─────────────────────────────────────
DONG_NAME_MAP = {
    '종로1.2.3.4가동': '종로1·2·3·4가동',
    '종로5.6가동':      '종로5·6가동',
    '금호2.3가동':      '금호2·3가동',
    '상계3.4동':        '상계3·4동',
    '상계6.7동':        '상계6·7동',
    '중계2.3동':        '중계2·3동',
    '면목3.8동':        '면목3·8동',
    '상일1동':          '상일제1동',
    '상일2동':          '상일제2동',
    '신설동':           '용신동',
    '용두동':           '용신동',
}
def norm_dong(name):
    return DONG_NAME_MAP.get(str(name).strip(), str(name).strip())


print("=" * 60)
print("compute_tobler_v4 — Tobler 경사 보정 Dijkstra 재계산")
print("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# 1. 행정동 GeoJSON (중심점 좌표용)
# ─────────────────────────────────────────────────────────────────────────────
print("\n1. 행정동 GeoJSON 로드 (중심점 좌표)")
resp = requests.get(
    "https://raw.githubusercontent.com/vuski/admdongkor/master/"
    "ver20230701/HangJeongDong_ver20230701.geojson",
    timeout=60
)
dong_gdf = gpd.GeoDataFrame.from_features(resp.json()['features'], crs=CRS_WGS84)
dong_gdf  = dong_gdf[dong_gdf['sido'] == '11'].copy()
dong_gdf['구명']  = dong_gdf['sggnm']
dong_gdf['동명']  = dong_gdf['adm_nm'].str.split(' ').str[-1].apply(norm_dong)
dong_gdf['동_key'] = dong_gdf['구명'] + '_' + dong_gdf['동명']
dong_gdf['centroid_lon'] = dong_gdf.geometry.centroid.x
dong_gdf['centroid_lat'] = dong_gdf.geometry.centroid.y
dong_gdf = dong_gdf.drop_duplicates('동_key').reset_index(drop=True)
print(f"  {len(dong_gdf)}개 행정동")


# ─────────────────────────────────────────────────────────────────────────────
# 2. 복지·공원 시설 로드
# ─────────────────────────────────────────────────────────────────────────────
print("\n2. 복지·공원 시설 로드")

with open(CACHE_FILE, 'r', encoding='utf-8') as f:
    cache = json.load(f)

with open(os.path.join(BASE_DIR,
          "서울시 사회복지시설(노인여가복지시설) 목록.csv"), 'rb') as f:
    welfare_df = pd.read_csv(io.StringIO(f.read().decode('euc-kr')))
welfare_df.columns = [
    '시설명','시설코드','시설유형','시설종류상세',
    '자치구구분','시군구코드','시군구명','시설주소',
    '전화번호','우편번호'
]
welfare_df['시설주소'] = welfare_df['시설주소'].fillna('').str.strip()
welfare_df = welfare_df[welfare_df['시설주소'] != ''].copy()

lats, lngs = [], []
for _, row in welfare_df.iterrows():
    v = cache.get(row['시설주소'], {})
    lats.append(v.get('lat'))
    lngs.append(v.get('lng'))
welfare_df['lat'] = lats
welfare_df['lng'] = lngs
welfare_ok  = welfare_df.dropna(subset=['lat', 'lng']).copy()
welfare_gdf = gpd.GeoDataFrame(
    welfare_ok,
    geometry=gpd.points_from_xy(welfare_ok['lng'], welfare_ok['lat']),
    crs=CRS_WGS84
)
print(f"  복지시설 {len(welfare_gdf)}개 좌표 확보")

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
    m = re.search(r'[\d,.]+', str(v).replace(',', ''))
    return float(m.group().replace(',', '')) if m else np.nan
parks_raw['면적_m2'] = parks_raw['면적'].apply(parse_area)
parks_df = (parks_raw[parks_raw['지역'].isin(SEOUL_GU)]
            .dropna(subset=['X_WGS84', 'Y_WGS84', '면적_m2'])
            .copy())
parks_df = parks_df[parks_df['X_WGS84'] > 0]
parks_gdf = gpd.GeoDataFrame(
    parks_df,
    geometry=gpd.points_from_xy(parks_df['X_WGS84'], parks_df['Y_WGS84']),
    crs=CRS_WGS84
)
print(f"  공원 {len(parks_gdf)}개 좌표 확보")


# ─────────────────────────────────────────────────────────────────────────────
# 3. OSM 보행 네트워크 로드 (캐시)
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n3. OSM 그래프 로드: {GRAPH_FILE}")
G   = ox.load_graphml(GRAPH_FILE)
G_u = ox.convert.to_undirected(G)
print(f"  노드 {G_u.number_of_nodes():,}개  엣지 {G_u.number_of_edges():,}개")


# ─────────────────────────────────────────────────────────────────────────────
# 4. 시설별 OSM 최근접 노드 사전 계산
# ─────────────────────────────────────────────────────────────────────────────
print("\n4. 시설 OSM 노드 매핑")

welfare_nodes_arr = ox.nearest_nodes(
    G_u, welfare_gdf.geometry.x.tolist(), welfare_gdf.geometry.y.tolist()
)
welfare_gdf = welfare_gdf.copy()
welfare_gdf['osm_node'] = welfare_nodes_arr

park_nodes_arr = ox.nearest_nodes(
    G_u, parks_gdf.geometry.x.tolist(), parks_gdf.geometry.y.tolist()
)
parks_gdf = parks_gdf.copy()
parks_gdf['osm_node'] = park_nodes_arr

welfare_node_count = defaultdict(int)
for n in welfare_gdf['osm_node']:
    welfare_node_count[n] += 1
park_node_count = defaultdict(int)
for n in parks_gdf['osm_node']:
    park_node_count[n] += 1

print(f"  복지 노드 {len(welfare_node_count)}개 / 공원 노드 {len(park_node_count)}개")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Tobler 비율 조인
# ─────────────────────────────────────────────────────────────────────────────
print("\n5. Tobler 비율 조인")

tobler = pd.read_csv(TOBLER_FILE)
tobler['gu']       = tobler['full_name'].str.split(' ').str[0]
tobler['dong_raw'] = tobler['full_name'].str.split(' ').str[1]
tobler['동_key']   = tobler['gu'] + '_' + tobler['dong_raw'].apply(norm_dong)

v2_df = pd.read_csv(V2_CSV, encoding='utf-8-sig')
v2_df.columns = [c.strip() for c in v2_df.columns]

merged = v2_df.merge(tobler[['동_key', 'tobler_ratio']], on='동_key', how='left')
n_miss = merged['tobler_ratio'].isna().sum()
merged['tobler_ratio'] = merged['tobler_ratio'].fillna(1.0)
print(f"  매칭: {len(merged) - n_miss}/{len(merged)}  (미매칭 {n_miss}개 → tobler=1.0)")

# 중심점 좌표 병합
dong_centers = dong_gdf[['동_key', 'centroid_lon', 'centroid_lat']].drop_duplicates('동_key')
merged = merged.merge(dong_centers, on='동_key', how='left')
n_no_center = merged['centroid_lon'].isna().sum()
if n_no_center:
    print(f"  경고: 중심점 없는 동 {n_no_center}개 → 해당 동은 0으로 처리")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tobler 보정 Dijkstra 계산
# ─────────────────────────────────────────────────────────────────────────────
print("\n6. Tobler 보정 Dijkstra 계산")
total_runs = len(merged) * len(BASE_SPEEDS)
print(f"  {len(merged)}개 동 × {len(BASE_SPEEDS)}개 속도 = {total_runs:,}회 Dijkstra")
print(f"  (일반인 속도는 보정 없이 기존 값 그대로 사용)\n")

col_names = []
for k in BASE_SPEEDS:
    col_names.append(f'복지_{k}보정')
    col_names.append(f'공원_{k}보정')

col_data = {c: [] for c in col_names}

t0 = time.time()
for idx, row in merged.iterrows():
    lon = row.get('centroid_lon')
    lat = row.get('centroid_lat')
    tobler_r = float(row['tobler_ratio'])

    # 중심점 없는 동: 0으로 채움
    if pd.isna(lon) or pd.isna(lat):
        for k in BASE_SPEEDS:
            col_data[f'복지_{k}보정'].append(0)
            col_data[f'공원_{k}보정'].append(0)
        continue

    try:
        center_node = ox.nearest_nodes(G_u, lon, lat)
    except Exception:
        for k in BASE_SPEEDS:
            col_data[f'복지_{k}보정'].append(0)
            col_data[f'공원_{k}보정'].append(0)
        continue

    for speed_key, base_mps in BASE_SPEEDS.items():
        corrected_dist = int(base_mps * tobler_r * SECS_30)
        try:
            reachable = nx.single_source_dijkstra_path_length(
                G_u, center_node, cutoff=corrected_dist, weight='length'
            )
            reach_set = set(reachable.keys())
            w_cnt = sum(welfare_node_count[n] for n in reach_set if n in welfare_node_count)
            p_cnt = sum(park_node_count[n]    for n in reach_set if n in park_node_count)
        except Exception:
            w_cnt = p_cnt = 0
        col_data[f'복지_{speed_key}보정'].append(w_cnt)
        col_data[f'공원_{speed_key}보정'].append(p_cnt)

    done = idx + 1
    if done % 50 == 0 or done == len(merged):
        elapsed = time.time() - t0
        remain  = elapsed / done * (len(merged) - done)
        print(f"  [{done:3d}/{len(merged)}]  경과 {elapsed/60:.1f}분  "
              f"남은 예상 {remain/60:.1f}분")


# ─────────────────────────────────────────────────────────────────────────────
# 7. 결과 저장
# ─────────────────────────────────────────────────────────────────────────────
print("\n7. 결과 저장")

for col, vals in col_data.items():
    merged[col] = vals

# 출력 컬럼: 기존 v2 컬럼 + tobler_ratio + 보정 컬럼 (중심점 컬럼 제외)
out_cols = (
    list(v2_df.columns)
    + ['tobler_ratio']
    + col_names
)
out_df   = merged[[c for c in out_cols if c in merged.columns]]
out_path = os.path.join(OUT_V4, 'dong_reachability_v4.csv')
out_df.to_csv(out_path, index=False, encoding='utf-8-sig')

total_min = (time.time() - t0) / 60
size_kb   = os.path.getsize(out_path) / 1024

print(f"  저장: {out_path}")
print(f"  크기: {size_kb:.0f} KB  행: {len(out_df)}  열: {len(out_df.columns)}")
print(f"  추가 컬럼: {col_names}")
print(f"\n  총 소요 시간: {total_min:.1f}분")
print("\n" + "=" * 60)
print("compute_tobler_v4 완료!")
print("다음 단계: python generate_dashboard_v4.py")
print("=" * 60)
