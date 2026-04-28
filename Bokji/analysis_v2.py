"""
analysis_v2.py — 서울시 노인 복지·녹지 접근성 분석 v2
=======================================================
팀 통합 파라미터 표준 반영:
  - 출발점: 행정동 중심점 426개
  - 거리 계산: OSM 보행 네트워크 (실제 도로망)
  - 보행 속도 (4단계):
      일반인       1.28 m/s  한음 외(2020)
      일반노인     1.12 m/s
      보조기기     0.88 m/s  메인 비교 대상
      보조하위15p  0.70 m/s  최약계층
  - 분석 기준 시간: 30분 (15·45분 병행)
  - 출력: output_v2/ (기존 output/ 미변경)
"""

import sys, warnings
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
import io, os, re, json, time
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, MultiPolygon
from shapely.ops import unary_union
import folium
import branca.colormap as bc
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import koreanize_matplotlib
import requests
import networkx as nx
import osmnx as ox

print("=" * 60)
print("analysis_v2 — OSM 보행 네트워크 기반 접근성 분석")
print("=" * 60)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output_v2")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE_FILE = os.path.join(BASE_DIR, "output", "geocode_cache.json")
GRAPH_FILE = os.path.join(OUTPUT_DIR, "seoul_walk.graphml")

CRS_WGS84 = "EPSG:4326"
CRS_KOREA = "EPSG:5179"

# ── 팀 통일 보행 속도 파라미터 ───────────────────────────────
# 컬럼명에 %를 피하기 위해 보조하위15p 사용
SPEEDS = {
    '일반인':      1.28,   # m/s  한음 외(2020)
    '일반노인':    1.12,   # m/s
    '보조기기':    0.88,   # m/s  메인 비교 대상
    '보조하위15p': 0.70,   # m/s  최약계층 보조 시각화용
}
TIMES_SEC = {15: 15 * 60, 30: 30 * 60, 45: 45 * 60}
MAIN_MIN  = 30

SPEED_LABELS = {
    '일반인':      '일반인\n(1.28 m/s)',
    '일반노인':    '일반 노인\n(1.12 m/s)',
    '보조기기':    '보조기기\n(0.88 m/s)',
    '보조하위15p': '보조 하위15%\n(0.70 m/s)',
}
SPEED_COLORS = {
    '일반인':      '#2196F3',
    '일반노인':    '#4CAF50',
    '보조기기':    '#FF9800',
    '보조하위15p': '#F44336',
}

def walk_dist(speed_key, minutes):
    return int(SPEEDS[speed_key] * TIMES_SEC[minutes])

SPEED_DIST_30 = {s: walk_dist(s, MAIN_MIN) for s in SPEEDS}
# 일반인 2304m / 일반노인 2016m / 보조기기 1584m / 보조하위15p 1260m

