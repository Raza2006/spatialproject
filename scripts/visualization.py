"""
Visualization Functions for LULC Change Analysis

Provides plotting helpers for:
- LULC composition charts (bar, pie, heatmap)
- Transition matrix heatmaps & Sankey diagrams
- Choropleth maps
- Water body maps
- Buffer analysis charts
- Urban gradient curves
- Hotspot maps
- Ranking charts (radar, bar)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import seaborn as sns
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LULC_CLASSES, LULC_COLORS, NUM_CLASSES,
    FIGURE_DPI, MAP_FIGSIZE, CHART_FIGSIZE, FIGURES_DIR,
)


def get_lulc_cmap():
    """Get a matplotlib colormap matching Dynamic World LULC colors."""
    colors = [LULC_COLORS[i] for i in range(NUM_CLASSES)]
    return mcolors.ListedColormap(colors)


def get_lulc_legend_patches():
    """Create legend patches for LULC classes."""
    return [
        Patch(facecolor=LULC_COLORS[i], label=LULC_CLASSES[i])
        for i in range(NUM_CLASSES)
    ]


def save_figure(fig, filename, subdir=None):
    """Save figure to the figures directory."""
    if subdir:
        outdir = FIGURES_DIR / subdir
    else:
        outdir = FIGURES_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    filepath = outdir / filename
    fig.savefig(filepath, dpi=FIGURE_DPI, bbox_inches='tight')
    plt.close(fig)
    print(f"📊 Saved: {filepath}")
    return filepath


# ================================================================
# COMPOSITION CHARTS
# ================================================================

def plot_state_composition_bars(composition_df, state_name, years):
    """Stacked bar chart of LULC composition across years."""
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    class_names = [LULC_CLASSES[i] for i in range(NUM_CLASSES)]
    x = np.arange(len(years))
    width = 0.6
    
    bottom = np.zeros(len(years))
    for i, cls in enumerate(class_names):
        values = [composition_df[f'pct_{y}'].iloc[i] for y in years]
        ax.bar(x, values, width, bottom=bottom, label=cls,
               color=LULC_COLORS[i])
        bottom += np.array(values)
    
    ax.set_xlabel('Year')
    ax.set_ylabel('Percentage (%)')
    ax.set_title(f'LULC Composition — {state_name}')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    
    return save_figure(fig, f'{state_name.lower()}_composition_bars.png', 'lulc_maps')


def plot_state_composition_pie(composition_df, state_name, year):
    """Pie chart of LULC composition for a single year."""
    fig, ax = plt.subplots(figsize=(8, 8))
    
    values = composition_df[f'pct_{year}'].values
    labels = composition_df['class_name'].values
    colors = [LULC_COLORS[i] for i in range(NUM_CLASSES)]
    
    # Only show labels for classes > 2%
    labels_display = [l if v > 2 else '' for l, v in zip(labels, values)]
    
    wedges, texts, autotexts = ax.pie(
        values, labels=labels_display, colors=colors,
        autopct=lambda v: f'{v:.1f}%' if v > 2 else '',
        startangle=90, pctdistance=0.85
    )
    ax.set_title(f'LULC Composition — {state_name} ({year})')
    
    return save_figure(fig, f'{state_name.lower()}_pie_{year}.png', 'lulc_maps')


# ================================================================
# TRANSITION MATRIX
# ================================================================

def plot_transition_heatmap(matrix_df, state_name, period_label, unit='km²'):
    """Annotated heatmap of a transition matrix."""
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Log scale for better visibility of small transitions
    data = matrix_df.values
    
    sns.heatmap(
        data, annot=True, fmt='.1f', cmap='YlOrRd',
        xticklabels=matrix_df.columns, yticklabels=matrix_df.index,
        ax=ax, cbar_kws={'label': f'Area ({unit})'},
        linewidths=0.5
    )
    
    ax.set_xlabel(f'To Class ({period_label.split("→")[1].strip()})')
    ax.set_ylabel(f'From Class ({period_label.split("→")[0].strip()})')
    ax.set_title(f'LULC Transition Matrix — {state_name} ({period_label})')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    
    return save_figure(fig, f'{state_name.lower()}_transition_{period_label.replace("→","to").replace(" ","")}.png',
                       'transition_sankey')


def plot_net_change_bars(net_change_df, state_name, period_label):
    """Bar chart of net class changes (gains and losses)."""
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    colors = ['green' if v > 0 else 'red' for v in net_change_df['net_change_km2']]
    
    ax.barh(net_change_df['class_name'], net_change_df['net_change_km2'], color=colors)
    ax.set_xlabel('Net Change (km²)')
    ax.set_title(f'Net LULC Change — {state_name} ({period_label})')
    ax.axvline(x=0, color='black', linewidth=0.8)
    
    return save_figure(fig, f'{state_name.lower()}_net_change_{period_label.replace("→","to").replace(" ","")}.png',
                       'lulc_maps')


# ================================================================
# DISTRICT MAPS
# ================================================================

def plot_district_choropleth(gdf, column, title, cmap='YlOrRd',
                             legend_title=None, state_name=''):
    """Choropleth map of a district-level variable."""
    fig, ax = plt.subplots(figsize=MAP_FIGSIZE)
    
    gdf.plot(column=column, cmap=cmap, legend=True,
             legend_kwds={'label': legend_title or column},
             edgecolor='black', linewidth=0.5, ax=ax)
    
    ax.set_title(title, fontsize=14)
    ax.set_axis_off()
    
    return save_figure(fig, f'{state_name.lower()}_{column}_choropleth.png', 'lulc_maps')


# ================================================================
# WATER BODY CHARTS
# ================================================================

def plot_water_size_distribution(size_table, state_name):
    """Grouped bar chart of water body counts by size class and year."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    years = size_table['year'].unique()
    size_classes = size_table['size_class'].unique()
    x = np.arange(len(size_classes))
    width = 0.25
    
    # Count chart
    for i, year in enumerate(years):
        data = size_table[size_table['year'] == year]
        ax1.bar(x + i * width, data['count'], width, label=str(year))
    
    ax1.set_xlabel('Size Class')
    ax1.set_ylabel('Count')
    ax1.set_title(f'Water Body Count by Size — {state_name}')
    ax1.set_xticks(x + width)
    ax1.set_xticklabels(size_classes, rotation=45, ha='right')
    ax1.legend()
    
    # Area chart
    for i, year in enumerate(years):
        data = size_table[size_table['year'] == year]
        ax2.bar(x + i * width, data['total_area_ha'], width, label=str(year))
    
    ax2.set_xlabel('Size Class')
    ax2.set_ylabel('Total Area (ha)')
    ax2.set_title(f'Water Body Area by Size — {state_name}')
    ax2.set_xticks(x + width)
    ax2.set_xticklabels(size_classes, rotation=45, ha='right')
    ax2.legend()
    
    fig.tight_layout()
    return save_figure(fig, f'{state_name.lower()}_water_size_distribution.png', 'water_analysis')


