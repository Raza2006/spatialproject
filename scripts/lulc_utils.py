"""
LULC Utility Functions

Provides:
- Transition matrix construction and formatting
- Area calculations (pixel counts → km², ha)
- Net change computation
- Summary table generation
"""

import numpy as np
import pandas as pd
from pathlib import Path
import json
import sys
import os

# Add project root to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LULC_CLASSES, NUM_CLASSES, PIXEL_AREA_KM2, PIXEL_AREA_HA


# ================================================================
# HISTOGRAM PARSING
# ================================================================

def parse_histogram(histogram_dict, scale=10):
    """
    Parse a GEE frequencyHistogram result into a clean dict.
    
    GEE returns histograms with string keys. This converts them
    to integer class values.
    
    Args:
        histogram_dict: dict from GEE (e.g., {'0': 12345, '1': 67890, ...})
        scale: Resolution in meters (for area conversion)
        
    Returns:
        dict: {class_int: pixel_count}
    """
    if histogram_dict is None:
        return {}
    
    parsed = {}
    for key, count in histogram_dict.items():
        try:
            class_val = int(float(key))
            if 0 <= class_val <= 8:
                parsed[class_val] = int(count)
        except (ValueError, TypeError):
            continue
    return parsed


def histogram_to_area_df(histogram_dict, scale=10, unit='km2'):
    """
    Convert a histogram dict to a DataFrame with area values.
    
    Args:
        histogram_dict: {class_int: pixel_count}
        scale: Resolution in meters
        unit: 'km2' or 'ha'
        
    Returns:
        pd.DataFrame with columns [class_value, class_name, pixel_count, area]
    """
    pixel_area = PIXEL_AREA_KM2[scale] if unit == 'km2' else PIXEL_AREA_HA[scale]
    
    rows = []
    for class_val in range(NUM_CLASSES):
        count = histogram_dict.get(class_val, 0)
        rows.append({
            'class_value': class_val,
            'class_name': LULC_CLASSES[class_val],
            'pixel_count': count,
            'area': count * pixel_area,
        })
    
    df = pd.DataFrame(rows)
    df['percentage'] = df['area'] / df['area'].sum() * 100
    return df


# ================================================================
# COMPOSITION TABLES
# ================================================================

def build_state_composition_table(histograms, state_name, years, scale=10):
    """
    Build a multi-year composition table for a state.
    
    Args:
        histograms: dict {year: histogram_dict}
        state_name: Name of the state
        years: List of years [2016, 2020, 2025]
        scale: Resolution in meters
        
    Returns:
        pd.DataFrame with columns for each year's area and percentage
    """
    all_data = {}
    
    for year in years:
        hist = parse_histogram(histograms.get(year, {}), scale)
        df = histogram_to_area_df(hist, scale)
        all_data[f'area_{year}'] = df['area']
        all_data[f'pct_{year}'] = df['percentage']
    
    result = pd.DataFrame({
        'class_value': range(NUM_CLASSES),
        'class_name': [LULC_CLASSES[i] for i in range(NUM_CLASSES)],
        **all_data
    })
    
    return result


def build_district_composition_table(district_histograms, year, scale=10):
    """
    Build a composition table for all districts in a given year.
    
    Args:
        district_histograms: dict {district_name: histogram_dict}
        year: Year for labeling
        scale: Resolution in meters
        
    Returns:
        pd.DataFrame with rows=districts, columns=class areas (km²)
    """
    records = []
    for district_name, hist in district_histograms.items():
        parsed = parse_histogram(hist, scale)
        row = {'district': district_name}
        total_area = 0
        for class_val in range(NUM_CLASSES):
            area = parsed.get(class_val, 0) * PIXEL_AREA_KM2[scale]
            row[LULC_CLASSES[class_val]] = area
            total_area += area
        row['total_area_km2'] = total_area
        records.append(row)
    
    df = pd.DataFrame(records)
    return df


# ================================================================
# TRANSITION MATRIX
# ================================================================

