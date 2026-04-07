"""
Ranking & Composite Index Functions

Provides:
- Indicator computation (urban growth rate, water body loss, vegetation decrease)
- Min-max normalization
- Composite index calculation
- District ranking
"""

import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LULC_CLASSES, VEGETATION_CLASSES


def compute_indicators(district_comp_t1, district_comp_t2, year_t1, year_t2):
    """
    Compute three ranking indicators per district.
    
    1. Urban Growth Rate: (built_t2 - built_t1) / built_t1 * 100
    2. Water Body Loss %: (water_t1 - water_t2) / water_t1 * 100
    3. Vegetation Decrease %: (veg_t1 - veg_t2) / veg_t1 * 100
    """
    df1 = district_comp_t1.set_index('district')
    df2 = district_comp_t2.set_index('district')
    common = df1.index.intersection(df2.index)
    df1, df2 = df1.loc[common], df2.loc[common]
    
    records = []
    veg_classes = ['Trees', 'Grass', 'Shrub & Scrub']
    
    for d in common:
        b1, b2 = df1.loc[d, 'Built Area'], df2.loc[d, 'Built Area']
        w1, w2 = df1.loc[d, 'Water'], df2.loc[d, 'Water']
        v1 = sum(df1.loc[d, c] for c in veg_classes if c in df1.columns)
        v2 = sum(df2.loc[d, c] for c in veg_classes if c in df2.columns)
        
        records.append({
            'district': d,
            'urban_growth_rate': ((b2 - b1) / b1 * 100) if b1 > 0 else 0,
            'water_loss_pct': ((w1 - w2) / w1 * 100) if w1 > 0 else 0,
            'veg_decrease_pct': ((v1 - v2) / v1 * 100) if v1 > 0 else 0,
        })
    return pd.DataFrame(records)


def min_max_normalize(series):
    """Min-max normalization to [0, 1]."""
    mn, mx = series.min(), series.max()
    return pd.Series(0.5, index=series.index) if mx == mn else (series - mn) / (mx - mn)


def compute_composite_index(indicators_df, weights=None):
    """Compute normalized composite index and rank districts."""
    result = indicators_df.copy()
    cols = ['urban_growth_rate', 'water_loss_pct', 'veg_decrease_pct']
    if weights is None:
        weights = {c: 1.0 / len(cols) for c in cols}
    
    for c in cols:
        result[f'norm_{c}'] = min_max_normalize(result[c])
    
    result['composite_index'] = sum(
        result[f'norm_{c}'] * weights[c] for c in cols
    )
    result['rank'] = result['composite_index'].rank(ascending=False).astype(int)
    return result.sort_values('rank').reset_index(drop=True)