# ── 행정동 이름 정규화 ────────────────────────────────────────
DONG_NAME_MAP = {
    '종로1.2.3.4가동': '종로1·2·3·4가동',
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
print("\n1. 데이터 로드")
print("-" * 40)

resp = requests.get(
    "https://raw.githubusercontent.com/vuski/admdongkor/master/"
    "ver20230701/HangJeongDong_ver20230701.geojson", timeout=60
)
dong_gdf = gpd.GeoDataFrame.from_features(resp.json()['features'], crs=CRS_WGS84)
dong_gdf = dong_gdf[dong_gdf['sido'] == '11'].copy()
dong_gdf['구명']  = dong_gdf['sggnm']
dong_gdf['동명']  = dong_gdf['adm_nm'].str.split(' ').str[-1]
dong_gdf['동_key'] = dong_gdf['구명'] + '_' + dong_gdf['동명']
dong_gdf = dong_gdf.reset_index(drop=True)
dong_gdf['centroid_lon'] = dong_gdf.geometry.centroid.x
dong_gdf['centroid_lat'] = dong_gdf.geometry.centroid.y
print(f"  서울 행정동 {len(dong_gdf)}개")

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
    elderly[c] = pd.to_numeric(elderly[c].astype(str).str.replace(',',''), errors='coerce')
elderly = elderly.dropna(subset=['65세이상'])
elderly['동명_norm'] = elderly['동명'].apply(norm_dong)
elderly['동_key']    = elderly['구명'] + '_' + elderly['동명_norm']
elderly_dong = (
    elderly[['동_key','구명','동명','전체인구','65세이상']]
    .groupby('동_key').agg(
        구명=('구명','first'), 동명=('동명','first'),
        전체인구=('전체인구','sum'), pop65=('65세이상','sum')
    ).reset_index()
)
elderly_dong.rename(columns={'pop65':'65세이상인구'}, inplace=True)
elderly_dong['고령화율'] = (elderly_dong['65세이상인구'] / elderly_dong['전체인구'] * 100).round(2)
print(f"  고령인구 행정동 {len(elderly_dong)}개")

with open(os.path.join(BASE_DIR, "서울시 사회복지시설(노인여가복지시설) 목록.csv"), 'rb') as f:
    welfare_df = pd.read_csv(io.StringIO(f.read().decode('euc-kr')))
welfare_df.columns = [
    '시설명','시설코드','시설유형','시설종류상세',
    '자치구구분','시군구코드','시군구명','시설주소',
    '전화번호','우편번호'
]
welfare_df['시설주소'] = welfare_df['시설주소'].fillna('').str.strip()
welfare_df = welfare_df[welfare_df['시설주소'] != ''].copy()

def short_type(t):
    if '소규모' in t:   return '노인복지관(소규모)'
    if '노인교실' in t: return '노인교실'
    return '노인복지관'
welfare_df['유형_간략'] = welfare_df['시설유형'].apply(short_type)
print(f"  복지시설 {len(welfare_df)}개  유형: {welfare_df['유형_간략'].value_counts().to_dict()}")

parks_raw = pd.read_excel(os.path.join(BASE_DIR, "서울시 주요 공원현황(2026 상반기).xlsx"))
parks_raw.columns = [
    '연번','관리부서','전화번호','공원명','공원개요',
    '면적','개원일','주요시설','주요식물','안내도',
    '오시는길','이용시참고사항','이미지','지역','공원주소',
    'X_GRS80','Y_GRS80','X_WGS84','Y_WGS84','바로가기'
]
SEOUL_GU = dong_gdf['구명'].unique().tolist()
def parse_area(v):
    m = re.search(r'[\d,.]+', str(v).replace(',',''))
    return float(m.group().replace(',','')) if m else np.nan
parks_raw['면적_m2'] = parks_raw['면적'].apply(parse_area)
parks_df = parks_raw[parks_raw['지역'].isin(SEOUL_GU)].dropna(
    subset=['X_WGS84','Y_WGS84','면적_m2']
).copy()
parks_df = parks_df[parks_df['X_WGS84'] > 0]
parks_gdf = gpd.GeoDataFrame(
    parks_df,
    geometry=gpd.points_from_xy(parks_df['X_WGS84'], parks_df['Y_WGS84']),
    crs=CRS_WGS84
)
print(f"  공원 {len(parks_gdf)}개")


# ============================================================
# 2. 복지시설 지오코딩 (기존 캐시 재활용)
# ============================================================
print("\n2. 복지시설 지오코딩 (캐시 재활용)")
print("-" * 40)

cache = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    ok = sum(1 for v in cache.values() if v.get('lat'))
    print(f"  캐시 {len(cache)}건 로드  (성공 {ok}건)")

lats, lngs = [], []
for _, row in welfare_df.iterrows():
    v = cache.get(row['시설주소'], {})
    lats.append(v.get('lat'))
    lngs.append(v.get('lng'))

welfare_df = welfare_df.copy()
welfare_df['lat'] = lats
welfare_df['lng'] = lngs
welfare_ok  = welfare_df.dropna(subset=['lat','lng']).copy()
welfare_gdf = gpd.GeoDataFrame(
    welfare_ok,
    geometry=gpd.points_from_xy(welfare_ok['lng'], welfare_ok['lat']),
    crs=CRS_WGS84
)
print(f"  좌표 확보: {len(welfare_gdf)}/{len(welfare_df)}개")


# ============================================================
# 3. OSM 보행 네트워크 로드
# ============================================================
print("\n3. OSM 보행 네트워크")
print("-" * 40)

if os.path.exists(GRAPH_FILE):
    print(f"  캐시에서 로드: {GRAPH_FILE}")
    G = ox.load_graphml(GRAPH_FILE)
else:
    print("  서울 보행 네트워크 다운로드 중... (최초 1회, 5~15분 소요)")
    G = ox.graph_from_place("Seoul, South Korea", network_type="walk")
    ox.save_graphml(G, GRAPH_FILE)
    print(f"  저장 완료: {GRAPH_FILE}")

G_u = ox.convert.to_undirected(G)
print(f"  노드 {G_u.number_of_nodes():,}개  엣지 {G_u.number_of_edges():,}개")


# ============================================================
# 4. 시설별 OSM 최근접 노드 사전 계산
# ============================================================
print("\n4. 시설 OSM 노드 매핑")
print("-" * 40)

welfare_nodes = ox.nearest_nodes(G_u, welfare_gdf.geometry.x.tolist(), welfare_gdf.geometry.y.tolist())
welfare_gdf = welfare_gdf.copy()
welfare_gdf['osm_node'] = welfare_nodes
print(f"  복지시설 {len(welfare_gdf)}개 매핑 완료")

park_nodes_arr = ox.nearest_nodes(G_u, parks_gdf.geometry.x.tolist(), parks_gdf.geometry.y.tolist())
parks_gdf = parks_gdf.copy()
parks_gdf['osm_node'] = park_nodes_arr
print(f"  공원 {len(parks_gdf)}개 매핑 완료")

from collections import defaultdict
welfare_node_count = defaultdict(int)
for n in welfare_gdf['osm_node']:
    welfare_node_count[n] += 1
park_node_count = defaultdict(int)
for n in parks_gdf['osm_node']:
    park_node_count[n] += 1


# ============================================================
# 5. 행정동 중심점 기반 도달 가능 시설 수 계산
# ============================================================
print("\n5. 행정동 중심점 → OSM 네트워크 도달 가능 시설 수")
print("-" * 40)
print(f"  기준: {MAIN_MIN}분 보행")
for s, d in SPEED_DIST_30.items():
    print(f"    {s}: {d}m")

rows = []
n_dongs = len(dong_gdf)
t0 = time.time()

for i, d in dong_gdf.iterrows():
    try:
        center_node = ox.nearest_nodes(G_u, d['centroid_lon'], d['centroid_lat'])
    except Exception:
        rows.append({'동_key': d['동_key']})
        continue

    row = {'동_key': d['동_key']}
    for speed_key, dist_m in SPEED_DIST_30.items():
        try:
            reachable = nx.single_source_dijkstra_path_length(
                G_u, center_node, cutoff=dist_m, weight='length'
            )
            reach_set = set(reachable.keys())
            welfare_cnt = sum(welfare_node_count[n] for n in reach_set if n in welfare_node_count)
            park_cnt    = sum(park_node_count[n]    for n in reach_set if n in park_node_count)
        except Exception:
            welfare_cnt = park_cnt = 0
        row[f'복지_{speed_key}'] = welfare_cnt
        row[f'공원_{speed_key}'] = park_cnt
    rows.append(row)

    if (i + 1) % 50 == 0 or (i + 1) == n_dongs:
        print(f"  [{i+1}/{n_dongs}]  경과 {time.time()-t0:.0f}s")

reach_df = pd.DataFrame(rows)
print(f"  계산 완료: {len(reach_df)}개 행정동")


# ============================================================
# 6. 메트릭 산출 및 Vulnerability Score v2
# ============================================================
print("\n6. 메트릭 산출")
print("-" * 40)

master = dong_gdf[['동_key','구명','동명','geometry']].merge(
    reach_df, on='동_key', how='left'
).merge(
    elderly_dong[['동_key','65세이상인구','고령화율','전체인구']], on='동_key', how='left'
)
master['65세이상인구'] = master['65세이상인구'].fillna(0)

# 속도 격차: 일반인 - 보조하위15p (최약계층 기준)
master['복지_속도격차'] = master['복지_일반인'] - master['복지_보조하위15p']
master['공원_속도격차'] = master['공원_일반인'] - master['공원_보조하위15p']

# 접근 불가: 최약계층(보조하위15p) 기준 30분 내 0개
master['복지_접근불가'] = (master['복지_보조하위15p'] == 0).astype(int)
master['공원_접근불가'] = (master['공원_보조하위15p'] == 0).astype(int)
master['복지_박탈노인'] = master['복지_접근불가'] * master['65세이상인구']
master['공원_박탈노인'] = master['공원_접근불가'] * master['65세이상인구']

def minmax(s):
    mn, mx = s.min(), s.max()
    return (s - mn) / (mx - mn + 1e-9)

valid = master[master['65세이상인구'] > 0].copy()
valid['norm_welf'] = minmax(valid['복지_박탈노인'])
valid['norm_park'] = minmax(valid['공원_박탈노인'])
valid['vulnerability_v2'] = (valid['norm_welf'] * 0.50 + valid['norm_park'] * 0.50).round(4)

master = master.merge(valid[['동_key','vulnerability_v2']], on='동_key', how='left')
master['vulnerability_v2'] = master['vulnerability_v2'].fillna(0)

print(f"  행정동 {len(master)}개  취약도 산출 완료")
print(f"  복지 접근 불가 동 (보조하위15p): {master['복지_접근불가'].sum()}개")
print(f"  공원 접근 불가 동 (보조하위15p): {master['공원_접근불가'].sum()}개")

top5 = (master[master['65세이상인구'] > 0]
        .nlargest(5, 'vulnerability_v2')
        [['동_key','구명','동명','65세이상인구',
          '복지_일반인','복지_보조기기','복지_보조하위15p',
          '공원_일반인','공원_보조기기','공원_보조하위15p',
          '복지_박탈노인','공원_박탈노인','vulnerability_v2']])
print("\n  취약도 TOP 5:")
print(top5.to_string(index=False))


# ============================================================
# 7. CSV 저장
# ============================================================
print("\n7. CSV 저장")
print("-" * 40)

out_cols = [
    '동_key','구명','동명','65세이상인구','고령화율',
    '복지_일반인','복지_일반노인','복지_보조기기','복지_보조하위15p',
    '공원_일반인','공원_일반노인','공원_보조기기','공원_보조하위15p',
    '복지_속도격차','공원_속도격차',
    '복지_박탈노인','공원_박탈노인','vulnerability_v2'
]
(master[[c for c in out_cols if c in master.columns]]
 .to_csv(os.path.join(OUTPUT_DIR, "dong_reachability_v2.csv"), index=False, encoding='utf-8-sig'))
top5.to_csv(os.path.join(OUTPUT_DIR, "top5_vulnerable_dong_v2.csv"), index=False, encoding='utf-8-sig')
print(f"  dong_reachability_v2.csv  top5_vulnerable_dong_v2.csv 저장 완료")


# ============================================================
# 8. 정적 차트
# ============================================================
print("\n8. 차트 생성")
print("-" * 40)

SPD_KEYS   = list(SPEEDS.keys())          # 4개
SPD_LABELS = [SPEED_LABELS[k] for k in SPD_KEYS]
SPD_COLORS = [SPEED_COLORS[k] for k in SPD_KEYS]

# ── 8-A. 히트맵: 구 × 보행속도별 평균 도달 시설 수 ──────────
agg_dict = {}
for s in SPD_KEYS:
    agg_dict[f'복지_{s}'] = 'mean'
    agg_dict[f'공원_{s}'] = 'mean'
gu_avg = master.groupby('구명').agg(agg_dict).round(2)

fig, axes = plt.subplots(1, 2, figsize=(20, 10))
for ax, kind, prefix, title in [
    (axes[0], '복지시설', '복지', '행정구 × 보행속도별 평균 도달 복지시설 수 (30분)'),
    (axes[1], '공원',     '공원', '행정구 × 보행속도별 평균 도달 공원 수 (30분)'),
]:
    cols = [f'{prefix}_{s}' for s in SPD_KEYS]
    hm   = gu_avg[cols].T
    hm.index = SPD_LABELS
    im = ax.imshow(hm.values, aspect='auto', cmap='YlOrRd')
    ax.set_xticks(range(len(hm.columns)))
    ax.set_xticklabels(hm.columns, rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(len(hm.index)))
    ax.set_yticklabels(hm.index, fontsize=9)
    vmax = hm.values.max() if hm.values.max() > 0 else 1
    for r in range(hm.shape[0]):
        for c in range(hm.shape[1]):
            v = hm.values[r, c]
            ax.text(c, r, f'{v:.1f}', ha='center', va='center',
                    fontsize=6, color='black' if v < vmax * 0.7 else 'white')
    plt.colorbar(im, ax=ax, label=f'평균 도달 {kind} 수')
    ax.set_title(title, fontsize=11, pad=10)

plt.suptitle('서울시 보행속도별 시설 접근성 히트맵 (OSM 네트워크 기반)', fontsize=13, y=1.01)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "v2_heatmap.png"), dpi=150, bbox_inches='tight')
plt.close()
print("  v2_heatmap.png 저장")