# ================================================================
# BUFFER ANALYSIS CHARTS
# ================================================================

def plot_buffer_lulc_stacked(ring_composition, state_name, title_prefix='Water Body'):
    """Stacked bar chart: LULC composition per buffer ring per year."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    
    years = sorted(ring_composition['year'].unique())
    rings = ring_composition['ring_label'].unique()
    
    for ax, year in zip(axes, years):
        year_data = ring_composition[ring_composition['year'] == year]
        bottom = np.zeros(len(rings))
        
        for cls_val in range(NUM_CLASSES):
            cls_name = LULC_CLASSES[cls_val]
            if cls_name in year_data.columns:
                values = year_data.set_index('ring_label').loc[rings, cls_name].values
                ax.bar(range(len(rings)), values, bottom=bottom,
                       label=cls_name, color=LULC_COLORS[cls_val])
                bottom += values
        
        ax.set_xlabel('Buffer Ring')
        ax.set_title(f'{year}')
        ax.set_xticks(range(len(rings)))
        ax.set_xticklabels(rings, rotation=45, ha='right')
    
    axes[0].set_ylabel('Area (%)')
    axes[-1].legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    fig.suptitle(f'{title_prefix} Buffer LULC — {state_name}', fontsize=14)
    fig.tight_layout()
    
    return save_figure(fig, f'{state_name.lower()}_{title_prefix.lower().replace(" ","_")}_buffer_lulc.png',
                       'water_analysis')


# ================================================================
# URBAN GRADIENT CURVES
# ================================================================

def plot_urban_density_curve(ring_data, city_name, state_name):
    """Distance vs. urban density curve for a city."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    years = sorted(ring_data['year'].unique())
    
    for year in years:
        data = ring_data[ring_data['year'] == year].sort_values('distance_km')
        ax.plot(data['distance_km'], data['built_pct'], 'o-',
                label=str(year), linewidth=2, markersize=8)
    
    ax.set_xlabel('Distance from City Center (km)')
    ax.set_ylabel('Built-up Area (%)')
    ax.set_title(f'Urban Density Gradient — {city_name}, {state_name}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    return save_figure(fig, f'{state_name.lower()}_{city_name.lower()}_urban_gradient.png',
                       'urban_gradient')


