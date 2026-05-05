#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_conclusion_v4.py — 서울시 복지·녹지 접근성 종합 결론 대시보드
=======================================================================
gu_scores_v4.csv 가 없으면 dong_reachability_v4.csv 에서 직접 집계합니다.

출력: output_v4/conclusion.html
"""

import os, sys, json, re
import pandas as pd
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_v4')
GU_CSV     = os.path.join(OUTPUT_DIR, 'gu_scores_v4.csv')
V4_CSV     = os.path.join(OUTPUT_DIR, 'dong_reachability_v4.csv')

print("=" * 60)
print("generate_conclusion_v4 — 종합 결론 대시보드 생성")
print("=" * 60)


# ── 1. 구 단위 점수 데이터 로드 (없으면 직접 집계) ───────────────────────────
print("\n1. 구 단위 점수 데이터 로드")

if os.path.exists(GU_CSV):
    gu_df = pd.read_csv(GU_CSV, encoding='utf-8-sig')
    print(f"  gu_scores_v4.csv 로드: {len(gu_df)}개 구")
else:
    print("  gu_scores_v4.csv 없음 → dong_reachability_v4.csv 에서 직접 집계")
    df = pd.read_csv(V4_CSV, encoding='utf-8-sig')
    df.columns = [c.strip() for c in df.columns]
    df['합산_일반인']   = df['복지_일반인'] + df['공원_일반인']
    df['합산_노인_X']   = df['복지_일반노인']    + df['공원_일반노인']
    df['합산_노인_O']   = df['복지_일반노인보정']    + df['공원_일반노인보정']
    df['합산_보행보조_X'] = df['복지_보조기기']    + df['공원_보조기기']
    df['합산_보행보조_O'] = df['복지_보조기기보정']    + df['공원_보조기기보정']
    df['합산_하위15_X']  = df['복지_보조하위15p'] + df['공원_보조하위15p']
    df['합산_하위15_O']  = df['복지_보조하위15p보정'] + df['공원_보조하위15p보정']
    den = df['합산_일반인'].replace(0, np.nan)
    score_cols = ['점수_노인_경사X','점수_노인_경사O',
                  '점수_보행보조_경사X','점수_보행보조_경사O',
                  '점수_하위15_경사X','점수_하위15_경사O']
    df['점수_노인_경사X']    = df['합산_노인_X']   / den * 100
    df['점수_노인_경사O']    = df['합산_노인_O']   / den * 100
    df['점수_보행보조_경사X'] = df['합산_보행보조_X'] / den * 100
    df['점수_보행보조_경사O'] = df['합산_보행보조_O'] / den * 100
    df['점수_하위15_경사X']  = df['합산_하위15_X']  / den * 100
    df['점수_하위15_경사O']  = df['합산_하위15_O']  / den * 100
    gu_df = df.groupby('구명')[score_cols].mean().round(1).reset_index()
    print(f"  직접 집계 완료: {len(gu_df)}개 구")

# ── 2. 종합 통계 계산 ─────────────────────────────────────────────────────────
print("\n2. 종합 통계 계산")

gu_df = gu_df.sort_values('점수_하위15_경사O')  # 가장 취약한 순서

def fmt(v):
    return round(float(v), 1) if pd.notna(v) else None

# 서울 전체 평균
avg = {}
for c in ['점수_노인_경사X','점수_노인_경사O','점수_보행보조_경사X',
          '점수_보행보조_경사O','점수_하위15_경사X','점수_하위15_경사O']:
    avg[c] = round(gu_df[c].mean(), 1)

# 경사 보정 감소폭 컬럼 추가
gu_df['감소_노인']    = (gu_df['점수_노인_경사X']    - gu_df['점수_노인_경사O']).round(1)
gu_df['감소_보행보조'] = (gu_df['점수_보행보조_경사X'] - gu_df['점수_보행보조_경사O']).round(1)
gu_df['감소_하위15']  = (gu_df['점수_하위15_경사X']  - gu_df['점수_하위15_경사O']).round(1)

for k in ['노인','보행보조','하위15']:
    col = f'감소_{k}'
    print(f"  경사 보정 감소 ({k}): 서울 평균 {gu_df[col].mean():.1f}점  "
          f"최대 {gu_df[col].max():.1f}점 ({gu_df.loc[gu_df[col].idxmax(),'구명']})")

# ── 3. JS용 데이터 직렬화 ─────────────────────────────────────────────────────
print("\n3. 데이터 직렬화")

GU_DATA = []
for _, r in gu_df.iterrows():
    GU_DATA.append({
        'gu':       r['구명'],
        'n_x':      fmt(r['점수_노인_경사X']),
        'n_o':      fmt(r['점수_노인_경사O']),
        'b_x':      fmt(r['점수_보행보조_경사X']),
        'b_o':      fmt(r['점수_보행보조_경사O']),
        'h_x':      fmt(r['점수_하위15_경사X']),
        'h_o':      fmt(r['점수_하위15_경사O']),
        'drop_n':   fmt(r['감소_노인']),
        'drop_b':   fmt(r['감소_보행보조']),
        'drop_h':   fmt(r['감소_하위15']),
    })

GU_JS  = json.dumps(GU_DATA,  ensure_ascii=False, separators=(',', ':'))
AVG_JS = json.dumps(avg,      ensure_ascii=False, separators=(',', ':'))
print(f"  GU_DATA: {len(GU_DATA)}개 구")

# ── 4. HTML 생성 ──────────────────────────────────────────────────────────────
print("\n4. HTML 생성 중...")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울시 노인 보행일상권 — 복지·녹지 접근성 종합 결론</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;background:#f5f4f0;color:#2c2c2a;font-size:14px;line-height:1.6;overflow-y:scroll}
header{background:#2c2c2a;color:#f1efe8;padding:20px 32px}
header h1{font-size:18px;font-weight:500;margin-bottom:4px}
header p{font-size:12px;opacity:.55}
.wrap{max-width:1320px;margin:0 auto;padding:20px 20px 60px}
.section{margin-bottom:28px}
.section-title{font-size:13px;font-weight:600;letter-spacing:.06em;color:#888780;text-transform:uppercase;margin-bottom:14px;padding-bottom:6px;border-bottom:1px solid #e8e6e0}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.card{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 20px}
.card-title{font-size:11px;color:#888780;margin-bottom:6px}
.card-val{font-size:26px;font-weight:500}
.card-sub{font-size:11px;color:#888780;margin-top:4px}
.card.warn{background:#fff8f0;border-color:#efb87c}
.card.danger{background:#fff0f0;border-color:#e08080}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.chart-card{background:#fff;border:0.5px solid #d3d1c7;border-radius:12px;padding:16px 20px}
.chart-label{font-size:11px;font-weight:500;color:#555;margin-bottom:10px}
.chart-wrap{position:relative;height:420px}
.chart-wrap-sm{position:relative;height:300px}
.note{background:#faeeda;border:0.5px solid #ef9f27;border-radius:8px;padding:12px 16px;font-size:12px;color:#633806;line-height:1.8;margin-top:16px}
.finding{background:#eef4ff;border:0.5px solid #a0b8e0;border-radius:8px;padding:12px 16px;font-size:12px;color:#1a3a6a;line-height:1.8;margin-top:8px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{padding:7px 10px;text-align:right;font-weight:500;color:#888780;border-bottom:0.5px solid #d3d1c7;white-space:nowrap;position:sticky;top:0;background:#fff;z-index:1}
th:first-child{text-align:left}
td{padding:7px 10px;border-bottom:0.5px solid #f1efe8;text-align:right}
td:first-child{text-align:left;font-weight:500}
tr:hover td{background:#fafaf8}
.tbl-wrap{overflow-x:auto;max-height:440px;overflow-y:auto;border:0.5px solid #d3d1c7;border-radius:8px}
.pill{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:8px}
.phi{background:#e1f5ee;color:#0f6e56}
.pmd{background:#faeeda;color:#854f0b}
.plo{background:#fcebeb;color:#a32d2d}
.drop-hi{color:#c62828;font-weight:600}
.drop-lo{color:#555}
.legend-row{display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap}
.leg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:#5f5e5a}
.leg-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.tab-btns{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}
.tb{font-size:12px;padding:4px 12px;border-radius:6px;border:0.5px solid #b4b2a9;background:transparent;color:#888780;cursor:pointer;font-family:inherit}
.tb:hover{background:#f5f4f0}
.tb.on{background:#f1efe8;color:#2c2c2a;font-weight:500;border-color:#d3d1c7}
@media(max-width:900px){.cards,.grid2,.grid3{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>서울시 노인 보행일상권 ② — 복지·녹지 인프라 접근성 종합 결론</h1>
  <p>OSM 보행 네트워크 기반 · Tobler 경사 보정 적용 · 30분 기준 · 서울시 25개 자치구 · 2026</p>
</header>

<div class="wrap">

  <!-- ── 요약 카드 ── -->
  <div class="section">
    <div class="section-title">서울시 전체 평균 도달가능점수 (복지+공원 합산)</div>
    <div class="cards" id="summaryCards"></div>
    <div class="finding" id="findingText"></div>
  </div>

  <!-- ── 비교 차트 ── -->
  <div class="section">
    <div class="section-title">보행자 유형별 도달가능점수 — 경사 보정 전후 비교 (구 단위)</div>
    <div class="tab-btns">
      <button class="tb on" onclick="showChart('노인',this)">🧓 일반 노인 (1.12 m/s)</button>
      <button class="tb" onclick="showChart('보행보조',this)">🦽 보조기기 (0.88 m/s)</button>
      <button class="tb" onclick="showChart('하위15',this)">♿ 보조 하위15% (0.70 m/s)</button>
    </div>
    <div class="chart-card">
      <div class="legend-row">
        <div class="leg-item"><div class="leg-dot" style="background:#4a90d9"></div>경사 보정 없음 (경사X)</div>
        <div class="leg-item"><div class="leg-dot" style="background:#e05b3a"></div>경사 보정 적용 (경사O)</div>
      </div>
      <div class="chart-wrap"><canvas id="compareChart"></canvas></div>
      <p style="font-size:11px;color:#888780;margin-top:8px">
        도달가능점수 = (해당 속도로 도달 가능한 복지+공원 합산 수 / 일반인 도달 수) × 100 · 구 내 행정동 평균
      </p>
    </div>
  </div>

  <!-- ── 경사 보정 감소량 ── -->
  <div class="section">
    <div class="section-title">경사 보정으로 인한 점수 감소량 (경사X − 경사O)</div>
    <div class="grid2">
      <div class="chart-card">
        <div class="chart-label">보조기기 vs 하위15% — 구별 감소량</div>
        <div class="chart-wrap-sm"><canvas id="dropChart"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-label">3개 유형 동시 비교 — 구별 (하위15% 감소 내림차순)</div>
        <div class="chart-wrap-sm"><canvas id="drop3Chart"></canvas></div>
      </div>
    </div>
    <div class="note" id="dropNote"></div>
  </div>

  <!-- ── 종합 테이블 ── -->
  <div class="section">
    <div class="section-title">구별 도달가능점수 종합 테이블 (하위15% 경사O 오름차순)</div>
    <div class="tbl-wrap">
      <table id="mainTable"></table>
    </div>
  </div>

</div><!-- /wrap -->

<script>
const GU   = __GU_DATA__;
const AVG  = __AVG_DATA__;

// ── 요약 카드 ────────────────────────────────────────────────────────────────
const CARD_CFG = [
  {key:'n',  label:'일반 노인 (1.12 m/s)', x:'n_x', o:'n_o'},
  {key:'b',  label:'보조기기 (0.88 m/s)',   x:'b_x', o:'b_o'},
  {key:'h',  label:'보조 하위15% (0.70 m/s)', x:'h_x', o:'h_o'},
];
function gradeClass(v){
  return v===null?'':v>=80?'phi':v>=50?'pmd':'plo';
}
function renderCards(){
  const avgs = {
    n_x: AVG['점수_노인_경사X'],    n_o: AVG['점수_노인_경사O'],
    b_x: AVG['점수_보행보조_경사X'], b_o: AVG['점수_보행보조_경사O'],
    h_x: AVG['점수_하위15_경사X'],  h_o: AVG['점수_하위15_경사O'],
  };
  document.getElementById('summaryCards').innerHTML = CARD_CFG.map(c=>{
    const vx=avgs[c.x], vo=avgs[c.o], drop=vo!==null&&vx!==null?(vx-vo).toFixed(1):null;
    const cls = vo>=80?'card':vo>=50?'card warn':'card danger';
    return `<div class="${cls}">
      <div class="card-title">${c.label}</div>
      <div class="card-val">
        <span class="pill ${gradeClass(vx)}">${vx}점</span>
        <span style="font-size:14px;color:#999;margin:0 6px">→</span>
        <span class="pill ${gradeClass(vo)}">${vo}점</span>
      </div>
      <div class="card-sub">경사X → 경사O · 서울 구 평균${drop!==null?' · 경사로 −'+drop+'점':''}</div>
    </div>`;
  }).join('');

  // 핵심 발견 텍스트
  const worst = GU[0];
  const bestH = [...GU].sort((a,b)=>b.h_o-a.h_o)[0];
  const maxDrop = [...GU].sort((a,b)=>b.drop_h-a.drop_h)[0];
  document.getElementById('findingText').innerHTML =
    `📌 <b>핵심 발견</b><br>
    · 보조 하위15% 기준 경사 보정 후 최저 구: <b>${worst.gu}</b> (${worst.h_o}점)<br>
    · 보조 하위15% 기준 경사 보정 후 최고 구: <b>${bestH.gu}</b> (${bestH.h_o}점)<br>
    · 경사 보정으로 하위15% 점수 최대 감소 구: <b>${maxDrop.gu}</b> (−${maxDrop.drop_h}점)`;
}

// ── 비교 차트 ────────────────────────────────────────────────────────────────
let compareChartObj = null;
const KEY_MAP = {
  '노인':   {x:'n_x', o:'n_o'},
  '보행보조':{x:'b_x', o:'b_o'},
  '하위15': {x:'h_x', o:'h_o'},
};
function showChart(type, btn){
  document.querySelectorAll('.tb').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  const ks = KEY_MAP[type];
  const sorted = [...GU].sort((a,b)=>a[ks.o]-b[ks.o]);
  const labels = sorted.map(g=>g.gu);
  const dataX  = sorted.map(g=>g[ks.x]);
  const dataO  = sorted.map(g=>g[ks.o]);

  if(compareChartObj){ compareChartObj.destroy(); compareChartObj=null; }
  compareChartObj = new Chart(document.getElementById('compareChart'),{
    type:'bar',
    data:{
      labels,
      datasets:[
        {label:'경사X', data:dataX, backgroundColor:'rgba(74,144,217,0.75)', borderRadius:3},
        {label:'경사O', data:dataO, backgroundColor:'rgba(224,91,58,0.75)',  borderRadius:3},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{
        legend:{position:'top',labels:{font:{size:11},boxWidth:12}},
        tooltip:{callbacks:{label:c=>` ${parseFloat(c.raw).toFixed(1)}점`}}
      },
      scales:{
        x:{ticks:{font:{size:10}},grid:{display:false}},
        y:{min:0,max:105,
           grid:{color:'#f1efe8'},
           title:{display:true,text:'도달가능점수 (%)',font:{size:10}}}
      }
    }
  });
}

// ── 감소량 차트 ──────────────────────────────────────────────────────────────
function renderDropCharts(){
  const sorted = [...GU].sort((a,b)=>b.drop_h-a.drop_h);
  const labels = sorted.map(g=>g.gu);

  // 보조기기 vs 하위15%
  new Chart(document.getElementById('dropChart'),{
    type:'bar',
    data:{
      labels,
      datasets:[
        {label:'보조기기 감소', data:sorted.map(g=>g.drop_b),
         backgroundColor:'rgba(255,152,0,0.75)', borderRadius:3},
        {label:'하위15% 감소', data:sorted.map(g=>g.drop_h),
         backgroundColor:'rgba(244,67,54,0.75)', borderRadius:3},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{font:{size:10},boxWidth:10}},
               tooltip:{callbacks:{label:c=>` −${parseFloat(c.raw).toFixed(1)}점`}}},
      scales:{x:{ticks:{font:{size:9}},grid:{display:false}},
              y:{grid:{color:'#f1efe8'},
                 title:{display:true,text:'점수 감소량 (점)',font:{size:10}}}}
    }
  });

  // 3개 유형 동시
  new Chart(document.getElementById('drop3Chart'),{
    type:'bar',
    data:{
      labels,
      datasets:[
        {label:'노인 감소',    data:sorted.map(g=>g.drop_n),
         backgroundColor:'rgba(76,175,80,0.7)', borderRadius:3},
        {label:'보조기기 감소', data:sorted.map(g=>g.drop_b),
         backgroundColor:'rgba(255,152,0,0.7)', borderRadius:3},
        {label:'하위15% 감소', data:sorted.map(g=>g.drop_h),
         backgroundColor:'rgba(244,67,54,0.7)', borderRadius:3},
      ]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{font:{size:10},boxWidth:10}},
               tooltip:{callbacks:{label:c=>` −${parseFloat(c.raw).toFixed(1)}점`}}},
      scales:{x:{ticks:{font:{size:9}},grid:{display:false}},
              y:{grid:{color:'#f1efe8'},
                 title:{display:true,text:'점수 감소량 (점)',font:{size:10}}}}
    }
  });

  // 노트
  const worst = sorted[0];
  const avg_h = (GU.reduce((s,g)=>s+g.drop_h,0)/GU.length).toFixed(1);
  document.getElementById('dropNote').innerHTML =
    `⚠️ 경사 보정 감소량이 클수록 지역 지형이 노인 접근성에 미치는 영향이 큽니다.<br>
    · 서울 평균: 하위15% 기준 경사 보정 시 <b>−${avg_h}점</b> 감소<br>
    · 가장 큰 영향: <b>${worst.gu}</b> (하위15% −${worst.drop_h}점, 보조기기 −${worst.drop_b}점, 노인 −${worst.drop_n}점)`;
}

// ── 종합 테이블 ──────────────────────────────────────────────────────────────
function renderTable(){
  function pill(v){
    if(v===null) return '<span class="pill" style="background:#eee;color:#666">N/A</span>';
    const cls=v>=80?'phi':v>=50?'pmd':'plo';
    return `<span class="pill ${cls}">${v.toFixed(1)}</span>`;
  }
  function dropCell(v){
    const cls = v>=10?'drop-hi':'drop-lo';
    return `<span class="${cls}">−${v.toFixed(1)}</span>`;
  }

  const rows = GU.map(g=>`<tr>
    <td>${g.gu}</td>
    <td>${pill(g.n_x)}</td><td>${pill(g.n_o)}</td>
    <td>${dropCell(g.drop_n)}</td>
    <td>${pill(g.b_x)}</td><td>${pill(g.b_o)}</td>
    <td>${dropCell(g.drop_b)}</td>
    <td>${pill(g.h_x)}</td><td>${pill(g.h_o)}</td>
    <td>${dropCell(g.drop_h)}</td>
  </tr>`).join('');

  document.getElementById('mainTable').innerHTML=`
    <thead>
      <tr>
        <th rowspan="2">구명</th>
        <th colspan="3" style="text-align:center;border-left:1px solid #e0e0e0">🧓 일반 노인 (1.12)</th>
        <th colspan="3" style="text-align:center;border-left:1px solid #e0e0e0">🦽 보조기기 (0.88)</th>
        <th colspan="3" style="text-align:center;border-left:1px solid #e0e0e0">♿ 하위15% (0.70)</th>
      </tr>
      <tr>
        <th style="border-left:1px solid #e0e0e0">경사X</th><th>경사O</th><th>감소</th>
        <th style="border-left:1px solid #e0e0e0">경사X</th><th>경사O</th><th>감소</th>
        <th style="border-left:1px solid #e0e0e0">경사X</th><th>경사O</th><th>감소</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  `;
}

// ── 초기화 ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{
  renderCards();
  showChart('노인', document.querySelector('.tb'));
  renderDropCharts();
  renderTable();
});
</script>
</body>
</html>"""

HTML = (TEMPLATE
        .replace('__GU_DATA__',  GU_JS)
        .replace('__AVG_DATA__', AVG_JS))

out_path = os.path.join(OUTPUT_DIR, 'conclusion.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)

size_kb = os.path.getsize(out_path) / 1024
print("\n" + "=" * 60)
print("[OK] 생성 완료!")
print(f"   파일: {out_path}")
print(f"   크기: {size_kb:.0f} KB")
print("=" * 60)