# ── 8-B. 속도 격차 막대 (구 단위, 4속도) ─────────────────────
fig, axes = plt.subplots(1, 2, figsize=(22, 8))
for ax, prefix, sort_key, title in [
    (axes[0], '복지', '복지_일반인', '복지시설 도달 수 비교 (30분 · 구 평균)'),
    (axes[1], '공원', '공원_일반인', '공원 도달 수 비교 (30분 · 구 평균)'),
]:
    cols   = [f'{prefix}_{s}' for s in SPD_KEYS]
    sorted_df = gu_avg.sort_values(sort_key, ascending=False)
    x  = np.arange(len(sorted_df))
    bw = 0.18
    offsets = np.linspace(-bw * 1.5, bw * 1.5, 4)
    for idx, (s, color, lbl) in enumerate(zip(SPD_KEYS, SPD_COLORS, SPD_LABELS)):
        ax.bar(x + offsets[idx], sorted_df[f'{prefix}_{s}'], bw,
               label=lbl.replace('\n', ' '), color=color, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(sorted_df.index, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('평균 도달 가능 수')
    ax.set_title(title, fontsize=11)
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis='y', alpha=0.3)

plt.suptitle('보행속도별 접근 격차 비교 (OSM 네트워크 기반)', fontsize=13)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "v2_speed_gap.png"), dpi=150, bbox_inches='tight')
plt.close()
print("  v2_speed_gap.png 저장")

