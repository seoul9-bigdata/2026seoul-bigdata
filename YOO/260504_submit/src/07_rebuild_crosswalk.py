"""
07_rebuild_crosswalk.py — 신호 없는 횡단보도 데이터 재생성 (보수 처리)

변경:
  기존: NaN/'-' → N으로 처리 → 신호 없음
  보수: N 명시된 것만 신호 없음. Y/'-'/NaN → 신호 있음 (보수 가정)

영향:
  '-' 8건이 신호 없음 → 신호 있음으로 이동 (오차 0.02%)
  사용자 원칙 적용 — "확실한 N만 신호 없음"

출력: outputs/tab5_crosswalk.html (덮어쓰기)
"""
import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.neighbors import BallTree

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "outputs" / "tab5_crosswalk.html"

CROSSWALK_CSV = ROOT.parent / "서울특별시_자치구_횡단보도_20260320.csv"
TAAS_CSV      = ROOT.parent / "data" / "processed" / "taas_seoul_elderly_pedestrian_2024.csv"

KAKAO_KEY = "4827d1df867dfc08ae1daba2b1d25835"
EARTH_R = 6371000


def load_crosswalk():
    cw = pd.read_csv(CROSSWALK_CSV)
    cw = cw[cw['시도명'] == '서울특별시'].copy()

    # 컬럼 swap (CSV 헤더 오류)
    cw = cw.rename(columns={'경도': 'lat', '위도': 'lon', '시군구명': '구'})
    cw = cw.dropna(subset=['lat', 'lon', '구']).reset_index(drop=True)
    assert 37.0 < cw['lat'].mean() < 38.0
    assert 126.0 < cw['lon'].mean() < 128.0

    # ▶ 보수 처리: 'N' 명시된 것만 False(없음). Y/'-'/NaN → True(있음)
    raw = cw['보행등유무'].fillna('').str.upper().str.strip()
    cw['보행등유무'] = raw != 'N'   # True = 신호 있음(보수)
    cw['신호없음'] = ~cw['보행등유무']  # True = N 명시

    log.info("=== 보수 처리 후 ===")
    log.info("  서울 횡단보도: %d건", len(cw))
    log.info("  신호 있음(보수): %d (%.1f%%)",
             cw['보행등유무'].sum(), cw['보행등유무'].mean()*100)
    log.info("  신호 없음(N확정): %d (%.1f%%)",
             cw['신호없음'].sum(), cw['신호없음'].mean()*100)
    return cw


def load_accidents(cw):
    acc = pd.read_csv(TAAS_CSV)
    acc = acc.dropna(subset=['lat','lon']).reset_index(drop=True)
    log.info("TAAS 노인 보행사고: %d건", len(acc))

    # 사고 ↔ 신호 없음 횡단보도 거리 (BallTree)
    cw_no = cw.loc[cw['신호없음'], ['lat','lon']].values
    cw_no_rad = np.radians(cw_no)
    tree = BallTree(cw_no_rad, metric='haversine')

    acc_pts_rad = np.radians(acc[['lat','lon']].values)
    d, _ = tree.query(acc_pts_rad, k=1)
    acc['최근접_신호없음_m'] = (d.flatten() * EARTH_R).round().astype(int)
    acc['인접_50m']  = acc['최근접_신호없음_m'] <= 50
    acc['인접_100m'] = acc['최근접_신호없음_m'] <= 100

    log.info("  사고 50m 내 신호 없음: %d (%.1f%%)",
             acc['인접_50m'].sum(), acc['인접_50m'].mean()*100)
    log.info("  사고 100m 내 신호 없음: %d (%.1f%%)",
             acc['인접_100m'].sum(), acc['인접_100m'].mean()*100)

    return acc


def filter_cw_near_acc(cw, acc, radius=200):
    """브라우저 부하 줄이기: 사고 200m 내 신호 없는 횡단보도만"""
    acc_pts_rad = np.radians(acc[['lat','lon']].values)
    cw_no = cw.loc[cw['신호없음']].copy()
    cw_no_rad = np.radians(cw_no[['lat','lon']].values)
    tree = BallTree(acc_pts_rad, metric='haversine')
    d, _ = tree.query(cw_no_rad, k=1)
    cw_no['min_acc_dist_m'] = (d.flatten() * EARTH_R).round()
    near = cw_no[cw_no['min_acc_dist_m'] <= radius].copy()
    log.info("  신호 없는 횡단보도 사고 %dm 내: %d / %d (%.1f%%)",
             radius, len(near), len(cw_no), len(near)/len(cw_no)*100)
    return near


def build_html(cw_near, acc):
    cw_records = [
        {"lat": float(r['lat']), "lon": float(r['lon']), "gu": r['구'],
         "음향": int(bool(r.get('음향신호기설치여부') == 'Y')),
         "고원식": int(bool(r.get('고원식횡단보도유무') == 'Y'))}
        for _, r in cw_near.iterrows()
    ]
    acc_records = [
        {"lat": float(r['lat']), "lon": float(r['lon']), "gu": r['legaldong_name'].split()[1] if isinstance(r.get('legaldong_name'),str) and len(r['legaldong_name'].split())>1 else '',
         "acdnt": str(r.get('acdnt_dc','')), "grade": str(r.get('acdnt_gae_dc','')),
         "crosswalk": False}
        for _, r in acc.iterrows()
    ]

    gu_options = ''.join(
        f'<option value="{g}">{g}</option>'
        for g in sorted(set(r['gu'] for r in acc_records if r['gu']))
    )

    html = f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<title>서울 신호 없는 횡단보도 × 노인 보행사고</title>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_KEY}"></script>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