def parse_transition_histogram(transition_dict, scale=10):
    """
    Parse a transition histogram (from change_code = t1*10 + t2).
    
    Args:
        transition_dict: dict from GEE (e.g., {'12': 5000, '45': 3000, ...})
        scale: Resolution in meters
        
    Returns:
        pd.DataFrame: 9×9 transition matrix (rows=from, cols=to), values in km²
    """
    matrix = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=float)
    pixel_area = PIXEL_AREA_KM2[scale]
    
    if transition_dict is None:
        return pd.DataFrame(
            matrix,
            index=[LULC_CLASSES[i] for i in range(NUM_CLASSES)],
            columns=[LULC_CLASSES[i] for i in range(NUM_CLASSES)]
        )
    
    for code_str, count in transition_dict.items():
        try:
            code = int(float(code_str))
            from_class = code // 10
            to_class = code % 10
            if 0 <= from_class < NUM_CLASSES and 0 <= to_class < NUM_CLASSES:
                matrix[from_class, to_class] = int(count) * pixel_area
        except (ValueError, TypeError):
            continue
    
    df = pd.DataFrame(
        matrix,
        index=[LULC_CLASSES[i] for i in range(NUM_CLASSES)],
        columns=[LULC_CLASSES[i] for i in range(NUM_CLASSES)]
    )
    return df


def compute_net_change(transition_matrix_df):
    """
    Compute net change per class from a transition matrix.
    
    Args:
        transition_matrix_df: pd.DataFrame (9×9 transition matrix in km²)
        
    Returns:
        pd.DataFrame with columns [class_name, gain, loss, net_change, pct_change]
    """
    class_names = list(LULC_CLASSES.values())
    records = []
    
    for i, class_name in enumerate(class_names):
        # Gain = sum of column (others converting TO this class), excluding diagonal
        gain = transition_matrix_df.iloc[:, i].sum() - transition_matrix_df.iloc[i, i]
        # Loss = sum of row (this class converting TO others), excluding diagonal
        loss = transition_matrix_df.iloc[i, :].sum() - transition_matrix_df.iloc[i, i]
        
        net_change = gain - loss
        
        # Base area from t1 (sum of row)
        base_area = transition_matrix_df.iloc[i, :].sum()
        pct_change = (net_change / base_area * 100) if base_area > 0 else 0
        
        records.append({
            'class_name': class_name,
            'gain_km2': gain,
            'loss_km2': loss,
            'net_change_km2': net_change,
            'pct_change': pct_change,
            'base_area_km2': base_area,
        })
    
    return pd.DataFrame(records)


def get_dominant_transition(transition_matrix_df, exclude_diagonal=True):
    """
    Find the dominant (largest area) transition in a matrix.
    
    Args:
        transition_matrix_df: pd.DataFrame (9×9 transition matrix)
        exclude_diagonal: If True, exclude no-change (diagonal) cells
        
    Returns:
        dict: {from_class, to_class, area_km2}
    """
    matrix = transition_matrix_df.values.copy()
    if exclude_diagonal:
        np.fill_diagonal(matrix, 0)
    
    idx = np.unravel_index(np.argmax(matrix), matrix.shape)
    from_class = transition_matrix_df.index[idx[0]]
    to_class = transition_matrix_df.columns[idx[1]]
    area = matrix[idx[0], idx[1]]
    
    return {
        'from_class': from_class,
        'to_class': to_class,
        'area_km2': area,
        'label': f"{from_class} → {to_class}",
    }


def compute_total_change_per_district(district_transitions, scale=10):
    """
    Compute total absolute LULC change per district.
    
    Used to rank districts and identify the highest-change district (Module 3).
    
    Args:
        district_transitions: dict {district_name: transition_histogram_dict}
        scale: Resolution in meters
        
    Returns:
        pd.DataFrame sorted by total_change descending
    """
    records = []
    
    for district_name, hist in district_transitions.items():
        matrix_df = parse_transition_histogram(hist, scale)
        net_df = compute_net_change(matrix_df)
        
        # Total absolute change = sum of all off-diagonal elements
        total_change = matrix_df.values.sum() - np.trace(matrix_df.values)
        
        # Get dominant transition
        dominant = get_dominant_transition(matrix_df)
        
        records.append({
            'district': district_name,
            'total_change_km2': total_change,
            'dominant_transition': dominant['label'],
            'dominant_area_km2': dominant['area_km2'],
            'total_area_km2': matrix_df.values.sum(),
            'change_pct': total_change / matrix_df.values.sum() * 100 if matrix_df.values.sum() > 0 else 0,
        })
    
    df = pd.DataFrame(records).sort_values('total_change_km2', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)
    return df


# ================================================================
# HELPER: Save/Load Results
# ================================================================

def save_composition_csv(df, filepath):
    """Save composition DataFrame to CSV."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)
    print(f"💾 Saved: {filepath}")


def save_transition_matrix_csv(matrix_df, filepath):
    """Save transition matrix to CSV (with row/column headers)."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    matrix_df.to_csv(filepath)
    print(f"💾 Saved: {filepath}")


def load_transition_matrix_csv(filepath):
    """Load transition matrix from CSV."""
    return pd.read_csv(filepath, index_col=0)