# ── 8-C. TOP10 취약 행정동 대시보드 ──────────────────────────
top10 = (master[master['65세이상인구'] > 0]
         .nlargest(10, 'vulnerability_v2').reset_index(drop=True))

fig, axes = plt.subplots(1, 3, figsize=(22, 8))

# 취약도 바
t10s = top10.sort_values('vulnerability_v2')
axes[0].barh(
    t10s['동_key'].str.replace('_', ' '),
    t10s['vulnerability_v2'],
    color=plt.cm.YlOrRd(np.linspace(0.3, 0.95, len(t10s)))
)
axes[0].set_xlabel('취약도 지수 v2')
axes[0].set_title('취약도 TOP 10 행정동', fontsize=11)

# 복지 / 공원 4속도 비교
for ax, prefix, ax_title in [
    (axes[1], '복지', '복지시설 접근 (TOP10 취약 동)'),
    (axes[2], '공원', '공원 접근 (TOP10 취약 동)'),
]:
    x  = np.arange(len(top10))
    bw = 0.18
    offsets = np.linspace(-bw * 1.5, bw * 1.5, 4)
    for idx, (s, color, lbl) in enumerate(zip(SPD_KEYS, SPD_COLORS, SPD_LABELS)):
        ax.bar(x + offsets[idx], top10[f'{prefix}_{s}'], bw,
               label=lbl.replace('\n', ' '), color=color, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(top10['동_key'].str.replace('_', '\n'), rotation=45, ha='right', fontsize=7)
    ax.set_ylabel('도달 가능 수')
    ax.set_title(ax_title, fontsize=11)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(axis='y', alpha=0.3)

plt.suptitle('취약 행정동 TOP 10 접근성 대시보드 (OSM 네트워크 · 30분 기준)', fontsize=13)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "v2_top10_dashboard.png"), dpi=150, bbox_inches='tight')
plt.close()
print("  v2_top10_dashboard.png 저장")

