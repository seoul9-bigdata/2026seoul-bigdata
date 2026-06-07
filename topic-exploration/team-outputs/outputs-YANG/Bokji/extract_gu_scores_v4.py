#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_gu_scores_v4.py — 구 단위 도달가능점수 집계 CSV 추출
=============================================================
기준 시간: 30분 고정 (dong_reachability_v4.csv 기준)
도달가능점수 = (선택속도 합산 도달 수 / 일반인 합산 도달 수) × 100
  · 복지시설 + 공원을 합산하여 계산
  · 분모(일반인 도달 수) = 0인 동은 평균 계산에서 제외

출력 컬럼:
  구명, 점수_노인_경사X, 점수_노인_경사O,
  점수_보행보조_경사X, 점수_보행보조_경사O,
  점수_하위15_경사X,  점수_하위15_경사O
"""

import sys, os
import pandas as pd
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
V4_CSV   = os.path.join(BASE_DIR, 'output_v4', 'dong_reachability_v4.csv')
OUT_CSV  = os.path.join(BASE_DIR, 'output_v4', 'gu_scores_v4.csv')

print("=" * 60)
print("extract_gu_scores_v4 — 구 단위 도달가능점수 집계")
print("=" * 60)

# ── 1. 데이터 로드 ────────────────────────────────────────────────────────────
print("\n1. 데이터 로드")
df = pd.read_csv(V4_CSV, encoding='utf-8-sig')
df.columns = [c.strip() for c in df.columns]
print(f"  {len(df)}개 행정동  컬럼: {df.columns.tolist()}")

# ── 2. 노드 유형 합산 (복지 + 공원) ──────────────────────────────────────────
print("\n2. 복지+공원 합산")

# 일반인 기준 합산 (도달가능점수 분모)
df['합산_일반인'] = df['복지_일반인'] + df['공원_일반인']

# 경사 보정 없음 (경사X)
df['합산_노인_X']    = df['복지_일반노인']    + df['공원_일반노인']
df['합산_보행보조_X'] = df['복지_보조기기']    + df['공원_보조기기']
df['합산_하위15_X']  = df['복지_보조하위15p'] + df['공원_보조하위15p']

# 경사 보정 있음 (경사O)
df['합산_노인_O']    = df['복지_일반노인보정']    + df['공원_일반노인보정']
df['합산_보행보조_O'] = df['복지_보조기기보정']    + df['공원_보조기기보정']
df['합산_하위15_O']  = df['복지_보조하위15p보정'] + df['공원_보조하위15p보정']

# ── 3. 동별 도달가능점수 계산 ─────────────────────────────────────────────────
print("\n3. 동별 도달가능점수 계산 (분모=0 → NaN 처리)")

den = df['합산_일반인'].replace(0, np.nan)

df['점수_노인_경사X']    = (df['합산_노인_X']    / den * 100)
df['점수_노인_경사O']    = (df['합산_노인_O']    / den * 100)
df['점수_보행보조_경사X'] = (df['합산_보행보조_X'] / den * 100)
df['점수_보행보조_경사O'] = (df['합산_보행보조_O'] / den * 100)
df['점수_하위15_경사X']  = (df['합산_하위15_X']  / den * 100)
df['점수_하위15_경사O']  = (df['합산_하위15_O']  / den * 100)

score_cols = [
    '점수_노인_경사X', '점수_노인_경사O',
    '점수_보행보조_경사X', '점수_보행보조_경사O',
    '점수_하위15_경사X',  '점수_하위15_경사O',
]
n_na = df['점수_노인_경사X'].isna().sum()
print(f"  분모=0 동 (NaN): {n_na}개  →  구 평균 계산에서 제외")

# ── 4. 구 단위 평균 집계 ──────────────────────────────────────────────────────
print("\n4. 구 단위 평균 집계")

gu_df = (df.groupby('구명')[score_cols]
           .mean()
           .round(1)
           .reset_index())

print(f"  집계 결과: {len(gu_df)}개 구")

# ── 5. 검증 출력 ──────────────────────────────────────────────────────────────
print("\n5. 집계 결과 확인 (점수 오름차순 — 하위15% 경사O 기준)")
check = gu_df.sort_values('점수_하위15_경사O')
print(check.to_string(index=False))

print("\n  경사 보정으로 인한 점수 감소량 (경사X - 경사O, 구 평균)")
for col in ['노인', '보행보조', '하위15']:
    diff = gu_df[f'점수_{col}_경사X'] - gu_df[f'점수_{col}_경사O']
    print(f"  {col}: 평균 {diff.mean():.1f}점  최대 {diff.max():.1f}점 감소")

# ── 6. 저장 ──────────────────────────────────────────────────────────────────
print("\n6. 저장")
gu_df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
size_kb = os.path.getsize(OUT_CSV) / 1024
print(f"  저장: {OUT_CSV}  ({size_kb:.1f} KB)")
print("\n완료! 다음 단계: python generate_conclusion_v4.py")
