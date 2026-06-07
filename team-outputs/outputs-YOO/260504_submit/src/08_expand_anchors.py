"""
08_expand_anchors.py — 탭 4 거점 확장

기존: 거점 시장 + 노인복지관
추가:
  - 🌳 거점 공원 (YANG xlsx, 면적 ≥ 50,000m²)
  - 🚌 장거리 터미널·기차역 (수동 좌표)
  - 📜 노인 명소 (탑골·종묘·광장시장 등)
  - 🚇 노인 도착 TOP 환승역 (자동 — elderly_card_trips goff TOP)

출력: data/anchor_access.json (확장)
"""
import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import duckdb
from sklearn.neighbors import BallTree

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB   = ROOT.parent / "data" / "seoul.duckdb"
PARK_XLSX = ROOT.parent.parent / "Bokji" / "서울시 주요 공원현황(2026 상반기).xlsx"

EARTH_R = 6371000

# ── 수동 좌표 ──
TERMINALS = [
    ("서울고속버스터미널", "서초구", 37.5051, 127.0050),
    ("동서울종합터미널",   "광진구", 37.5345, 127.0944),
    ("서울남부터미널",     "서초구", 37.4847, 127.0151),
    ("강변고속버스터미널",  "광진구", 37.5345, 127.0941),
    ("서울역",            "용산구", 37.5547, 126.9707),
    ("청량리역",          "동대문구", 37.5800, 127.0466),
    ("용산역",            "용산구", 37.5298, 126.9648),
    ("영등포역",          "영등포구", 37.5156, 126.9075),
]
ICONIC = [
    ("탑골공원",       "종로구",   37.5712, 126.9885),
    ("종묘",           "종로구",   37.5740, 126.9941),
    ("광장시장",       "종로구",   37.5705, 126.9994),
    ("동대문(흥인지문)", "종로구",   37.5715, 127.0099),
    ("덕수궁",         "중구",     37.5658, 126.9750),
]


def load_anchor_markets():
    mkts = json.load(open(DATA / 'shim_mkt.json'))
    df = pd.DataFrame(mkts)
    keywords = ['가락', '남대문', '동대문', '경동', '노량진', '광장', '청량리', '신촌', '망원', '암사']
    is_famous = df['name'].apply(lambda n: any(k in n for k in keywords))
    is_big = df['stores'] >= 80
    anchor = df[is_famous | is_big].copy()
    anchor['anchor_type'] = '거점 시장'
    log.info("거점 시장: %d개", len(anchor))
    return anchor[['name','gu','lat','lng','anchor_type']].rename(columns={'lng':'lon'})


def load_welfare_centers():
    cache_path = ROOT.parent.parent / "Bokji" / "output" / "geocode_cache.json"
    geo_cache = json.load(open(cache_path)) if cache_path.exists() else {}
    df = pd.read_csv(ROOT.parent.parent / "Bokji" / "서울시 사회복지시설(노인여가복지시설) 목록.csv", encoding='cp949')
    centers = df[df['시설종류명(시설유형)'] == '(노인복지시설) 노인복지관'].copy()
    rows = []
    for _, r in centers.iterrows():
        coord = geo_cache.get(r.get('시설주소',''))
        if coord:
            rows.append({
                'name': r['시설명'], 'gu': r['시군구명'],
                'lat': coord['lat'], 'lon': coord['lng'],
                'anchor_type': '노인복지관',
            })
    log.info("노인복지관: %d개", len(rows))
    return pd.DataFrame(rows)


def load_anchor_parks(min_area=50_000):
    df = pd.read_excel(PARK_XLSX)
    df['면적_숫자'] = pd.to_numeric(
        df['면적'].astype(str).str.replace(',','').str.replace('㎡','').str.strip(), errors='coerce')
    df = df.dropna(subset=['X좌표(WGS84)','Y좌표(WGS84)','면적_숫자'])
    big = df[df['면적_숫자'] >= min_area].copy()
    log.info("거점 공원 (면적 ≥ %d): %d개", min_area, len(big))
    return pd.DataFrame({
        'name': big['공원명'].values,
        'gu':   big['지역'].values,
        'lat':  big['Y좌표(WGS84)'].values,
        'lon':  big['X좌표(WGS84)'].values,
        'anchor_type': '거점 공원',
    })


def load_terminals():
    rows = [{'name': n, 'gu': g, 'lat': la, 'lon': lo, 'anchor_type': '장거리 터미널·역'}
            for n, g, la, lo in TERMINALS]
    log.info("장거리 터미널·역: %d개", len(rows))
    return pd.DataFrame(rows)


def load_iconic():
    rows = [{'name': n, 'gu': g, 'lat': la, 'lon': lo, 'anchor_type': '노인 명소'}
            for n, g, la, lo in ICONIC]
    log.info("노인 명소: %d개", len(rows))
    return pd.DataFrame(rows)