# ── 8-D. 레이더 차트: TOP5 취약 동 비교 (8축) ────────────────
top5_vis = master[master['65세이상인구'] > 0].nlargest(5, 'vulnerability_v2').reset_index(drop=True)
cat_keys = [f'복지_{s}' for s in SPD_KEYS] + [f'공원_{s}' for s in SPD_KEYS]
cat_labels = (
    ['복지\n일반인', '복지\n일반노인', '복지\n보조기기', '복지\n보조하위15%'] +
    ['공원\n일반인', '공원\n일반노인', '공원\n보조기기', '공원\n보조하위15%']
)
N = len(cat_keys)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
radar_colors = ['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00']
max_vals = master[cat_keys].max()

for idx, row in top5_vis.iterrows():
    vals = [row[c] / (max_vals[c] + 1e-9) for c in cat_keys]
    vals += vals[:1]
    ax.plot(angles, vals, 'o-', linewidth=2, color=radar_colors[idx],
            label=f"{row['구명']} {row['동명']}")
    ax.fill(angles, vals, alpha=0.12, color=radar_colors[idx])

ax.set_xticks(angles[:-1])
ax.set_xticklabels(cat_labels, fontsize=9)
ax.set_ylim(0, 1)
ax.set_yticks([0.25, 0.5, 0.75, 1.0])
ax.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=8)
ax.legend(loc='upper right', bbox_to_anchor=(1.4, 1.1), fontsize=10)
ax.set_title('취약 TOP5 행정동 — 보행속도별 접근성 레이더\n(전체 최대값 대비 비율)',
             fontsize=12, pad=20)