#map{{width:100%;height:100vh}}
#panel{{position:absolute;top:12px;left:12px;background:rgba(255,255,255,0.96);
       padding:14px 16px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,0.18);z-index:10;max-width:300px}}
h3{{margin:0 0 8px 0;font-size:15px}}
select{{width:100%;margin-top:8px;padding:5px;font-size:13px}}
.stat{{font-size:12px;color:#444;margin-top:8px;line-height:1.6}}
.note{{font-size:11px;color:#888;margin-top:6px;line-height:1.5}}
.dot-mk{{
  border-radius:50%;border:1.5px solid rgba(255,255,255,.85);cursor:pointer;
  transform:translate(-50%,-50%);box-shadow:0 1px 4px rgba(0,0,0,.45);
  transition:transform .12s;pointer-events:auto;
}}
.dot-mk:hover{{transform:translate(-50%,-50%) scale(1.5);z-index:50}}
.iw-card{{font-family:-apple-system,sans-serif;font-size:12px;color:#222;
  padding:9px 12px;line-height:1.55;min-width:200px;max-width:300px}}
.iw-card .h{{font-size:13.5px;font-weight:600;margin-bottom:4px;color:#111}}
.iw-card .sub{{font-size:10.5px;color:#888;margin-bottom:6px}}
.iw-card .row{{display:flex;justify-content:space-between;font-size:11px;padding:1.5px 0;color:#444}}
.iw-card .row b{{font-weight:500;color:#111}}
</style>
</head>
<body>
<div id="panel">
  <select id="guSelect"><option value="">전체 자치구</option>{gu_options}</select>
  <div class="stat" id="stat"></div>
  <div class="note">🔴 노인 보행사고 · 🔵 신호 없는 횡단보도 (보행등 = 'N' 명시만). 마커 클릭 → 상세.</div>
</div>
<div id="map"></div>
<script>
const ACC = {json.dumps(acc_records, ensure_ascii=False)};
const CW  = {json.dumps(cw_records, ensure_ascii=False)};

const map = new kakao.maps.Map(document.getElementById("map"), {{
  center: new kakao.maps.LatLng(37.55, 126.99),
  level: 7
}});

let _iw = null;
function openIW(lat,lon,html){{
  if(_iw) _iw.close();
  _iw = new kakao.maps.InfoWindow({{
    position: new kakao.maps.LatLng(lat,lon),
    content: '<div class="iw-card">'+html+'</div>',
    removable: true,
  }});
  _iw.open(map);
}}
function dotOverlay(lat,lon,size,color,onClick,z){{
  const el = document.createElement('div');
  el.className = 'dot-mk';
  el.style.cssText = 'width:'+size+'px;height:'+size+'px;background:'+color+';opacity:.9';
  el.addEventListener('click', e => {{ e.stopPropagation(); onClick(); }});
  return new kakao.maps.CustomOverlay({{
    map, position: new kakao.maps.LatLng(lat,lon),
    content: el, yAnchor:0.5, xAnchor:0.5, clickable:true, zIndex:z||3,
  }});
}}

const accLayer = [];
const cwLayer = [];
function clear(arr){{arr.forEach(m=>m.setMap(null));arr.length=0}}

function draw(filter){{
  clear(accLayer); clear(cwLayer);
  let accCnt=0, cwCnt=0;
  CW.forEach(p=>{{
    if(filter && p.gu!==filter) return;
    cwLayer.push(dotOverlay(p.lat,p.lon,7,'#1f77b4',()=>openIW(p.lat,p.lon,
      '<div class="h">신호 없는 횡단보도</div>'+
      '<div class="sub">'+(p.gu||'')+'</div>'+
      '<div class="row"><span>음향신호기</span><b>'+(p['음향']?'있음':'없음')+'</b></div>'+
      '<div class="row"><span>고원식</span><b>'+(p['고원식']?'있음':'없음')+'</b></div>'),3));
    cwCnt++;
  }});
  ACC.forEach(p=>{{
    if(filter && p.gu!==filter) return;
    accLayer.push(dotOverlay(p.lat,p.lon,9,'#d62728',()=>openIW(p.lat,p.lon,
      '<div class="h">노인 보행사고</div>'+
      '<div class="sub">'+(p.gu||'')+'</div>'+
      '<div class="row"><span>사고 분류</span><b>'+(p.acdnt||'-')+'</b></div>'+
      '<div class="row"><span>중상도</span><b>'+(p.grade||'-')+'</b></div>'),5));
    accCnt++;
  }});
  document.getElementById("stat").textContent =
    `노인 사고 ${{accCnt}}건 · 신호 없는 횡단보도 ${{cwCnt}}개 표시 중`;
}}

document.getElementById("guSelect").addEventListener("change", e=>draw(e.target.value));
draw("");
</script>
</body>
</html>
"""
    OUT.write_text(html, encoding='utf-8')
    log.info("저장: %s (%d KB)", OUT, OUT.stat().st_size//1024)


def main():
    cw = load_crosswalk()
    acc = load_accidents(cw)
    cw_near = filter_cw_near_acc(cw, acc, radius=200)
    build_html(cw_near, acc)


if __name__ == "__main__":
    main()
