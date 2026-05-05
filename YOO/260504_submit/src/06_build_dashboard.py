"""
06_build_dashboard.py — 5탭 통합 대시보드 HTML 생성

탭 구조:
  1) 환승 별자리      — constellation.json
  2) 응급실 30분      — emergency_access.json
  3) 폭염 정류장      — climate_station.json + heat_shelters.json
  4) 거점 시설        — anchor_access.json
  5) 횡단보도 안전    — tab5_crosswalk.html iframe

디자인: SHIM 별자리지도 톤. Python에서 SVG·리스트 미리 생성 (innerHTML 사용 회피).
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT  = ROOT / "outputs" / "transit_dashboard.html"

KAKAO_KEY = "4827d1df867dfc08ae1daba2b1d25835"


def esc(s):
    """HTML escape — 정류장/병원명 안전 처리"""
    if s is None: return ''
    return (str(s).replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('"','&quot;'))


def short_kind(k):
    return (k.replace('응급의료','').replace('센터','C')
            .replace('기관','I').replace('운영신고','신고'))


import re as _re


def short_hosp(name):
    """병원명 정규화 — 법인 wrapper 제거 + '대학교 ' 띄어쓰기"""
    s = name
    # 학교법인OO학원 / 재단법인OO재단 / 의료법인OO재단 등 wrapper 제거
    s = _re.sub(r'^(학교법인|재단법인|의료법인|사회복지법인|사단법인|특수법인)[가-힣]*?(학원|재단|법인)(?=[가-힣])', '', s)
    # 단독 leading 의료법인/재단법인 제거
    s = _re.sub(r'^(의료법인|재단법인|학교법인)(?=[가-힣])', '', s)
    # 의과대학부속 / 부속 → 공백
    s = s.replace('의과대학부속', ' ').replace('의대부속', ' ')
    s = _re.sub(r'(?<=대학교)부속(?=[가-힣])', ' ', s)
    # 대학교 뒤 한글 (병원이 아니면) 공백 삽입
    s = _re.sub(r'대학교(?=[가-힣])(?!병원|의과대학)', '대학교 ', s)
    s = _re.sub(r'\s+', ' ', s).strip()
    return s or name


def build_clock_svg(by_hour_xfer):
    """시간대별 환승시간 시계 SVG"""
    W, H, cx, cy, R = 320, 180, 160, 120, 80
    sec_list = [d['avg_sec'] for d in by_hour_xfer]
    minS, maxS = min(sec_list), max(sec_list)
    parts = ['<defs><radialGradient id="g1" cx="50%" cy="60%" r="60%">'
             '<stop offset="0%" stop-color="#1a3060" stop-opacity=".3"/>'
             '<stop offset="100%" stop-color="#040810" stop-opacity="0"/></radialGradient></defs>',
             f'<ellipse cx="{cx}" cy="{cy}" rx="{R+20}" ry="{R+15}" fill="url(#g1)"/>']
    for d in by_hour_xfer:
        h = int(d['tzon'])
        ang = (h - 6) / 24 * 2 * math.pi
        ratio = (d['avg_sec'] - minS) / (maxS - minS) if maxS > minS else 0
        r1, r2 = R - 12, R + 8 + ratio * 25
        c = '#ff5f5f' if ratio > 0.7 else '#f5b740' if ratio > 0.4 else '#3ecfa0'
        x1, y1 = cx + math.cos(ang) * r1, cy + math.sin(ang) * r1
        x2, y2 = cx + math.cos(ang) * r2, cy + math.sin(ang) * r2
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="3" opacity="0.85"/>')
        if h % 6 == 0:
            tx, ty = cx + math.cos(ang) * (R+38), cy + math.sin(ang) * (R+38)
            parts.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="central" '
                         f'font-family="IBM Plex Mono" font-size="10" fill="#888680">{h:02d}시</text>')
    avg_min = sum(sec_list) / len(sec_list) / 60
    parts.append(f'<text x="{cx}" y="{cy-3}" text-anchor="middle" font-family="Noto Serif KR" font-size="11" fill="#bfbdb8">평균</text>')
    parts.append(f'<text x="{cx}" y="{cy+14}" text-anchor="middle" font-family="IBM Plex Mono" font-size="14" fill="#f5b740">{avg_min:.1f}분</text>')
    return f'<svg id="clock1" viewBox="0 0 {W} {H}" style="width:100%;height:180px">' + ''.join(parts) + '</svg>'


def build_od_list(od_arr, top=15):
    """환승 OD pair 리스트 — 출발 클릭 시 출발 정류장으로 이동"""
    items = []
    for r in od_arr[:top]:
        items.append(
            f'<li class="clickable" data-tab="1" data-lat="{r["ride_lat"]}" data-lon="{r["ride_lon"]}" '
            f'data-name="{esc(r["ride_nm"])}">'
            f'<span class="rank-name">{esc(r["ride_nm"])} → {esc(r["goff_nm"])}</span>'
            f'<span class="rank-val">{r["n"]}건</span></li>')
    return ''.join(items)


def build_self_suff_bars(gu_self_suff):
    """자치구 자족 비율 바 — 내림차순"""
    arr = sorted(gu_self_suff, key=lambda g: -g['self_pct'])
    rows = []
    for g in arr:
        w = g['self_pct']
        # 색: 자족 높음=teal, 낮음=red
        c = '#3ecfa0' if w > 75 else '#5aadff' if w > 65 else '#f5b740' if w > 55 else '#ff5f5f'
        rows.append(
            f'<div class="bar-row"><div class="bar-name">{esc(g["gu"])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{w:.0f}%;background:{c}"></div></div>'
            f'<div class="bar-num">{w:.0f}%</div></div>')
    return ''.join(rows)


TYPE_LABEL = {'BB':'🚌→🚌', 'BT':'🚌→🚇', 'TB':'🚇→🚌', 'TT':'🚇→🚇'}


def dominant_type(breakdown):
    """가장 인원 많은 환승 종류"""
    if not breakdown: return ''
    t = max(breakdown.items(), key=lambda x: x[1]['pax'])
    return t[0]


def build_station_rank_list(arr, key, fmt, suffix='명', tab=1, breakdown=None):
    """정류장 TOP 리스트 — key='avg_sec' or 'pax', 클릭 가능, dominant_type 마크"""
    items = []
    for r in arr:
        val = fmt(r[key])
        sub = ''
        if key == 'avg_sec':
            sub = f"{int(r['pax']):,}명"
        elif key == 'pax':
            sub = f"{r['avg_sec']/60:.1f}분"
        # dominant 환승 종류 — sttn_nm으로 lookup (sttn_id 없음)
        dom_str = ''
        if breakdown is not None:
            for sid, bd in breakdown.items():
                pass  # not directly mappable here, handled differently
        items.append(
            f'<li class="clickable" data-tab="{tab}" data-lat="{r["lat"]}" data-lon="{r["lon"]}" '
            f'data-name="{esc(r["sttn_nm"])}">'
            f'<span class="rank-name">{esc(r["sttn_nm"])} '
            f'<span style="color:var(--text4);font-size:9.5px">[{esc(r["kind"])}] {sub}</span></span>'
            f'<span class="rank-val">{val}</span></li>')
    return ''.join(items)


def build_xfer_type_bars(summary):
    """A안: 환승 종류 4종 평균 시간 막대 SVG"""
    # I/O 합쳐서 평균
    by_type = {}
    for r in summary:
        t = r['type']
        by_type.setdefault(t, {'pax': 0, 'sec_x_pax': 0})
        by_type[t]['pax'] += r['pax']
        by_type[t]['sec_x_pax'] += r['avg_sec'] * r['pax']
    rows = []
    for t in ['TT','BT','BB','TB']:
        d = by_type.get(t, {'pax':0, 'sec_x_pax':0})
        avg = d['sec_x_pax'] / d['pax'] if d['pax'] else 0
        rows.append({'type': t, 'avg_min': avg/60, 'pax': d['pax']})
    max_min = max(r['avg_min'] for r in rows)
    out = []
    colors = {'TT':'#3ecfa0', 'BT':'#5aadff', 'BB':'#f5b740', 'TB':'#ff5f5f'}
    for r in rows:
        w = (r['avg_min'] / max_min) * 100
        out.append(
            f'<div class="bar-row"><div class="bar-name">{TYPE_LABEL[r["type"]]}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{w:.0f}%;background:{colors[r["type"]]}"></div></div>'
            f'<div class="bar-num">{r["avg_min"]:.1f}분</div></div>')
    return ''.join(out)


def build_hospital_chart(hosp_top):
    """C안: 병원 정류장 TOP8 환승 종류 분해 — 누적 막대 SVG"""
    W = 320
    bar_h = 22
    H = len(hosp_top) * (bar_h + 4) + 30
    cx_label = 100  # label 영역 너비
    cx_bar = 200   # bar 영역 너비
    cx_total = cx_label + cx_bar + 18

    parts = []
    colors = {'TT':'#3ecfa0', 'BT':'#5aadff', 'BB':'#f5b740', 'TB':'#ff5f5f'}
    # 최대값 = 가장 긴 정류장의 최대 분
    max_min = 1
    for h in hosp_top:
        for typ, d in h['breakdown'].items():
            if d['sec'] / 60 > max_min:
                max_min = d['sec'] / 60
    # 헤더
    parts.append(f'<text x="0" y="11" font-family="IBM Plex Mono" font-size="10" fill="#888680">병원 정류장</text>')
    parts.append(f'<text x="{cx_label+5}" y="11" font-family="IBM Plex Mono" font-size="10" fill="#888680">환승 종류 평균 (분)</text>')
    # 각 정류장 행 — 4 type 그룹 막대
    for i, h in enumerate(hosp_top):
        y = 26 + i * (bar_h + 4)
        nm = h['sttn_nm'][:11] + ('…' if len(h['sttn_nm'])>11 else '')
        parts.append(f'<text x="0" y="{y+13}" font-family="Noto Sans KR" font-size="10.5" fill="#bfbdb8">{esc(nm)}</text>')
        # 4 type 막대 가로로 작게 그리기
        sub_h = bar_h / 4
        for j, typ in enumerate(['TT','BT','BB','TB']):
            d = h['breakdown'].get(typ)
            yy = y + j * sub_h
            if d:
                w = (d['sec'] / 60 / max_min) * cx_bar
                parts.append(f'<rect x="{cx_label}" y="{yy}" width="{w:.1f}" height="{sub_h-1}" fill="{colors[typ]}" opacity="0.85"/>')
                if w > 35:
                    parts.append(f'<text x="{cx_label+w-3}" y="{yy+sub_h-2}" text-anchor="end" font-family="IBM Plex Mono" font-size="8.5" fill="#070910">{d["sec"]/60:.0f}분</text>')
    # 범례 아래
    leg_y = H - 6
    leg_x = 0
    legend_parts = []
    for typ in ['TT','BT','BB','TB']:
        legend_parts.append(f'<rect x="{leg_x}" y="{leg_y-7}" width="9" height="9" fill="{colors[typ]}"/>'
                            f'<text x="{leg_x+13}" y="{leg_y}" font-family="IBM Plex Mono" font-size="9.5" fill="#888680">{TYPE_LABEL[typ]}</text>')
        leg_x += 80
    return f'<svg viewBox="0 0 {cx_total} {H+16}" style="width:100%;height:auto">' + ''.join(parts) + ''.join(legend_parts) + '</svg>'


def build_gu_bars(by_gu, top=10):
    arr = sorted(by_gu, key=lambda g: -g['avg_sec'])[:top]
    maxS = max(g['avg_sec'] for g in arr)
    minS = min(g['avg_sec'] for g in arr)
    rows = []
    for g in arr:
        w = ((g['avg_sec'] - minS*0.92) / (maxS - minS*0.92) * 100) if maxS > minS else 50
        rows.append(f'<div class="bar-row"><div class="bar-name">{esc(g["gu_nm"])}</div>'
                    f'<div class="bar-track"><div class="bar-fill" style="width:{w:.0f}%"></div></div>'
                    f'<div class="bar-num">{g["avg_sec"]/60:.1f}분</div></div>')
    return ''.join(rows)


def build_em_top10_list(top10, em_full):
    """em_full: 좌표 lookup 위해 전체 응급실 데이터"""
    name_to_coord = {h['name']: (h['lat'], h['lng']) for h in em_full}
    items = []
    for r in top10:
        coord = name_to_coord.get(r['name'])
        attrs = ''
        if coord:
            attrs = f' class="clickable" data-tab="2" data-lat="{coord[0]}" data-lon="{coord[1]}" data-name="{esc(short_hosp(r["name"]))}"'
        items.append(
            f'<li{attrs}><span class="rank-name">{esc(short_hosp(r["name"]))} '
            f'<span style="color:var(--text4);font-size:9.5px">[{esc(short_kind(r["kind"]))}]</span></span>'
            f'<span class="rank-val">{r["burden_min"]:.1f}분</span></li>')
    return ''.join(items)


def build_blind_list(blind, top=10):
    items = []
    for b in blind[:top]:
        items.append(
            f'<li class="clickable" data-tab="3" data-lat="{b["lat"]}" data-lon="{b["lon"]}" data-name="{esc(b["sttn_nm"])}">'
            f'<span class="rank-name">{esc(b["sttn_nm"])} '
            f'<span style="color:var(--text4);font-size:9.5px">[{esc(b["kind"])}]</span></span>'
            f'<span class="rank-val">{b["elder_rides_noon"]}회 · {b["heat_nearest_m"]}m</span></li>')
    return ''.join(items)


TYPE_ICON = {
    '거점 시장': '🛒',
    '노인복지관': '🏛',
    '거점 공원': '🌳',
    '장거리 터미널·역': '🚌',
    '노인 명소': '📜',
    '환승 거점역': '🚇',
    '응급·상급병원': '🏥',
}


def build_anchor_top(anchors, top=20):
    arr = sorted(anchors, key=lambda a: -a['elder_alights_300m'])[:top]
    items = []
    for a in arr:
        ico = TYPE_ICON.get(a['anchor_type'], '·')
        nm = short_hosp(a['name']) if a['anchor_type'] == '응급·상급병원' else a['name']
        gu = a['gu'] if a['gu'] else a.get('nearest_stn','')[:6]
        items.append(
            f'<li class="clickable" data-tab="4" data-lat="{a["lat"]}" data-lon="{a["lon"]}" data-name="{esc(nm)}">'
            f'<span class="rank-name">{ico} {esc(nm)} '
            f'<span style="color:var(--text4);font-size:9.5px">{esc(gu)}</span></span>'
            f'<span class="rank-val">{a["elder_alights_300m"]:,}명</span></li>')
    return ''.join(items)


def main():
    cst   = json.load(open(DATA/'constellation.json'))
    em    = json.load(open(DATA/'emergency_access.json'))
    cli   = json.load(open(DATA/'climate_station.json'))
    anc   = json.load(open(DATA/'anchor_access.json'))
    heat  = json.load(open(DATA/'heat_shelters.json'))
    chain = json.load(open(DATA/'transfer_chain.json'))

    bright_stations = [s for s in cst['stations'] if s['elder_rides'] >= 5]
    cli_top = sorted(cli['stations'], key=lambda x: -x['elder_rides_noon'])[:500]

    em_sum, cli_sum, anc_sum, cst_sum = em['summary'], cli['summary'], anc['summary'], cst['summary']

    clock_svg     = build_clock_svg(cst['by_hour_xfer'])
    gu_bars       = build_gu_bars(cst['by_gu'])
    xfer_long_list= build_station_rank_list(cst['top_xfer_long'], 'avg_sec', lambda v: f"{v/60:.1f}분")
    xfer_pax_list = build_station_rank_list(cst['top_xfer_pax'],  'pax',     lambda v: f"{int(v):,}명")
    od_list_t1    = build_od_list(cst['od_stations'], top=10)
    od_list_t6    = build_od_list(cst['od_stations'], top=20)
    xfer_type_bars= build_xfer_type_bars(cst['xfer_type_summary'])
    hosp_chart    = build_hospital_chart(cst['hosp_top'])
    # 환승 거점역 TOP10 리스트 (재구성된 chain)
    chain_top_items = []
    for r in chain['station_top10']:
        chain_top_items.append(
            f'<li class="clickable" data-tab="1" data-lat="{r["lat"]}" data-lon="{r["lon"]}" '
            f'data-name="{esc(r["sttn_nm"])}">'
            f'<span class="rank-name">{esc(r["sttn_nm"])} '
            f'<span style="color:var(--text4);font-size:9.5px">[{esc(r["kind"])}]</span></span>'
            f'<span class="rank-val">{r["total"]}건</span></li>')
    chain_top_list = ''.join(chain_top_items)
    self_suff_bars= build_self_suff_bars(cst['gu_self_suff'])
    ss_arr        = cst['gu_self_suff']
    self_avg      = sum(g['self_pct'] for g in ss_arr) / len(ss_arr)
    self_top      = max(ss_arr, key=lambda g: g['self_pct'])
    self_bot      = min(ss_arr, key=lambda g: g['self_pct'])
    # em_list 더이상 사용 안 함 (탭 2 제거)
    blind_list  = build_blind_list(cli['blind_spots_top30'])
    anchor_list = build_anchor_top(anc['anchors'], top=20)

    # 마커 데이터 (JS로 보내는 슬림 버전)
    # 환승 분해는 bright_stations만 — 클라이언트 부하 ↓
    bright_ids = {s['sttn_id'] for s in bright_stations}
    bd_slim = {sid: bd for sid, bd in cst['xfer_breakdown'].items() if sid in bright_ids}

    js_data = {
        'stations':       bright_stations,
        'emergency':      em['emergency'],
        'climate':        cli_top,
        'heat':           heat,
        'anchors':        anc['anchors'],
        'od_stations':    cst['od_stations'],
        'xfer_breakdown': bd_slim,
        'chain_breakdown': chain['station_breakdown'],
    }

    html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>서울 노인 교통·이동 대시보드 — 5축 진단</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@300;400;600&family=IBM+Plex+Mono:wght@300;400;500&family=Noto+Sans+KR:wght@300;400;500;700&display=swap" rel="stylesheet">
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey=__KAKAO_KEY__"></script>
<style>
:root {
  --bg:#070910; --bg2:#0c0f1a; --bg3:#121520; --bg4:#181c28;
  --border:rgba(255,255,255,0.08); --border2:rgba(255,255,255,0.18);
  --text:#edecea; --text2:#bfbdb8; --text3:#888680; --text4:#50504e;
  --teal:#3ecfa0; --blue:#5aadff; --purple:#b48ef4;
  --red:#ff5f5f; --amber:#f5b740; --pink:#f472b6; --green:#7cd982;
  --mono:'IBM Plex Mono',monospace;
  --serif:'Noto Serif KR',serif;
  --sans:'Noto Sans KR',sans-serif;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;overflow-x:hidden}

header{
  border-bottom:1px solid var(--border);
  padding:1.8rem 3rem 1.4rem;
  display:flex;align-items:flex-end;justify-content:space-between;gap:2rem;
  background:linear-gradient(180deg,#08091400 0%,var(--bg) 100%);
  position:relative;
}
header::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 70% 110% at 12% 50%,rgba(90,173,255,0.05) 0%,transparent 70%);
  pointer-events:none;
}
.hd-kicker{font-family:var(--mono);font-size:10px;letter-spacing:.22em;color:var(--text4);text-transform:uppercase;margin-bottom:.6rem}
header h1{font-family:var(--serif);font-size:2.1rem;font-weight:300;line-height:1.2}
header h1 em{color:var(--amber);font-style:normal;font-weight:400}
.hd-meta{font-family:var(--mono);font-size:10.5px;color:var(--text4);text-align:right;line-height:2}

.tabbar{
  background:var(--bg2);border-bottom:1px solid var(--border);
  padding:1rem 3rem;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;
}
.tabbtn{
  font-family:var(--mono);font-size:11.5px;padding:8px 16px;border-radius:4px;
  border:1px solid var(--border2);background:transparent;color:var(--text3);
  cursor:pointer;letter-spacing:.04em;transition:all .15s;
}
.tabbtn:hover{border-color:rgba(255,255,255,.35);color:var(--text)}
.tabbtn.on{color:var(--bg);font-weight:500}
.tabbtn.on.t1{background:var(--blue);   border-color:var(--blue)}
.tabbtn.on.t2{background:var(--red);    border-color:var(--red)}
.tabbtn.on.t3{background:var(--amber);  border-color:var(--amber)}
.tabbtn.on.t4{background:var(--green);  border-color:var(--green)}
.tabbtn.on.t5{background:var(--purple); border-color:var(--purple)}
.tabbtn.on.t6{background:var(--pink); border-color:var(--pink)}

main{padding:0;min-height:calc(100vh - 200px)}
.tab-content{display:none}
.tab-content.on{display:block}

.layout{display:grid;grid-template-columns:1fr 380px;height:calc(100vh - 145px)}
.map-area{position:relative;background:var(--bg3);border-right:1px solid var(--border)}
.map-area .map{width:100%;height:100%}
.side{padding:1.6rem 1.8rem;background:var(--bg2);overflow-y:auto}
.side h2{font-family:var(--serif);font-size:1.3rem;font-weight:400;margin-bottom:.3rem}
.side .ksub{font-family:var(--mono);font-size:10.5px;color:var(--text3);letter-spacing:.06em;margin-bottom:1.2rem}
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:1.4rem}
.kpi{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:.7rem .9rem}
.kpi-l{font-family:var(--mono);font-size:9.5px;color:var(--text4);text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.kpi-v{font-size:1.45rem;font-weight:500;line-height:1.1}
.kpi-s{font-family:var(--mono);font-size:10px;color:var(--text4);margin-top:3px}

.divider{height:1px;background:var(--border);margin:1.1rem 0}
.section-title{font-family:var(--serif);font-size:1rem;color:var(--text2);margin-bottom:.7rem;padding-bottom:5px;border-bottom:1px solid var(--border);margin-top:1.4rem}

ul.rank{list-style:none}
ul.rank li{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed var(--border);font-family:var(--mono);font-size:11.5px}
ul.rank li:last-child{border-bottom:none}
ul.rank li.clickable{cursor:pointer;transition:background .12s,padding .12s}
ul.rank li.clickable:hover{background:rgba(90,173,255,.08);padding-left:6px;padding-right:6px;border-radius:4px}
.rank-name{color:var(--text2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rank-val{color:var(--amber);font-weight:500;margin-left:.6rem;flex-shrink:0}

.bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:4px;font-family:var(--mono);font-size:10.5px}
.bar-name{width:60px;color:var(--text3);flex-shrink:0}
.bar-track{flex:1;height:7px;background:var(--bg4);border-radius:3px;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--blue),var(--red))}
.bar-num{width:38px;text-align:right;color:var(--text2)}

.iframe-wrap{height:calc(100vh - 145px);background:#fff}
.iframe-wrap iframe{width:100%;height:100%;border:none}

footer{padding:1.4rem 3rem;border-top:1px solid var(--border);background:var(--bg2);font-family:var(--mono);font-size:10px;color:var(--text4);line-height:1.8}

.info-panel{
  position:absolute;top:14px;left:14px;background:rgba(7,9,16,0.92);
  border:1px solid var(--border2);border-radius:6px;padding:12px 16px;
  font-family:var(--mono);font-size:11.5px;color:var(--text2);max-width:280px;z-index:5;
  backdrop-filter:blur(6px);
}
.info-panel b{color:var(--text);font-weight:500}
.info-legend{display:flex;gap:1rem;margin-top:6px;flex-wrap:wrap}
.lg{display:flex;align-items:center;gap:5px;font-size:10.5px}
.lgd{width:9px;height:9px;border-radius:50%}

.shock-box{margin-top:1rem;padding:.8rem .9rem;background:rgba(255,95,95,.06);border:1px solid rgba(255,95,95,.18);border-radius:6px;font-family:var(--mono);font-size:10.5px;color:var(--text2);line-height:1.7}
.shock-box b{color:var(--red);font-weight:500}

.od-toggle{margin-top:8px;font-family:var(--mono);font-size:10.5px;padding:5px 10px;border-radius:4px;
  border:1px solid var(--border2);background:transparent;color:var(--text2);cursor:pointer;letter-spacing:.04em;transition:all .12s;width:100%}
.od-toggle:hover{border-color:var(--pink);color:var(--pink)}
.od-toggle.on{background:var(--pink);color:var(--bg);border-color:var(--pink)}
</style>
</head>
<body>

<header>
  <div>
    <div class="hd-kicker">Seoul Elder Mobility · 노인 교통·이동 진단 ⑤</div>
    <h1>노인이 동네를 벗어날 때<br><em>잃는 시간</em>의 지도</h1>
  </div>
  <div class="hd-meta">
    정류장 16,067 · 환승 데이터 825K · 노인 카드 trip 505K<br>
    응급실 75 · 더위쉼터 4,107 · 거점 시장·복지관 172<br>
    노인 사고 1,963건 · 횡단보도 40,281 · 2025-10 ~ 2026-02-22
  </div>
</header>

<div class="tabbar">
  <button class="tabbtn t1 on" onclick="setTab(1,this)">🌌 1 · 환승 별자리</button>
  <button class="tabbtn t3"    onclick="setTab(3,this)">🌡️ 2 · 폭염 정류장</button>
  <button class="tabbtn t4"    onclick="setTab(4,this)">🛒 3 · 거점 시설</button>
  <button class="tabbtn t5"    onclick="setTab(5,this)">🚦 4 · 횡단보도 안전</button>
  <button class="tabbtn t6"    onclick="setTab(6,this)">🔀 5 · 환승 OD</button>
</div>

<main>

<div class="tab-content on" id="tab1">
  <div class="layout">
    <div class="map-area">
      <div class="info-panel">
        <b>환승 별자리</b><br>
        노인이 자주 타는 정류장 ≈ 빛나는 별. 환승시간 길수록 붉음.
        <div class="info-legend">
          <div class="lg"><div class="lgd" style="background:#3ecfa0"></div>환승 ≤10분</div>
          <div class="lg"><div class="lgd" style="background:#f5b740"></div>15~20분</div>
          <div class="lg"><div class="lgd" style="background:#ff5f5f"></div>>20분</div>
        </div>
        <button class="od-toggle" id="od-toggle-t1" onclick="toggleOD(1,this)">🔀 환승 OD 흐름선 표시</button>
      </div>
      <div class="map" id="map1"></div>
    </div>
    <div class="side">
      <h2>환승 별자리</h2>
      <div class="ksub">노인 이용 정류장 __N_BRIGHT__개 / 전체 __N_TOTAL__개</div>

      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-l">평균 환승</div><div class="kpi-v">__AVG_XFER_MIN__<span style="font-size:.7em;color:var(--text3)"> 분</span></div></div>
        <div class="kpi"><div class="kpi-l">노인 환승률</div><div class="kpi-v">1.7<span style="font-size:.7em;color:var(--text3)"> %</span></div><div class="kpi-s">8,648 / 505,754</div></div>
      </div>

      <div class="section-title">시간대별 환승 시간 (전체)</div>
      __CLOCK_SVG__

      <div class="section-title">25구 환승 시간 TOP10</div>
      __GU_BARS__

      <div class="section-title">🔀 환승 종류별 평균 시간</div>
      __XFER_TYPE_BARS__
      <div style="font-family:var(--mono);font-size:9.5px;color:var(--text4);margin-top:6px;line-height:1.6">TT 지하철↔지하철 가장 빠름 · BB·TB 버스 환승 가장 오래 (배차 + 통로)</div>

      <div class="section-title">⏱ 환승 오래 걸리는 정류장 TOP10</div>
      <ul class="rank">__XFER_LONG_LIST__</ul>

      <div class="section-title">🏥 병원 정류장 환승 종류 분해 (TOP8)</div>
      __HOSP_CHART__
      <div style="font-family:var(--mono);font-size:9.5px;color:var(--text4);margin-top:6px;line-height:1.6">병원 환승은 BB(버스↔버스)가 30~60분. 노인 의료 마지막 1mile 부담</div>

      <div class="section-title">👥 이용객 많은 환승 정류장 TOP10</div>
      <ul class="rank">__XFER_PAX_LIST__</ul>

      <div class="section-title">🔀 노인 환승 OD pair TOP10 (출발→도착)</div>
      <ul class="rank">__OD_LIST_T1__</ul>

      <div class="section-title">🚇 환승 발생 거점역 TOP10 (재구성)</div>
      <ul class="rank">__CHAIN_TOP_LIST__</ul>
      <div style="font-family:var(--mono);font-size:9.5px;color:var(--text4);margin-top:6px;line-height:1.6">
        카드별 trip 시간순 → 30분 갭 = 환승. 정류장 클릭 시 from→to 노선 분해 보기.
      </div>
    </div>
  </div>
</div>

<div class="tab-content" id="tab3">
  <div class="layout">
    <div class="map-area">
      <div class="info-panel">
        <b>폭염일 정류장 안전</b><br>
        정류장 100m 내 더위쉼터 유무. 큰 빨간 별 = 사각지대 + 노인 낮 이용 多
        <div class="info-legend">
          <div class="lg"><div class="lgd" style="background:#f5b740"></div>더위쉼터</div>
          <div class="lg"><div class="lgd" style="background:#3ecfa0"></div>쉼터 100m내 정류장</div>
          <div class="lg"><div class="lgd" style="background:#ff5f5f"></div>사각지대</div>
        </div>
      </div>
      <div class="map" id="map3"></div>
    </div>
    <div class="side">
      <h2>폭염일 정류장</h2>
      <div class="ksub">KIM 쉼터→집 보완 — 쉼터 ↔ 정류장 연계</div>

      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-l">더위쉼터 100m</div><div class="kpi-v">__PCT_HEAT__<span style="font-size:.7em;color:var(--text3)">%</span></div></div>
        <div class="kpi"><div class="kpi-l">한파쉼터 100m</div><div class="kpi-v">__PCT_COLD__<span style="font-size:.7em;color:var(--text3)">%</span></div></div>
        <div class="kpi"><div class="kpi-l">평균 더위쉼터 거리</div><div class="kpi-v">__AVG_HEAT__<span style="font-size:.7em;color:var(--text3)">m</span></div></div>
        <div class="kpi"><div class="kpi-l">평균 한파쉼터 거리</div><div class="kpi-v">__AVG_COLD__<span style="font-size:.7em;color:var(--text3)">m</span></div></div>
      </div>

      <div class="section-title">사각지대 TOP10 (낮 12-15시 노인 이용)</div>
      <ul class="rank">__BLIND_LIST__</ul>
    </div>
  </div>
</div>

<div class="tab-content" id="tab4">
  <div class="layout">
    <div class="map-area">
      <div class="info-panel">
        <b>거점 시설 도달</b><br>
        도시 전체 노인 destinations. 원 크기 = 노인 도착(300m) 수.
        <div class="info-legend">
          <div class="lg"><div class="lgd" style="background:#7cd982"></div>거점 시장</div>
          <div class="lg"><div class="lgd" style="background:#b48ef4"></div>노인복지관</div>
          <div class="lg"><div class="lgd" style="background:#3ecfa0"></div>거점 공원</div>
          <div class="lg"><div class="lgd" style="background:#5aadff"></div>터미널·역</div>
          <div class="lg"><div class="lgd" style="background:#f5b740"></div>노인 명소</div>
          <div class="lg"><div class="lgd" style="background:#ff5f5f"></div>환승 거점역</div>
          <div class="lg"><div class="lgd" style="background:#f472b6"></div>응급·상급병원</div>
        </div>
      </div>
      <div class="map" id="map4"></div>
    </div>
    <div class="side">
      <h2>거점 시설 도달</h2>
      <div class="ksub">시장·공원·복지관·터미널·명소·환승역·병원 = __N_TOTAL__개</div>

      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-l">거점 시장</div><div class="kpi-v">__N_MKT__</div></div>
        <div class="kpi"><div class="kpi-l">거점 공원</div><div class="kpi-v">__N_PARK__</div></div>
        <div class="kpi"><div class="kpi-l">응급·상급병원</div><div class="kpi-v">__N_HOSP__</div></div>
        <div class="kpi"><div class="kpi-l">노인복지관·기타</div><div class="kpi-v">__N_OTHER__</div></div>
      </div>

      <div class="section-title">노인 도착 TOP20 거점</div>
      <ul class="rank">__ANCHOR_LIST__</ul>
    </div>
  </div>
</div>

<div class="tab-content" id="tab5">
  <div class="iframe-wrap">
    <iframe src="tab5_crosswalk.html" title="신호 없는 횡단보도 × 노인 사고"></iframe>
  </div>
</div>

<div class="tab-content" id="tab6">
  <div class="layout">
    <div class="map-area">
      <div class="info-panel">
        <b>노인 환승 OD 흐름</b><br>
        TOP 40 환승 trip — 출발에서 도착까지 곡선. 두께·진하기 = 빈도.
        <div class="info-legend">
          <div class="lg"><div class="lgd" style="background:#ff5f5f;border-radius:0;width:14px;height:3px"></div>도심간 이동</div>
          <div class="lg"><div class="lgd" style="background:#5aadff;border-radius:0;width:14px;height:3px"></div>외곽 이동</div>
        </div>
      </div>
      <div class="map" id="map6"></div>
    </div>
    <div class="side">
      <h2>노인 환승 OD</h2>
      <div class="ksub">환승 trip 8,648건 (전체 trip의 1.7%)</div>

      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-l">자족 평균</div><div class="kpi-v">__SELF_AVG__<span style="font-size:.7em;color:var(--text3)">%</span></div><div class="kpi-s">같은 구 내 환승</div></div>
        <div class="kpi"><div class="kpi-l">자족 최고</div><div class="kpi-v">__SELF_MAX__<span style="font-size:.7em;color:var(--text3)">%</span></div><div class="kpi-s">__SELF_MAX_GU__</div></div>
        <div class="kpi"><div class="kpi-l">자족 최저</div><div class="kpi-v">__SELF_MIN__<span style="font-size:.7em;color:var(--text3)">%</span></div><div class="kpi-s">__SELF_MIN_GU__</div></div>
        <div class="kpi"><div class="kpi-l">총 OD pair</div><div class="kpi-v">40</div><div class="kpi-s">정류장 단위</div></div>
      </div>

      <div class="section-title">25구 환승 자족 비율</div>
      __SELF_SUFF_BARS__

      <div class="section-title">환승 OD pair TOP20</div>
      <ul class="rank">__OD_LIST_T6__</ul>

      <div class="shock-box" style="background:rgba(124,217,130,.06);border-color:rgba(124,217,130,.18)">
        <b style="color:var(--green)">📍 핵심 발견</b><br>
        외곽구(은평·노원 84%+) 자족 ↑, 도심구(중·마포·용산 ≤55%) 자족 ↓. 도심은 인접 구로 짧은 환승, 외곽은 동네 안.
      </div>
    </div>
  </div>
</div>

</main>

<footer>
  데이터 출처: 공공데이터포털(환승·정류장·노선) · TAAS(노인 사고) · 서울 열린데이터광장(횡단보도) · 카카오맵<br>
  병원 데이터는 LEE 의료, 쉼터는 KIM 기후, 시장은 SHIM 인프라, 복지관은 YANG 복지 파트에서 차용 — 5팀 통합 발표 자산.<br>
  분석 기준: 노인 보행속도 0.88 m/s · 환승시간 실측(2025-10) · 노인 카드 trip 1일 단일(2026-02-22 일요일)
</footer>

<script>
const DATA = __JS_DATA__;

const maps = {}, mapInited = {};
function setTab(n, btn){
  document.querySelectorAll('.tabbtn').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('on'));
  document.getElementById('tab'+n).classList.add('on');
  if (!mapInited[n] && n !== 5) {
    setTimeout(() => initMap(n), 80);
    mapInited[n] = true;
  } else if (maps[n]) {
    setTimeout(() => maps[n].relayout(), 80);
  }
}

function xferColor(sec) {
  if (sec == null || sec === 0) return '#888680';
  if (sec < 600)  return '#3ecfa0';
  if (sec < 900)  return '#5aadff';
  if (sec < 1200) return '#f5b740';
  return '#ff5f5f';
}

function initMap(n) {
  if (typeof kakao === 'undefined' || !kakao.maps || !kakao.maps.LatLng) {
    setTimeout(() => initMap(n), 200);
    return;
  }
  const center = new kakao.maps.LatLng(37.55, 126.99);
  const map = new kakao.maps.Map(document.getElementById('map'+n), { center, level: 8 });
  maps[n] = map;
  if (n === 1) renderTab1(map);
  else if (n === 3) renderTab3(map);
  else if (n === 4) renderTab4(map);
  else if (n === 6) renderTab6(map);
}

// ──── OD 곡선 보간 (베지어) ────
function bezierCurve(lat1, lon1, lat2, lon2, n=24, curvature=0.18) {
  const mx = (lon1 + lon2) / 2, my = (lat1 + lat2) / 2;
  const dx = lon2 - lon1, dy = lat2 - lat1;
  const len = Math.hypot(dx, dy);
  // perpendicular offset
  const offX = -dy / len * curvature * len;
  const offY =  dx / len * curvature * len;
  const cx = mx + offX, cy = my + offY;
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const x = (1-t)*(1-t)*lon1 + 2*(1-t)*t*cx + t*t*lon2;
    const y = (1-t)*(1-t)*lat1 + 2*(1-t)*t*cy + t*t*lat2;
    pts.push(new kakao.maps.LatLng(y, x));
  }
  return pts;
}

function odColor(n) {
  if (n >= 20) return '#ff5f5f';
  if (n >= 13) return '#f5b740';
  if (n >= 8)  return '#5aadff';
  return '#b48ef4';
}

const odLayers = {};
function renderODCurves(map, tab) {
  const lines = [];
  DATA.od_stations.forEach(o => {
    const path = bezierCurve(o.ride_lat, o.ride_lon, o.goff_lat, o.goff_lon);
    const w = Math.max(2, Math.min(7, Math.sqrt(o.n) * 1.4));
    const pl = new kakao.maps.Polyline({
      map, path, strokeWeight: w,
      strokeColor: odColor(o.n), strokeOpacity: 0.65, strokeStyle: 'solid',
    });
    lines.push(pl);
    // 출발·도착 점
    const dotR = Math.max(60, Math.sqrt(o.n) * 25);
    lines.push(new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(o.ride_lat, o.ride_lon),
      radius: dotR, strokeWeight: 0, fillColor: '#3ecfa0', fillOpacity: 0.75,
    }));
    lines.push(new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(o.goff_lat, o.goff_lon),
      radius: dotR * 0.9, strokeWeight: 1, strokeColor: '#fff', strokeOpacity: 0.7,
      fillColor: '#f472b6', fillOpacity: 0.75,
    }));
  });
  odLayers[tab] = lines;
}

function clearOD(tab) {
  if (odLayers[tab]) {
    odLayers[tab].forEach(o => o.setMap(null));
    delete odLayers[tab];
  }
}

function toggleOD(tab, btn) {
  if (odLayers[tab]) {
    clearOD(tab);
    btn.classList.remove('on');
    btn.textContent = '🔀 환승 OD 흐름선 표시';
  } else {
    renderODCurves(maps[tab], tab);
    btn.classList.add('on');
    btn.textContent = '✕ OD 흐름선 끄기';
  }
}

function renderTab6(map) {
  // 항상 OD 곡선 표시
  renderODCurves(map, 6);
}

const TYPE_LABEL = {'BB':'🚌→🚌', 'BT':'🚌→🚇', 'TB':'🚇→🚌', 'TT':'🚇→🚇'};
const TYPE_COLOR = {'TT':'#3ecfa0','BT':'#5aadff','BB':'#f5b740','TB':'#ff5f5f'};

let infoWindow = null;
function showStationInfo(map, s) {
  if (infoWindow) infoWindow.close();
  const bd = DATA.xfer_breakdown[s.sttn_id] || {};
  const types = ['TT','BT','BB','TB'];
  let rows = '';
  for (const t of types) {
    const d = bd[t];
    if (!d) continue;
    const min = (d.sec/60).toFixed(1);
    rows += '<div style="display:flex;justify-content:space-between;font-size:11px;padding:2px 0;color:#444">' +
            '<span style="color:'+TYPE_COLOR[t]+';font-weight:500">'+TYPE_LABEL[t]+'</span>' +
            '<span>'+min+'분 · '+d.pax.toLocaleString()+'명</span></div>';
  }
  if (!rows) rows = '<div style="font-size:11px;color:#888">환승 데이터 없음</div>';

  // from→to 노선 분해 (재구성된 chain)
  const chain = DATA.chain_breakdown[s.sttn_id];
  let chainRows = '';
  if (chain && chain.pairs && chain.pairs.length) {
    chainRows = '<div style="border-top:1px solid #eee;padding-top:6px;margin-top:6px">' +
                '<div style="font-size:10px;color:#888;margin-bottom:4px">노선 from→to TOP (노인 카드 기준 · 총 '+chain.total+'건):</div>';
    for (const p of chain.pairs.slice(0, 5)) {
      const fromN = (p.from || '?').replace(/\(.*?\)/g,'').slice(0, 18);
      const toN   = (p.to   || '?').replace(/\(.*?\)/g,'').slice(0, 18);
      chainRows += '<div style="font-size:10.5px;padding:1.5px 0;color:#555">' +
                   '<span style="color:#3ecfa0">'+fromN+'</span> → <span style="color:#f472b6">'+toN+'</span> ' +
                   '<span style="color:#888">'+p.n+'건</span></div>';
    }
    chainRows += '</div>';
  }

  const html = '<div style="padding:8px 11px;font-family:-apple-system,sans-serif;min-width:240px;max-width:320px">' +
               '<div style="font-size:13px;font-weight:600;margin-bottom:6px">'+s.sttn_nm+'</div>' +
               '<div style="font-size:10.5px;color:#888;margin-bottom:6px">노인 ride '+s.elder_rides+'회 / 평균 환승 '+(s.avg_xfer_sec/60).toFixed(1)+'분</div>' +
               '<div style="border-top:1px solid #eee;padding-top:5px">'+rows+'</div>' +
               chainRows + '</div>';
  infoWindow = new kakao.maps.InfoWindow({
    position: new kakao.maps.LatLng(s.lat, s.lon),
    content: html, removable: true,
  });
  infoWindow.open(map);
}

function renderTab1(map) {
  DATA.stations.forEach(s => {
    const r = Math.max(80, Math.min(600, Math.sqrt(s.elder_rides) * 12));
    const color = xferColor(s.avg_xfer_sec);
    const c = new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(s.lat, s.lon),
      radius: r, strokeWeight: 0, fillColor: color, fillOpacity: 0.65,
    });
    kakao.maps.event.addListener(c, 'click', () => showStationInfo(map, s));
  });
}

function renderTab3(map) {
  DATA.heat.forEach(s => {
    new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(s.lat, s.lng),
      radius: 100, strokeWeight: 0, fillColor: '#f5b740', fillOpacity: 0.4,
    });
  });
  DATA.climate.forEach(s => {
    const blind = s.heat_within_100m === 0;
    const color = blind ? '#ff5f5f' : '#3ecfa0';
    const r = blind ? Math.max(200, Math.sqrt(s.elder_rides_noon) * 25) : 120;
    new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(s.lat, s.lon),
      radius: r, strokeWeight: blind ? 2 : 0, strokeColor: '#fff', strokeOpacity: 0.7,
      fillColor: color, fillOpacity: blind ? 0.7 : 0.4,
    });
  });
}

function renderTab4(map) {
  const TYPE_COLOR = {
    '거점 시장':       '#7cd982',
    '노인복지관':      '#b48ef4',
    '거점 공원':       '#3ecfa0',
    '장거리 터미널·역': '#5aadff',
    '노인 명소':       '#f5b740',
    '환승 거점역':     '#ff5f5f',
  };
  DATA.anchors.forEach(a => {
    const color = TYPE_COLOR[a.anchor_type] || '#888680';
    const r = Math.max(220, Math.min(2200, Math.sqrt(a.elder_alights_300m || 1) * 28));
    new kakao.maps.Circle({
      map, center: new kakao.maps.LatLng(a.lat, a.lon),
      radius: r, strokeWeight: 2, strokeColor: '#fff', strokeOpacity: 0.55,
      fillColor: color, fillOpacity: 0.5,
    });
  });
}

window.addEventListener('load', () => setTimeout(() => initMap(1), 80));
mapInited[1] = true;

// ──── 랭킹 클릭 → 지도 이동 ────
let highlightMarker = null;
function panToStation(tabN, lat, lon, name) {
  const tabBtn = document.querySelector('.tabbtn.t' + tabN);
  if (tabBtn && !tabBtn.classList.contains('on')) tabBtn.click();

  const go = () => {
    const map = maps[tabN];
    if (!map) { setTimeout(go, 120); return; }
    const ll = new kakao.maps.LatLng(parseFloat(lat), parseFloat(lon));
    map.setLevel(4, { animate: true });
    map.panTo(ll);
    if (highlightMarker) highlightMarker.setMap(null);
    highlightMarker = new kakao.maps.Circle({
      map, center: ll, radius: 80,
      strokeWeight: 3, strokeColor: '#f5b740', strokeOpacity: 0.95,
      fillColor: '#f5b740', fillOpacity: 0.35,
    });
    setTimeout(() => { if (highlightMarker) { highlightMarker.setMap(null); highlightMarker = null; }}, 4500);
  };
  setTimeout(go, 100);
}

document.addEventListener('click', e => {
  const li = e.target.closest('li.clickable');
  if (!li) return;
  panToStation(li.dataset.tab, li.dataset.lat, li.dataset.lon, li.dataset.name);
});
</script>
</body>
</html>
"""

    repls = {
        '__KAKAO_KEY__':         KAKAO_KEY,
        '__N_TOTAL__':           f"{cst_sum['n_stations_total']:,}",
        '__N_BRIGHT__':          f"{len(bright_stations):,}",
        '__AVG_XFER_MIN__':      f"{cst_sum['avg_xfer_sec']/60:.1f}",
        '__CLOCK_SVG__':         clock_svg,
        '__GU_BARS__':           gu_bars,
        '__XFER_LONG_LIST__':    xfer_long_list,
        '__XFER_PAX_LIST__':     xfer_pax_list,
        '__OD_LIST_T1__':        od_list_t1,
        '__OD_LIST_T6__':        od_list_t6,
        '__XFER_TYPE_BARS__':    xfer_type_bars,
        '__HOSP_CHART__':        hosp_chart,
        '__CHAIN_TOP_LIST__':    chain_top_list,
        '__SELF_SUFF_BARS__':    self_suff_bars,
        '__SELF_AVG__':          f"{self_avg:.0f}",
        '__SELF_MAX__':          f"{self_top['self_pct']:.0f}",
        '__SELF_MAX_GU__':       self_top['gu'],
        '__SELF_MIN__':          f"{self_bot['self_pct']:.0f}",
        '__SELF_MIN_GU__':       self_bot['gu'],
        '__PCT_HEAT__':          f"{cli_sum['pct_stn_with_heat_100m']:.0f}",
        '__PCT_COLD__':          f"{cli_sum['pct_stn_with_cold_100m']:.0f}",
        '__AVG_HEAT__':          str(cli_sum['avg_heat_distance_m']),
        '__AVG_COLD__':          str(cli_sum['avg_cold_distance_m']),
        '__BLIND_LIST__':        blind_list,
        '__N_TOTAL__':           str(anc_sum.get('n_total', 0)),
        '__N_MKT__':             str(anc.get('type_counts', {}).get('거점 시장', 0)),
        '__N_PARK__':            str(anc.get('type_counts', {}).get('거점 공원', 0)),
        '__N_HOSP__':            str(anc.get('type_counts', {}).get('응급·상급병원', 0)),
        '__N_OTHER__':           str(
            anc.get('type_counts', {}).get('노인복지관', 0)
            + anc.get('type_counts', {}).get('장거리 터미널·역', 0)
            + anc.get('type_counts', {}).get('노인 명소', 0)
            + anc.get('type_counts', {}).get('환승 거점역', 0)),
        '__ANCHOR_LIST__':       anchor_list,
        '__JS_DATA__':           json.dumps(js_data, ensure_ascii=False),
    }

    out = html_template
    for k, v in repls.items():
        out = out.replace(k, v)

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f"saved: {OUT}")
    print(f"size:  {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