plt.savefig(os.path.join(OUTPUT_DIR, "v2_radar.png"), dpi=150, bbox_inches='tight')
plt.close()
print("  v2_radar.png 저장")


# ============================================================
# 9. Folium 인터랙티브 지도
# ============================================================
print("\n9. Folium 지도 생성")
print("-" * 40)

dong_map_gdf = dong_gdf[['동_key','구명','동명','geometry']].merge(
    master[['동_key','복지_일반인','복지_일반노인','복지_보조기기','복지_보조하위15p',
            '공원_일반인','공원_일반노인','공원_보조기기','공원_보조하위15p',
            '복지_속도격차','공원_속도격차','65세이상인구','vulnerability_v2']],
    on='동_key', how='left'
).fillna(0)

m = folium.Map(location=[37.5665, 126.9780], zoom_start=11, tiles='CartoDB positron')

# 레이어 1: 취약도 단계구분도
vul_fg = folium.FeatureGroup(name='취약도 지수 v2 (행정동)', show=True)
vul_cm = bc.linear.YlOrRd_09.scale(
    dong_map_gdf['vulnerability_v2'].min(),
    dong_map_gdf['vulnerability_v2'].max()
)
for _, row in dong_map_gdf.iterrows():
    geom = row['geometry']
    if geom is None or geom.is_empty:
        continue
    folium.GeoJson(
        geom.__geo_interface__,
        style_function=lambda f, vul=row['vulnerability_v2']: {
            'fillColor': vul_cm(vul), 'fillOpacity': 0.65,
            'color': '#555', 'weight': 0.4
        },
        tooltip=folium.Tooltip(
            f"<b>{row['구명']} {row['동명']}</b><br>"
            f"취약도: {row['vulnerability_v2']:.3f}<br>"
            f"─ 복지 ─<br>"
            f"일반인: {int(row['복지_일반인'])}개 &nbsp; "
            f"일반노인: {int(row['복지_일반노인'])}개<br>"
            f"보조기기: {int(row['복지_보조기기'])}개 &nbsp; "
            f"보조하위15%: {int(row['복지_보조하위15p'])}개<br>"
            f"─ 공원 ─<br>"
            f"일반인: {int(row['공원_일반인'])}개 &nbsp; "
            f"일반노인: {int(row['공원_일반노인'])}개<br>"
            f"보조기기: {int(row['공원_보조기기'])}개 &nbsp; "
            f"보조하위15%: {int(row['공원_보조하위15p'])}개<br>"
            f"65세이상: {int(row['65세이상인구'])}명"
        )
    ).add_to(vul_fg)
