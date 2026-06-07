"""
05_anchor_destinations.py — 거점 시설 도달 데이터 가공

SHIM 시장 195개 + YANG 노인복지관에서 "거점급" 추출:
  - 거점 시장: 점포 ≥100개 또는 유명 시장 키워드 (가락·남대문·동대문·경동·노량진)
  - 거점 복지관: 유형이 "노인복지관" (경로당 제외)

각 거점 → 가장 가까운 정류장 + 노인 trip OD 흐름 (해당 거점에 도착한 노인 수)
출력: data/anchor_access.json
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
WELFARE_CSV = ROOT.parent.parent / "Bokji" / "서울시 사회복지시설(노인여가복지시설) 목록.csv"

EARTH_R = 6371000


def load_anchor_markets():
    mkts = json.load(open(DATA / 'shim_mkt.json'))
    df = pd.DataFrame(mkts)
    # 거점 시장 = 점포 ≥80 OR 유명 키워드
    keywords = ['가락', '남대문', '동대문', '경동', '노량진', '광장', '청량리', '신촌', '망원', '암사']
    is_famous = df['name'].apply(lambda n: any(k in n for k in keywords))
    is_big = df['stores'] >= 80
    anchor = df[is_famous | is_big].copy()
    anchor['anchor_type'] = '거점 시장'
    log.info("거점 시장: %d개 (큰시장 %d + 유명 %d)", len(anchor), is_big.sum(), is_famous.sum())
    return anchor[['name','gu','lat','lng','stores','anchor_type']].rename(
        columns={'lng':'lon'})


def load_welfare_centers():
    """YANG의 raw CSV에서 '노인복지관' 만 추출. 좌표 없으면 주소 → Nominatim은 시간 들어서 SKIP.
       대신 YANG의 cache geocode_cache.json 활용."""
    cache_path = ROOT.parent.parent / "Bokji" / "output" / "geocode_cache.json"
    geo_cache = {}
    if cache_path.exists():
        geo_cache = json.load(open(cache_path))
        log.info("YANG geocode cache: %d주소", len(geo_cache))

    df = pd.read_csv(WELFARE_CSV, encoding='cp949')
    log.info("복지시설 raw: %d행", len(df))
    log.info("  유형 분포: %s", df['시설종류명(시설유형)'].value_counts().to_dict())

    # 노인복지관만 (소규모 제외)
    centers = df[df['시설종류명(시설유형)'] == '(노인복지시설) 노인복지관'].copy()
    log.info("  노인복지관: %d개", len(centers))

    # 좌표 매칭
    rows = []
    for _, r in centers.iterrows():
        addr = r.get('시설주소','')
        coord = geo_cache.get(addr)
        if coord and 'lat' in coord and 'lng' in coord:
            rows.append({
                'name': r['시설명'],
                'gu':   r['시군구명'],
                'lat':  coord['lat'],
                'lon':  coord['lng'],
                'anchor_type': '노인복지관',
            })
    log.info("  좌표 있음: %d / %d", len(rows), len(centers))
    return pd.DataFrame(rows)


def main():
    log.info("=== 거점 시장 ===")
    mkts = load_anchor_markets()

    log.info("=== 노인복지관 ===")
    centers = load_welfare_centers()

    # 노인복지관 좌표 매칭이 부족하면 Bokji output_v3 dashboard에서 재추출 시도
    if len(centers) < 30:
        log.warning("복지관 좌표 부족(%d). YANG dashboard에서 추출 시도", len(centers))
        bokji_html = ROOT.parent.parent / "Bokji" / "output_v3" / "infra_dashboard_bokji.html"
        if bokji_html.exists():
            with open(bokji_html) as f:
                txt = f.read()
            # WELFARE_LOC 또는 비슷한 변수 찾기
            import re
            m = re.search(r'const\s+WELFARE\w*\s*=\s*(\[.*?\])', txt, re.DOTALL)
            if m:
                try:
                    arr = json.loads(m.group(1))
                    rows = [{'name': x.get('name','복지관'),
                             'gu': x.get('gu',''),
                             'lat': x.get('lat'),
                             'lon': x.get('lng', x.get('lon')),
                             'anchor_type':'노인복지관'} for x in arr if x.get('lat')]
                    centers = pd.DataFrame(rows)
                    log.info("  YANG dashboard에서 %d개 추출", len(centers))
                except Exception as e:
                    log.warning("  파싱 실패: %s", e)

    anchors = pd.concat([mkts, centers], ignore_index=True)
    anchors = anchors.dropna(subset=['lat','lon'])
    log.info("총 거점 %d개 (시장 %d + 복지관 %d)",
             len(anchors), (anchors['anchor_type']=='거점 시장').sum(),
             (anchors['anchor_type']=='노인복지관').sum())

    # 정류장 + 노인 OD goff 빈도
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
    log.info("  정류장 %d개", len(sttn))

    # 각 거점 → 가장 가까운 정류장 + 100m 내 정류장 노인 alight 합계
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
        elder_arrived = int(sttn.iloc[nearby]['elder_alights'].sum()) if len(nearby) else 0
        rows.append({
            'name': a['name'],
            'gu':   a['gu'],
            'lat':  float(a['lat']),
            'lon':  float(a['lon']),
            'anchor_type': a['anchor_type'],
            'nearest_stn': sttn.iloc[i]['sttn_nm'],
            'nearest_stn_kind': sttn.iloc[i]['kind'],
            'nearest_stn_dist_m': int(round(float(d_near[k][0]) * EARTH_R)),
            'nearby_stations_300m': int(len(nearby)),
            'elder_alights_300m': elder_arrived,
        })

    anchor_out = pd.DataFrame(rows).sort_values('elder_alights_300m', ascending=False)

    out = {
        'anchors': anchor_out.to_dict('records'),
        'top10_traffic': anchor_out.head(10).to_dict('records'),
        'summary': {
            'n_anchor_markets':   int((anchor_out['anchor_type']=='거점 시장').sum()),
            'n_welfare_centers':  int((anchor_out['anchor_type']=='노인복지관').sum()),
            'avg_dist_m':         int(anchor_out['nearest_stn_dist_m'].mean()),
            'total_elder_alights_300m': int(anchor_out['elder_alights_300m'].sum()),
        }
    }
    with open(DATA / 'anchor_access.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    log.info("저장: data/anchor_access.json")

    log.info("\n=== 노인 도착 TOP 10 거점 ===")
    for r in out['top10_traffic']:
        log.info("  %4d명 — %s [%s] (%s · 정류장 %dm)",
                 r['elder_alights_300m'], r['name'], r['anchor_type'], r['gu'],
                 r['nearest_stn_dist_m'])


if __name__ == "__main__":
    main()
