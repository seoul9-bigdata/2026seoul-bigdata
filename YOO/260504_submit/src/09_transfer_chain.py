"""
09_transfer_chain.py — 노인 카드 trip chain 재구성으로 환승 from-route → to-route 추적

알고리즘:
  카드별 (vr_card_no) trip을 ride_dt 시간순 정렬 →
  연속 trip의 시간 갭 ≤ 30분 = 환승 (goff_dt → 다음 ride_dt)
  환승 정류장 = 이전 leg의 goff_sttn_id

출력: data/transfer_chain.json
  - station_routes: 정류장별 TOP from-route → to-route pair
  - top_transfers: 글로벌 TOP 환승 from→to (노선 단위)
  - hub_breakdown: 환승 거점역 노선 분포
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
    con = duckdb.connect(str(DB), read_only=True)

    # 1. 노인 trip chain 재구성 — LAG window 사용
    log.info("환승 chain 재구성 (LAG window)...")
    chains = con.sql("""
    WITH ordered AS (
      SELECT vr_card_no, ride_dt, goff_dt, ride_sttn_id, goff_sttn_id, rte_id,
             LAG(goff_dt)       OVER (PARTITION BY vr_card_no ORDER BY ride_dt) as prev_goff_dt,
             LAG(goff_sttn_id)  OVER (PARTITION BY vr_card_no ORDER BY ride_dt) as prev_goff_sttn,
             LAG(rte_id)        OVER (PARTITION BY vr_card_no ORDER BY ride_dt) as prev_rte_id
      FROM elderly_card_trips
      WHERE goff_sttn_id IS NOT NULL
    ),
    transfers AS (
      SELECT prev_goff_sttn as xfer_sttn_id,
             prev_rte_id    as from_rte,
             rte_id         as to_rte,
             vr_card_no
      FROM ordered
      WHERE prev_goff_dt IS NOT NULL
        AND prev_rte_id IS NOT NULL
        AND prev_rte_id != rte_id  -- 같은 노선 재승차 제외
        -- 시간 갭 ≤ 30분 (1800초). VARCHAR 시간 비교가 어려우므로 strptime
        AND date_diff('minute',
              strptime(prev_goff_dt, '%Y%m%d%H%M%S'),
              strptime(ride_dt,      '%Y%m%d%H%M%S')) BETWEEN 0 AND 30
    )
    SELECT * FROM transfers
    """).df()

    log.info("재구성된 환승 이벤트: %d건", len(chains))

    # 2. 정류장 + 노선 정보 조인
    log.info("정류장·노선 메타 조인")
    enriched = con.sql(f"""
    WITH x AS (SELECT * FROM chains)
    SELECT x.xfer_sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd,
           x.from_rte, br_from.rte_nm as from_rte_nm,
           x.to_rte,   br_to.rte_nm   as to_rte_nm
    FROM (SELECT * FROM chains) x
    LEFT JOIN sttn_coords s ON x.xfer_sttn_id = s.sttn_id
    LEFT JOIN bus_route br_from ON x.from_rte = br_from.rte_id
    LEFT JOIN bus_route br_to   ON x.to_rte   = br_to.rte_id
    WHERE s.lat IS NOT NULL
    """).df()
    log.info("좌표 매칭된 환승: %d건", len(enriched))

    # rte_nm fallback — railway_line에서도 lookup
    rl = con.sql("SELECT rte_id, rte_nm FROM railway_line").df()
    rl_map = dict(zip(rl['rte_id'], rl['rte_nm']))
    enriched['from_rte_nm'] = enriched.apply(
        lambda r: r['from_rte_nm'] if r['from_rte_nm'] else rl_map.get(r['from_rte'], r['from_rte']), axis=1)
    enriched['to_rte_nm'] = enriched.apply(
        lambda r: r['to_rte_nm'] if r['to_rte_nm'] else rl_map.get(r['to_rte'], r['to_rte']), axis=1)

    # 3. 글로벌 TOP from→to pair
    log.info("TOP from→to pair 집계")
    global_top = enriched.groupby(['from_rte', 'from_rte_nm', 'to_rte', 'to_rte_nm']).size().reset_index(name='n')
    global_top = global_top.sort_values('n', ascending=False).head(30)

    # 4. 정류장별 TOP from→to pair (TOP 환승역만)
    log.info("정류장별 환승 TOP")
    station_pairs = enriched.groupby(['xfer_sttn_id', 'sttn_nm', 'kind', 'lat', 'lon',
                                       'from_rte_nm', 'to_rte_nm']).size().reset_index(name='n')
    # 정류장 환승 총량
    station_total = enriched.groupby(['xfer_sttn_id', 'sttn_nm', 'kind', 'lat', 'lon']).size().reset_index(name='total')
    station_total = station_total.sort_values('total', ascending=False)
    log.info("환승 발생 정류장 총 %d개 (TOP10: %s)",
             len(station_total),
             station_total.head(10)['sttn_nm'].tolist())

    # 정류장별 TOP 5 from→to pair
    station_top_pairs = (station_pairs.sort_values('n', ascending=False)
                                       .groupby('xfer_sttn_id', sort=False)
                                       .head(5)
                                       .reset_index(drop=True))

    # 5. 환승 거점역 (TOP 50)에 대해 dict 형태로 저장
    top_xfer_stations = station_total.head(50)['xfer_sttn_id'].tolist()
    station_breakdown = {}
    for sid in top_xfer_stations:
        sub = station_pairs[station_pairs['xfer_sttn_id'] == sid].sort_values('n', ascending=False).head(8)
        if len(sub) == 0: continue
        meta = station_total[station_total['xfer_sttn_id'] == sid].iloc[0]
        station_breakdown[sid] = {
            'sttn_nm': meta['sttn_nm'],
            'kind': meta['kind'],
            'lat': float(meta['lat']),
            'lon': float(meta['lon']),
            'total': int(meta['total']),
            'pairs': [{'from': r['from_rte_nm'], 'to': r['to_rte_nm'], 'n': int(r['n'])}
                      for _, r in sub.iterrows()],
        }

    out = {
        'global_top': global_top.to_dict('records'),
        'station_top10': station_total.head(10).to_dict('records'),
        'station_breakdown': station_breakdown,
        'summary': {
            'n_transfer_events': int(len(enriched)),
            'n_xfer_stations':   int(len(station_total)),
            'n_unique_pairs':    int(len(global_top)),  # only top 30 saved, real total bigger
        }
    }

    with open(DATA / 'transfer_chain.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    log.info("저장: data/transfer_chain.json")

    log.info("\n=== 글로벌 TOP10 from-route → to-route ===")
    for r in out['global_top'][:10]:
        log.info("  %4d건 | %s → %s", r['n'], r['from_rte_nm'], r['to_rte_nm'])

    log.info("\n=== 환승 정류장 TOP10 ===")
    for r in out['station_top10']:
        log.info("  %4d건 | %s [%s]", r['total'], r['sttn_nm'], r['kind'])

    con.close()


if __name__ == "__main__":
    main()
