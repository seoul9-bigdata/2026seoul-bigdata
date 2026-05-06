"""
02_constellation_data.py — 탭 1 (환승 별자리) 데이터 가공

노인 자주 이용 TOP 정류장 + 환승 시간 + 주변 정류장 매핑
출력: data/constellation.json

별자리 의미:
  - 별 = 정류장 (16K 중 노인 trip 5+ 또는 환승 데이터 있는 것)
  - 별 크기 = 노인 ride 빈도
  - 별 색 = 환승 시간 (짧음 → 청록 / 길음 → 적색)
  - 별자리 선 = 노선 시퀀스 (route_station)
"""
import json
import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB   = ROOT.parent / "data" / "seoul.duckdb"


def main():
    log.info("DuckDB 연결")
    con = duckdb.connect(str(DB), read_only=True)

    # 정류장 + 노인 ride/goff + 환승시간 + 시간대별 분포
    log.info("정류장 마스터 빌드")
    stations = con.sql("""
    WITH ride AS (
      SELECT ride_sttn_id as sttn_id,
             COUNT(*) as elder_rides,
             SUM(CASE WHEN trnf_cnt > 0 THEN 1 ELSE 0 END) as elder_xfer_rides
      FROM elderly_card_trips
      WHERE ride_sttn_id IS NOT NULL
      GROUP BY ride_sttn_id
    ),
    xfer AS (
      SELECT sttn_id,
             SUM(trnf_hr) * 1.0 / NULLIF(SUM(pasg_cnt), 0) as avg_xfer_sec,
             SUM(pasg_cnt) as total_pax
      FROM monthly_transfer_accessibility
      GROUP BY sttn_id
    )
    SELECT s.sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd,
           COALESCE(r.elder_rides, 0) as elder_rides,
           COALESCE(r.elder_xfer_rides, 0) as elder_xfer,
           x.avg_xfer_sec, COALESCE(x.total_pax, 0) as total_pax
    FROM sttn_coords s
    LEFT JOIN ride r USING(sttn_id)
    LEFT JOIN xfer x USING(sttn_id)
    WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL
    """).df()
    log.info("  전체 정류장 %d", len(stations))

    # 별 후보: 노인 ride ≥ 5 OR 환승 데이터 있음
    bright = stations[(stations['elder_rides'] >= 5) | (stations['avg_xfer_sec'].notna())].copy()
    log.info("  별자리 후보 정류장 %d", len(bright))

    # 시간대별 환승 시간 (24x)
    log.info("시간대별 환승 시간")
    by_hour = con.sql("""
    SELECT tzon,
           SUM(trnf_hr)*1.0/NULLIF(SUM(pasg_cnt),0) as avg_sec,
           SUM(pasg_cnt) as pax
    FROM monthly_transfer_accessibility
    GROUP BY tzon ORDER BY tzon
    """).df()

    # 노인 시간대별 ride
    elder_hour = con.sql("""
    SELECT SUBSTRING(ride_dt, 9, 2) as hour, COUNT(*) as n
    FROM elderly_card_trips GROUP BY hour ORDER BY hour
    """).df()

    # 자치구별 환승 부담 (전체 정류장 평균)
    by_gu = con.sql("""
    SELECT sgg_cd,
           SUM(pasg_cnt) as total_pax,
           SUM(trnf_hr)*1.0/SUM(pasg_cnt) as avg_sec
    FROM monthly_transfer_accessibility
    WHERE sgg_cd IS NOT NULL AND ctpv_cd='11'
    GROUP BY sgg_cd
    """).df()

    # TOP 노선별 노인 trip
    top_routes = con.sql("""
    SELECT t.rte_id, br.rte_nm, COUNT(*) as n_trips
    FROM elderly_card_trips t LEFT JOIN bus_route br USING(rte_id)
    GROUP BY t.rte_id, br.rte_nm
    ORDER BY n_trips DESC LIMIT 30
    """).df()

    # TOP10 환승 오래 걸리는 정류장 (인원 ≥ 100 필터로 노이즈 제거)
    top_xfer_long = con.sql("""
    SELECT s.sttn_nm, s.kind, s.sgg_cd, s.lat, s.lon,
           SUM(t.pasg_cnt) as pax,
           SUM(t.trnf_hr)*1.0/SUM(t.pasg_cnt) as avg_sec
    FROM monthly_transfer_accessibility t JOIN sttn_coords s USING(sttn_id)
    WHERE t.pasg_cnt > 0 AND s.lat IS NOT NULL
    GROUP BY s.sttn_nm, s.kind, s.sgg_cd, s.lat, s.lon
    HAVING SUM(t.pasg_cnt) >= 100
    ORDER BY avg_sec DESC LIMIT 10
    """).df()

    # 노인 환승 trip OD pair (정류장 단위, TOP 40, 좌표 포함, 같은 정류장 OD 제외)
    od_stations = con.sql("""
    SELECT r.sttn_nm as ride_nm, r.kind as ride_kind, r.lat as ride_lat, r.lon as ride_lon,
           g.sttn_nm as goff_nm, g.kind as goff_kind, g.lat as goff_lat, g.lon as goff_lon,
           COUNT(*) as n
    FROM elderly_card_trips t
    JOIN sttn_coords r ON t.ride_sttn_id = r.sttn_id
    JOIN sttn_coords g ON t.goff_sttn_id = g.sttn_id
    WHERE t.trnf_cnt > 0
      AND r.lat IS NOT NULL AND g.lat IS NOT NULL
      AND r.sttn_id != g.sttn_id
    GROUP BY ride_nm, ride_kind, ride_lat, ride_lon, goff_nm, goff_kind, goff_lat, goff_lon
    ORDER BY n DESC LIMIT 40
    """).df()

    # 환승 종류별 전체 평균 시간 (4종)
    xfer_type_summary = con.sql("""
    SELECT trnf_type_cd as type,
           SUM(pasg_cnt) as pax,
           SUM(trnf_hr)*1.0/SUM(pasg_cnt) as avg_sec
    FROM monthly_transfer_accessibility
    WHERE pasg_cnt > 0
    GROUP BY trnf_type_cd ORDER BY avg_sec
    """).df()

    # 각 정류장의 환승 종류별 분해 (clickable popup용)
    xfer_breakdown = con.sql("""
    SELECT sttn_id, trnf_type_cd as type,
           SUM(pasg_cnt) as pax,
           SUM(trnf_hr)*1.0/SUM(pasg_cnt) as avg_sec
    FROM monthly_transfer_accessibility
    WHERE pasg_cnt > 0
    GROUP BY sttn_id, trnf_type_cd
    """).df()

    # sttn_id별 종류별 dict로 압축 (클라이언트 부하 ↓)
    bd_map = {}
    for _, r in xfer_breakdown.iterrows():
        bd_map.setdefault(r['sttn_id'], {})[r['type']] = {
            'pax': int(r['pax']), 'sec': round(float(r['avg_sec']))
        }
    log.info("정류장 환승 분해 빌드: %d개", len(bd_map))

    # 병원 근처 정류장 (LEE 응급/상급 75개 + 응급실 정류장)
    em_data = json.load(open('/Users/saroro/GitHub/prototype-seoul/YOO/260504_submit/data/emergency_access.json'))
    hosp_pts = [(h['lat'], h['lng'], h['name']) for h in em_data['emergency']]
    hosp_stations = []
    for h_lat, h_lon, h_name in hosp_pts:
        # 가장 가까운 정류장 1개
        for_st = con.sql(f"""
        SELECT sttn_id, sttn_nm, kind, lat, lon,
               (lat-{h_lat})*(lat-{h_lat})*12100 + (lon-{h_lon})*(lon-{h_lon})*8000 as d2
        FROM sttn_coords WHERE lat IS NOT NULL ORDER BY d2 LIMIT 1
        """).df()
        if len(for_st):
            r = for_st.iloc[0]
            if r['sttn_id'] in bd_map:
                hosp_stations.append({
                    'sttn_nm': r['sttn_nm'],
                    'kind': r['kind'],
                    'lat': float(r['lat']),
                    'lon': float(r['lon']),
                    'hospital': h_name,
                    'breakdown': bd_map[r['sttn_id']],
                })
    # 중복 제거 (같은 정류장이 여러 병원 근처에 잡힐 수 있음)
    seen = set()
    hosp_stations_uniq = []
    for h in hosp_stations:
        if h['sttn_nm'] not in seen:
            seen.add(h['sttn_nm'])
            hosp_stations_uniq.append(h)
    # 평균 환승 시간 긴 순 TOP 8
    def avg_t(h):
        bd = h['breakdown']
        tot_pax = sum(v['pax'] for v in bd.values())
        tot_sec = sum(v['pax']*v['sec'] for v in bd.values())
        return tot_sec / tot_pax if tot_pax else 0
    hosp_stations_uniq.sort(key=avg_t, reverse=True)
    hosp_top = hosp_stations_uniq[:8]
    log.info("병원 근접 정류장 TOP 8: %s", [h['sttn_nm'] for h in hosp_top])

    # 자치구 OD 매트릭스 (환승 trip)
    od_gu = con.sql("""
    SELECT r.sgg_cd as ride_sgg, g.sgg_cd as goff_sgg, COUNT(*) as n
    FROM elderly_card_trips t
    JOIN sttn_coords r ON t.ride_sttn_id = r.sttn_id
    JOIN sttn_coords g ON t.goff_sttn_id = g.sttn_id
    WHERE t.trnf_cnt > 0 AND r.sgg_cd IS NOT NULL AND g.sgg_cd IS NOT NULL
    GROUP BY ride_sgg, goff_sgg
    """).df()

    # TOP10 이용객 많은 환승 정류장
    top_xfer_pax = con.sql("""
    SELECT s.sttn_nm, s.kind, s.sgg_cd, s.lat, s.lon,
           SUM(t.pasg_cnt) as pax,
           SUM(t.trnf_hr)*1.0/SUM(t.pasg_cnt) as avg_sec
    FROM monthly_transfer_accessibility t JOIN sttn_coords s USING(sttn_id)
    WHERE s.lat IS NOT NULL
    GROUP BY s.sttn_nm, s.kind, s.sgg_cd, s.lat, s.lon
    ORDER BY pax DESC LIMIT 10
    """).df()

    # 자치구 코드 → 이름 매핑
    gu_map = {
        '11110':'종로구','11140':'중구','11170':'용산구','11200':'성동구','11215':'광진구',
        '11230':'동대문구','11260':'중랑구','11290':'성북구','11305':'강북구','11320':'도봉구',
        '11350':'노원구','11380':'은평구','11410':'서대문구','11440':'마포구','11470':'양천구',
        '11500':'강서구','11530':'구로구','11545':'금천구','11560':'영등포구','11590':'동작구',
        '11620':'관악구','11650':'서초구','11680':'강남구','11710':'송파구','11740':'강동구',
    }

    by_gu['gu_nm'] = by_gu['sgg_cd'].map(gu_map)
    by_gu = by_gu.dropna(subset=['gu_nm'])

    # 자치구 자족 비율 계산
    od_gu['ride_gu'] = od_gu['ride_sgg'].map(gu_map)
    od_gu['goff_gu'] = od_gu['goff_sgg'].map(gu_map)
    od_gu = od_gu.dropna(subset=['ride_gu','goff_gu'])

    gu_self_suff = []
    for gu in sorted(set(od_gu['ride_gu'])):
        sub = od_gu[od_gu['ride_gu'] == gu]
        total = int(sub['n'].sum())
        self_n = int(sub[sub['goff_gu']==gu]['n'].sum())
        # 외부 도착 TOP 3
        outflow = sub[sub['goff_gu']!=gu].sort_values('n', ascending=False).head(3)
        gu_self_suff.append({
            'gu': gu, 'total': total, 'self': self_n,
            'self_pct': round(self_n/total*100, 1) if total else 0,
            'top_destinations': outflow[['goff_gu','n']].to_dict('records'),
        })
    gu_self_suff.sort(key=lambda x: -x['self_pct'])

    con.close()

    out = {
        'stations': bright.fillna({'avg_xfer_sec': 0}).to_dict('records'),
        'by_hour_xfer': by_hour.to_dict('records'),
        'by_hour_elder': elder_hour.to_dict('records'),
        'by_gu': by_gu.sort_values('avg_sec', ascending=False).to_dict('records'),
        'top_routes': top_routes.to_dict('records'),
        'top_xfer_long': top_xfer_long.to_dict('records'),
        'top_xfer_pax':  top_xfer_pax.to_dict('records'),
        'od_stations':   od_stations.to_dict('records'),
        'gu_self_suff':  gu_self_suff,
        'xfer_type_summary': xfer_type_summary.to_dict('records'),
        'xfer_breakdown':    bd_map,
        'hosp_top':          hosp_top,
        'summary': {
            'n_stations_total': int(len(stations)),
            'n_stations_bright': int(len(bright)),
            'avg_xfer_sec': float(stations['avg_xfer_sec'].mean()),
            'avg_elder_rides': float(stations['elder_rides'].mean()),
            'gu_map': gu_map,
        }
    }
    with open(DATA / 'constellation.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    log.info("저장: data/constellation.json (정류장 %d개)", len(bright))


if __name__ == "__main__":
    main()