# ================================================================
# HOTSPOT MAPS
# ================================================================

def plot_hotspot_map(grid_gdf, state_name):
    """Hotspot/coldspot map from Gi* analysis."""
    fig, ax = plt.subplots(figsize=MAP_FIGSIZE)
    
    colors = {'Hotspot': '#d73027', 'Coldspot': '#4575b4', 'Not Significant': '#e0e0e0'}
    
    for cls, color in colors.items():
        subset = grid_gdf[grid_gdf['hotspot_class'] == cls]
        if len(subset) > 0:
            subset.plot(ax=ax, color=color, edgecolor='grey',
                       linewidth=0.2, label=cls, alpha=0.8)
    
    ax.set_title(f'LULC Change Hotspots (Gi*) — {state_name}', fontsize=14)
    ax.legend(loc='lower right')
    ax.set_axis_off()
    
    return save_figure(fig, f'{state_name.lower()}_hotspot_map.png', 'hotspot_maps')


# ================================================================
# RANKING CHARTS
# ================================================================

def plot_ranking_bar(ranking_df, state_name):
    """Horizontal bar chart of district rankings."""
    fig, ax = plt.subplots(figsize=(10, max(6, len(ranking_df) * 0.4)))
    
    colors = plt.cm.RdYlGn_r(ranking_df['composite_index'] / ranking_df['composite_index'].max())
    
    ax.barh(ranking_df['district'], ranking_df['composite_index'], color=colors)
    ax.set_xlabel('Composite Change Index')
    ax.set_title(f'District Ranking by Change Intensity — {state_name}')
    ax.invert_yaxis()
    
    return save_figure(fig, f'{state_name.lower()}_ranking_bar.png', 'ranking_charts')


def plot_radar_chart(ranking_df, state_name, top_n=5):
    """Radar/spider chart for top-N districts."""
    top = ranking_df.head(top_n)
    categories = ['Urban Growth', 'Water Loss', 'Veg Decrease']
    norm_cols = ['norm_urban_growth_rate', 'norm_water_loss_pct', 'norm_veg_decrease_pct']
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    
    for _, row in top.iterrows():
        values = [row[c] for c in norm_cols]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=row['district'])
        ax.fill(angles, values, alpha=0.1)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.set_title(f'Top {top_n} Districts — {state_name}', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)
    
    return save_figure(fig, f'{state_name.lower()}_radar_top{top_n}.png', 'ranking_charts')


# ================================================================
# TIME SERIES (Module 3)
# ================================================================

def plot_annual_timeseries(annual_data, district_name, state_name):
    """Line chart of annual LULC class areas."""
    fig, ax = plt.subplots(figsize=CHART_FIGSIZE)
    
    for cls_val in range(NUM_CLASSES):
        cls_name = LULC_CLASSES[cls_val]
        if cls_name in annual_data.columns:
            ax.plot(annual_data['year'], annual_data[cls_name],
                    'o-', label=cls_name, color=LULC_COLORS[cls_val],
                    linewidth=2, markersize=5)
    
    ax.set_xlabel('Year')
    ax.set_ylabel('Area (km²)')
    ax.set_title(f'Annual LULC — {district_name}, {state_name}')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)
    
    return save_figure(fig, f'{state_name.lower()}_{district_name.lower()}_timeseries.png', 'lulc_maps')