vul_fg.add_to(m)
vul_cm.caption = '취약도 지수 v2'
vul_cm.add_to(m)

# 레이어 2: 속도격차 단계구분도
gap_fg = folium.FeatureGroup(name='복지 속도격차 (일반인−보조하위15%)', show=False)
max_gap = dong_map_gdf['복지_속도격차'].max() or 1
for _, row in dong_map_gdf.iterrows():
    geom = row['geometry']
    if geom is None or geom.is_empty:
        continue
    ratio = min(row['복지_속도격차'] / max_gap, 1)
    r = int(255 * ratio); b = int(255 * (1 - ratio))
    folium.GeoJson(
        geom.__geo_interface__,
        style_function=lambda f, c=f'#{r:02x}00{b:02x}': {
            'fillColor': c, 'fillOpacity': 0.6, 'color': '#555', 'weight': 0.3
        },
        tooltip=folium.Tooltip(
            f"<b>{row['구명']} {row['동명']}</b><br>"
            f"복지 속도격차: {int(row['복지_속도격차'])}개<br>"
            f"공원 속도격차: {int(row['공원_속도격차'])}개"
        )
    ).add_to(gap_fg)
gap_fg.add_to(m)

# 레이어 3: 복지시설 마커
TYPE_COLOR = {'노인복지관': 'blue', '노인교실': 'orange', '노인복지관(소규모)': 'lightblue'}
welfare_fg = folium.FeatureGroup(name='복지시설', show=False)
for _, row in welfare_gdf.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lng']], radius=4,
        color=TYPE_COLOR.get(row['유형_간략'], 'gray'),
        fill=True, fill_opacity=0.8,
        tooltip=f"{row['시설명']} ({row['유형_간략']})"
    ).add_to(welfare_fg)
welfare_fg.add_to(m)

# 레이어 4: 공원 마커
park_fg = folium.FeatureGroup(name='공원', show=False)
for _, row in parks_gdf.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=max(3, min(12, row['면적_m2'] / 100_000)),
        color='green', fill=True, fill_opacity=0.5,
        tooltip=f"{row['공원명']} ({row['면적_m2']:,.0f}㎡)"
    ).add_to(park_fg)
park_fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(os.path.join(OUTPUT_DIR, "v2_accessibility_map.html"))
print("  v2_accessibility_map.html 저장")


# ============================================================
# 완료 요약
# ============================================================
print("\n" + "=" * 60)
print("analysis_v2 완료!")
print(f"  출력 폴더: {OUTPUT_DIR}")
print("  생성 파일:")
for fname in sorted(os.listdir(OUTPUT_DIR)):
    fpath = os.path.join(OUTPUT_DIR, fname)
    size  = os.path.getsize(fpath)
    unit  = 'KB' if size < 1_000_000 else 'MB'
    val   = size / 1024 if size < 1_000_000 else size / 1_048_576
    print(f"    {fname:<42} {val:6.1f} {unit}")
print("=" * 60)