def load_top_transit_hubs(top=10):
    """노인 도착 TOP 환승역 — elderly trip goff_sttn 기준"""
    con = duckdb.connect(str(DB), read_only=True)
    hubs = con.sql(f"""
    SELECT s.sttn_nm as name, s.lat, s.lon, s.kind,
           COUNT(*) as elder_alights
    FROM elderly_card_trips t JOIN sttn_coords s ON t.goff_sttn_id = s.sttn_id
    WHERE s.kind = 'subway' AND s.lat IS NOT NULL
    GROUP BY s.sttn_nm, s.lat, s.lon, s.kind
    ORDER BY elder_alights DESC LIMIT {top}
    """).df()
    con.close()
    rows = [{'name': r['name'], 'gu': '',
             'lat': float(r['lat']), 'lon': float(r['lon']),
             'anchor_type': '환승 거점역'}
            for _, r in hubs.iterrows()]
    log.info("환승 거점역 TOP %d: %s", top, [r['name'] for r in rows[:5]])
    return pd.DataFrame(rows)


def load_emergency_hospitals():
    """LEE 응급/상급 의료기관 75개 — 거점에 추가"""
    em_data = json.load(open(DATA / 'emergency_access.json'))
    rows = [{'name': h['name'], 'gu': '',
             'lat': h['lat'], 'lon': h['lng'],
             'anchor_type': '응급·상급병원'}
            for h in em_data['emergency']]
    log.info("응급·상급병원: %d개", len(rows))
    return pd.DataFrame(rows)


def main():
    parts = [
        load_anchor_markets(),
        load_welfare_centers(),
        load_anchor_parks(),
        load_terminals(),
        load_iconic(),
        load_top_transit_hubs(),
        load_emergency_hospitals(),
    ]
    anchors = pd.concat(parts, ignore_index=True).dropna(subset=['lat','lon'])
    log.info("=== 총 거점 %d개 ===", len(anchors))
    log.info(anchors['anchor_type'].value_counts().to_dict())

    # 정류장 + 노인 alight 빈도
    log.info("정류장 + 노인 goff 빈도 로드")
    con = duckdb.connect(str(DB), read_only=True)
    sttn = con.sql("""
    WITH g AS (
      SELECT goff_sttn_id as sttn_id, COUNT(*) as elder_alights
      FROM elderly_card_trips WHERE goff_sttn_id IS NOT NULL
      GROUP BY goff_sttn_id
    )
    SELECT s.sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd,
           COALESCE(g.elder_alights, 0) as elder_alights
    FROM sttn_coords s LEFT JOIN g USING(sttn_id)
    WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL
    """).df()
    con.close()

    sttn_pts = np.radians(sttn[['lat','lon']].values)
    tree = BallTree(sttn_pts, metric='haversine')
    a_pts = np.radians(anchors[['lat','lon']].values)
    d_near, i_near = tree.query(a_pts, k=1)
    r300 = 300.0 / EARTH_R
    nearby_idx = tree.query_radius(a_pts, r=r300)

    rows = []
    for k, (_, a) in enumerate(anchors.iterrows()):
        i = int(i_near[k][0])
        nearby = nearby_idx[k]
        rows.append({
            'name': a['name'], 'gu': a['gu'],
            'lat': float(a['lat']), 'lon': float(a['lon']),
            'anchor_type': a['anchor_type'],
            'nearest_stn': sttn.iloc[i]['sttn_nm'],
            'nearest_stn_kind': sttn.iloc[i]['kind'],
            'nearest_stn_dist_m': int(round(float(d_near[k][0]) * EARTH_R)),
            'nearby_stations_300m': int(len(nearby)),
            'elder_alights_300m': int(sttn.iloc[nearby]['elder_alights'].sum()) if len(nearby) else 0,
        })

    out_df = pd.DataFrame(rows).sort_values('elder_alights_300m', ascending=False)

    # 타입별 색상 코드
    type_colors = {
        '거점 시장':       '#7cd982',
        '노인복지관':      '#b48ef4',
        '거점 공원':       '#3ecfa0',
        '장거리 터미널·역': '#5aadff',
        '노인 명소':       '#f5b740',
        '환승 거점역':     '#ff5f5f',
        '응급·상급병원':    '#f472b6',
    }

    out = {
        'anchors': out_df.to_dict('records'),
        'top20_traffic': out_df.head(20).to_dict('records'),
        'type_counts': out_df['anchor_type'].value_counts().to_dict(),
        'type_colors': type_colors,
        'summary': {
            'n_total': int(len(out_df)),
            'avg_dist_m': int(out_df['nearest_stn_dist_m'].mean()),
            'total_elder_alights_300m': int(out_df['elder_alights_300m'].sum()),
        }
    }
    with open(DATA / 'anchor_access.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    log.info("저장: data/anchor_access.json (%d 거점)", len(out_df))

    log.info("\n=== TOP 20 노인 도착 ===")
    for r in out['top20_traffic']:
        log.info("  %5d명 — %s [%s] (%s)", r['elder_alights_300m'], r['name'], r['anchor_type'], r['gu'])


if __name__ == "__main__":
    main()
