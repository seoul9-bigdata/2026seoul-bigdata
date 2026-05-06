"""
04_climate_station.py — 폭염일 정류장 안전 데이터 가공

KIM 더위쉼터 4,107개 + 한파쉼터 1,642개를 정류장에 매칭:
  - 정류장 100m 내 쉼터 유무 (BallTree haversine)
  - 노인 trip 여름철 시간대(12-15시) 이용량
  - 쉼터 없는 정류장 = 사각지대

출력: data/climate_station.json
  - shelter_coverage: 정류장 → 가장 가까운 쉼터 거리
  - blind_spots: 100m 내 쉼터 없으면서 노인 이용 많은 정류장 TOP
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

EARTH_R = 6371000


def main():
    log.info("쉼터 로드")
    heat = json.load(open(DATA / 'heat_shelters.json'))
    cold = json.load(open(DATA / 'cold_shelters.json'))
    log.info("  더위 %d / 한파 %d", len(heat), len(cold))

    log.info("정류장 + 노인 ride 빈도 로드")
    con = duckdb.connect(str(DB), read_only=True)
    sttn = con.sql("""
    WITH ride AS (
      SELECT ride_sttn_id as sttn_id,
             COUNT(*) as elder_rides,
             SUM(CASE WHEN SUBSTRING(ride_dt,9,2) BETWEEN '12' AND '15' THEN 1 ELSE 0 END) as elder_rides_noon
      FROM elderly_card_trips GROUP BY ride_sttn_id
    )
    SELECT s.sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd,
           COALESCE(r.elder_rides, 0) as elder_rides,
           COALESCE(r.elder_rides_noon, 0) as elder_rides_noon
    FROM sttn_coords s LEFT JOIN ride r USING(sttn_id)
    WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL
    """).df()
    con.close()
    log.info("  정류장 %d개", len(sttn))

    # BallTree (radians) — 쉼터
    heat_pts = np.radians([[s['lat'], s['lng']] for s in heat])
    cold_pts = np.radians([[s['lat'], s['lng']] for s in cold])
    sttn_pts = np.radians(sttn[['lat','lon']].values)

    log.info("BallTree 매칭 (haversine)")
    t_heat = BallTree(heat_pts, metric='haversine')
    t_cold = BallTree(cold_pts, metric='haversine')

    # 가장 가까운 쉼터 거리 + 100m 내 쉼터 수
    d_heat, _ = t_heat.query(sttn_pts, k=1)
    d_cold, _ = t_cold.query(sttn_pts, k=1)
    sttn['heat_nearest_m'] = (d_heat.flatten() * EARTH_R).round().astype(int)
    sttn['cold_nearest_m'] = (d_cold.flatten() * EARTH_R).round().astype(int)

    # 100m 반경 내 쉼터 카운트
    r100 = 100.0 / EARTH_R
    sttn['heat_within_100m'] = [len(idx) for idx in t_heat.query_radius(sttn_pts, r=r100)]
    sttn['cold_within_100m'] = [len(idx) for idx in t_cold.query_radius(sttn_pts, r=r100)]

    log.info("=== 통계 ===")
    log.info("  더위쉼터 100m내 정류장: %d / %d (%.1f%%)",
             (sttn['heat_within_100m']>0).sum(), len(sttn),
             (sttn['heat_within_100m']>0).mean()*100)
    log.info("  한파쉼터 100m내 정류장: %d / %d (%.1f%%)",
             (sttn['cold_within_100m']>0).sum(), len(sttn),
             (sttn['cold_within_100m']>0).mean()*100)

    # 사각지대: 100m 내 더위쉼터 없는데 노인 낮시간(12-15) 이용 많은 정류장
    blind = sttn[(sttn['heat_within_100m']==0) & (sttn['elder_rides_noon']>=10)].copy()
    blind = blind.sort_values('elder_rides_noon', ascending=False)
    log.info("폭염 사각지대 정류장 (100m내 쉼터 없음 + 노인 낮시간 이용 ≥10): %d개", len(blind))

    # 자치구별 사각지대 비율
    by_gu = sttn.groupby('sgg_cd').agg(
        n_stations=('sttn_id','count'),
        n_no_heat=('heat_within_100m', lambda s: (s==0).sum()),
        elder_rides=('elder_rides','sum'),
    ).reset_index()
    by_gu['blind_ratio'] = (by_gu['n_no_heat'] / by_gu['n_stations'] * 100).round(1)

    # 출력
    out = {
        'stations': sttn[['sttn_id','sttn_nm','kind','lat','lon','sgg_cd',
                          'heat_nearest_m','cold_nearest_m',
                          'heat_within_100m','cold_within_100m',
                          'elder_rides','elder_rides_noon']].to_dict('records'),
        'blind_spots_top30': blind.head(30)[['sttn_id','sttn_nm','kind','lat','lon',
                                              'sgg_cd','heat_nearest_m','elder_rides_noon']
                                             ].to_dict('records'),
        'by_gu': by_gu.to_dict('records'),
        'summary': {
            'n_stations': int(len(sttn)),
            'n_heat_shelters': len(heat),
            'n_cold_shelters': len(cold),
            'pct_stn_with_heat_100m': round(float((sttn['heat_within_100m']>0).mean()*100), 1),
            'pct_stn_with_cold_100m': round(float((sttn['cold_within_100m']>0).mean()*100), 1),
            'avg_heat_distance_m': int(sttn['heat_nearest_m'].mean()),
            'avg_cold_distance_m': int(sttn['cold_nearest_m'].mean()),
        }
    }
    with open(DATA / 'climate_station.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    log.info("저장: data/climate_station.json")

    log.info("\n=== 폭염 사각지대 TOP 5 ===")
    for r in out['blind_spots_top30'][:5]:
        log.info("  %s [%s] — 가장 가까운 쉼터 %dm, 노인 낮 이용 %d회",
                 r['sttn_nm'], r['kind'], r['heat_nearest_m'], r['elder_rides_noon'])


if __name__ == "__main__":
    main()
