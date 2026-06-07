"""
03_emergency_hospital.py — 응급의료기관 + 종합병원 도달 데이터 가공

LEE 병원 CSV에서:
  - 권역응급의료센터 7개
  - 지역응급의료센터 24개
  - 지역응급의료기관 21개
  - 응급실운영신고기관 23개
  - 종합병원 (응급실 없는) 나머지

각 응급실에 대해:
  - 가장 가까운 정류장 (sttn_coords) 매칭
  - 그 정류장의 평균 환승 시간 (monthly_transfer_accessibility)
  - 결과 emergency_access.json
"""
import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import duckdb

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB   = ROOT.parent / "data" / "seoul.duckdb"
HOSP_CSV = ROOT.parent.parent / "medical_LEE" / "data" / "서울시 병의원 위치 정보.csv"


def main():
    log.info("LEE 병원 CSV 로드: %s", HOSP_CSV)
    df = pd.read_csv(HOSP_CSV, encoding='cp949')
    log.info("  전체 %d행", len(df))

    # 응급의료기관 + 종합병원 추출
    em_codes = ['권역응급의료센터', '지역응급의료센터', '지역응급의료기관', '응급실운영신고기관']
    em = df[df['응급의료기관코드명'].isin(em_codes)].copy()
    gen = df[(df['병원분류명'] == '종합병원') & (~df['응급의료기관코드명'].isin(em_codes))].copy()

    log.info("  응급의료기관: %d (권역 %d / 지역센터 %d / 지역기관 %d / 신고 %d)",
             len(em),
             (em['응급의료기관코드명']=='권역응급의료센터').sum(),
             (em['응급의료기관코드명']=='지역응급의료센터').sum(),
             (em['응급의료기관코드명']=='지역응급의료기관').sum(),
             (em['응급의료기관코드명']=='응급실운영신고기관').sum())
    log.info("  응급실 없는 종합병원: %d", len(gen))

    # 좌표 정리
    em = em.dropna(subset=['병원위도', '병원경도'])
    em = em[(em['병원경도'] > 120) & (em['병원위도'] > 35)]
    gen = gen.dropna(subset=['병원위도', '병원경도'])
    gen = gen[(gen['병원경도'] > 120) & (gen['병원위도'] > 35)]

    # 정류장 좌표 + 환승 시간 로드 (DuckDB)
    log.info("정류장 + 환승 시간 로드 (DuckDB)")
    con = duckdb.connect(str(DB), read_only=True)
    sttn_xfer = con.sql("""
    SELECT s.sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd,
           SUM(t.trnf_hr) * 1.0 / NULLIF(SUM(t.pasg_cnt), 0) as avg_xfer_sec,
           SUM(t.pasg_cnt) as total_pax
    FROM sttn_coords s
    LEFT JOIN monthly_transfer_accessibility t USING(sttn_id)
    GROUP BY s.sttn_id, s.sttn_nm, s.kind, s.lat, s.lon, s.sgg_cd
    """).df()
    con.close()
    sttn_xfer = sttn_xfer.dropna(subset=['lat', 'lon']).reset_index(drop=True)
    log.info("  정류장 %d개 (좌표 있음), 환승 데이터 %d개", len(sttn_xfer), sttn_xfer['avg_xfer_sec'].notna().sum())

    # 각 병원에 가장 가까운 정류장 매칭 (haversine)
    EARTH_R = 6371000

    def haversine_m(lat1, lon1, lat2, lon2):
        rad = np.radians
        dphi = rad(lat2 - lat1)
        dlam = rad(lon2 - lon1)
        a = (np.sin(dphi/2)**2
             + np.cos(rad(lat1)) * np.cos(rad(lat2)) * np.sin(dlam/2)**2)
        return 2 * EARTH_R * np.arcsin(np.sqrt(a))

    sttn_lat = sttn_xfer['lat'].values
    sttn_lon = sttn_xfer['lon'].values

    def match_nearest(hosp_df):
        rows = []
        for _, h in hosp_df.iterrows():
            d = haversine_m(h['병원위도'], h['병원경도'], sttn_lat, sttn_lon)
            i = int(np.argmin(d))
            best = sttn_xfer.iloc[i]
            rows.append({
                'name': h['기관명'],
                'kind': h['응급의료기관코드명'] if pd.notna(h['응급의료기관코드명']) else '종합병원',
                'lat': float(h['병원위도']),
                'lng': float(h['병원경도']),
                'walk_to_stn_m': round(float(d[i])),
                'nearest_stn': best['sttn_nm'],
                'nearest_stn_kind': best['kind'],
                'nearest_stn_lat': float(best['lat']),
                'nearest_stn_lng': float(best['lon']),
                'avg_xfer_sec': float(best['avg_xfer_sec']) if pd.notna(best['avg_xfer_sec']) else None,
            })
        return rows

    em_rows = match_nearest(em)
    gen_rows = match_nearest(gen)
    log.info("매칭 완료 — 응급 %d / 종합 %d", len(em_rows), len(gen_rows))

    # 자치구별 응급실 도달 부담 점수 (구 내 응급실 평균 환승시간)
    em_df = pd.DataFrame(em_rows)
    em_df['walk_min'] = em_df['walk_to_stn_m'] / 0.88 / 60  # 노인 보행 분
    em_df['xfer_min'] = em_df['avg_xfer_sec'].fillna(em_df['avg_xfer_sec'].median()) / 60
    em_df['burden_min'] = em_df['walk_min'] + em_df['xfer_min']

    # 출력
    out = {
        'emergency': em_rows,
        'general':   gen_rows,
        'summary': {
            'n_emergency': len(em_rows),
            'n_general':   len(gen_rows),
            'avg_walk_to_stn_m': round(em_df['walk_to_stn_m'].mean()),
            'avg_xfer_sec':      round(em_df['avg_xfer_sec'].mean()),
            'top10_burden':      em_df.nlargest(10, 'burden_min')[
                ['name','kind','burden_min','walk_min','xfer_min']
            ].round(1).to_dict('records'),
        }
    }
    with open(DATA / 'emergency_access.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log.info("저장: data/emergency_access.json")

    log.info("\n=== TOP10 응급실 환승 부담 (분) ===")
    for r in out['summary']['top10_burden']:
        log.info("  %5.1f분 (보행 %4.1f + 환승 %4.1f) — %s [%s]",
                 r['burden_min'], r['walk_min'], r['xfer_min'], r['name'], r['kind'])


if __name__ == "__main__":
    main()
