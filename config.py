"""
Configuration file for LULC Change Analysis Project
Maharashtra & Sikkim (2016, 2020, 2025)

Central place for all constants, paths, CRS settings, and class mappings.
"""

import os
from pathlib import Path

# ============================================================
# PROJECT PATHS
# ============================================================
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LULC_DIR = RAW_DIR / "lulc"
LULC_10M_DIR = RAW_DIR / "lulc_10m_crops"
BOUNDARIES_DIR = RAW_DIR / "boundaries"
ROADS_DIR = RAW_DIR / "roads"
DEM_DIR = RAW_DIR / "dem"
GEE_EXPORTS_DIR = DATA_DIR / "gee_exports"
PROCESSED_DIR = DATA_DIR / "processed"

# Output directories
FIGURES_DIR = PROJECT_ROOT / "figures"
REPORT_DIR = PROJECT_ROOT / "report"
VALIDATION_DIR = PROJECT_ROOT / "validation"

# ============================================================
# STUDY AREA CONFIGURATION
# ============================================================
STATES = {
    "maharashtra": {
        "name": "Maharashtra",
        "gaul_name": "Maharashtra",  # Name in FAO GAUL dataset
        "num_districts": 36,
        "utm_epsg": 32643,           # UTM Zone 43N
        "center_lat": 19.7515,
        "center_lon": 75.7139,
        "cities": [                   # For urban expansion analysis (Module 6)
            {"name": "Mumbai",     "lat": 19.0760, "lon": 72.8777},
            {"name": "Pune",       "lat": 18.5204, "lon": 73.8567},
            {"name": "Nagpur",     "lat": 21.1458, "lon": 79.0882},
            {"name": "Nashik",     "lat": 19.9975, "lon": 73.7898},
            {"name": "Aurangabad", "lat": 19.8762, "lon": 75.3433},
        ],
    },
    "sikkim": {
        "name": "Sikkim",
        "gaul_name": "Sikkim",
        "num_districts": 6,
        "utm_epsg": 32645,           # UTM Zone 45N
        "center_lat": 27.5330,
        "center_lon": 88.5122,
        "cities": [
            {"name": "Gangtok", "lat": 27.3389, "lon": 88.6065},
            {"name": "Namchi",  "lat": 27.1667, "lon": 88.3500},
        ],
    },
}

# Analysis years
YEARS = [2016, 2020, 2025]

# All years for highest-change district annual analysis (Module 3)
ALL_YEARS = list(range(2016, 2026))  # 2016-2025

# ============================================================
# DYNAMIC WORLD V1 — LULC CLASSES
# ============================================================
DW_ASSET = "GOOGLE/DYNAMICWORLD/V1"

# Class value → label mapping
LULC_CLASSES = {
    0: "Water",
    1: "Trees",
    2: "Grass",
    3: "Flooded Vegetation",
    4: "Crops",
    5: "Shrub & Scrub",
    6: "Built Area",
    7: "Bare Ground",
    8: "Snow & Ice",
}

NUM_CLASSES = len(LULC_CLASSES)

# Color scheme for LULC maps (matching Dynamic World palette)
LULC_COLORS = {
    0: "#419BDF",  # Water — blue
    1: "#397D49",  # Trees — dark green
    2: "#88B053",  # Grass — light green
    3: "#7A87C6",  # Flooded Vegetation — purple-blue
    4: "#E49635",  # Crops — orange
    5: "#DFC35A",  # Shrub & Scrub — yellow
    6: "#C4281B",  # Built Area — red
    7: "#A59B8F",  # Bare Ground — grey-brown
    8: "#B39FE1",  # Snow & Ice — lavender
}

# Vegetation classes (for composite vegetation indicator in Module 8)
VEGETATION_CLASSES = [1, 2, 5]  # Trees, Grass, Shrub & Scrub

# ============================================================
# SRTM DEM
# ============================================================
SRTM_ASSET = "USGS/SRTMGL1_003"

# ============================================================
# ADMINISTRATIVE BOUNDARIES (GEE)
# ============================================================
GAUL_LEVEL1_ASSET = "FAO/GAUL/2015/level1"  # State boundaries
GAUL_LEVEL2_ASSET = "FAO/GAUL/2015/level2"  # District boundaries

# ============================================================
# RESOLUTION SETTINGS (Hybrid Strategy)
# ============================================================

# Tier 1: Server-side computation — uses native 10m inside GEE
TIER1_SCALE = 10  # Native Dynamic World resolution

# Tier 2: Full-state rasters for visualization
TIER2_SCALE = 30  # 30m — 9x fewer pixels than 10m

# Tier 3: Targeted 10m crops (highest-change district, buffer zones)
TIER3_SCALE = 10  # Full resolution for detailed spatial analysis

# Pixel area in m² for each tier
PIXEL_AREA_M2 = {10: 100, 30: 900}  # scale → area in m²
PIXEL_AREA_HA = {10: 0.01, 30: 0.09}  # scale → area in hectares
PIXEL_AREA_KM2 = {10: 1e-4, 30: 9e-4}  # scale → area in km²

# ============================================================
# WATER BODY SIZE CLASSES (Module 4)
# ============================================================
WATER_SIZE_CLASSES = [
    {"label": "Very Small",  "min_ha": 0,   "max_ha": 1},
    {"label": "Small",       "min_ha": 1,   "max_ha": 50},
    {"label": "Medium",      "min_ha": 50,  "max_ha": 100},
    {"label": "Large",       "min_ha": 100, "max_ha": 200},
    {"label": "Very Large",  "min_ha": 200, "max_ha": 300},
    {"label": "Mega",        "min_ha": 300, "max_ha": float('inf')},
]

# Major water body threshold for buffer analysis (Module 5)
MAJOR_WATER_BODY_THRESHOLD_HA = {
    "maharashtra": 100,  # > 100 ha
    "sikkim": 50,        # > 50 ha (fewer large water bodies)
}

# ============================================================
# BUFFER DISTANCES (meters)
# ============================================================

# Module 5: Water body buffers
WATER_BUFFER_DISTANCES_M = [2000, 4000, 8000, 10000]  # 2, 4, 8, 10 km

# Module 6: Road buffers
ROAD_BUFFER_DISTANCES_M = [1000, 2000]  # 1, 2 km

# Module 6: Urban growth gradient rings
URBAN_RING_DISTANCES_M = [1000, 3000, 5000]  # 1, 3, 5 km

# ============================================================
# HOTSPOT ANALYSIS (Module 7)
# ============================================================
GRID_CELL_SIZE_M = 5000  # 5 km grid cells
HOTSPOT_SIGNIFICANCE = 0.05  # p-value threshold
HOTSPOT_Z_THRESHOLD = 1.96   # z-score threshold

# ============================================================
# OSM ROAD FILTERS
# ============================================================
MAJOR_ROAD_TYPES = ['motorway', 'trunk', 'primary', 'secondary']

# ============================================================
# GEE EXPORT SETTINGS
# ============================================================
GEE_DRIVE_FOLDER = "LULC_Exports"  # Google Drive folder for exports
GEE_CRS = "EPSG:4326"
GEE_MAX_PIXELS = 1e13

# ============================================================
# VISUALIZATION SETTINGS
# ============================================================
FIGURE_DPI = 300
FIGURE_FORMAT = "png"
MAP_FIGSIZE = (14, 10)
CHART_FIGSIZE = (12, 6)

# Matplotlib style
import matplotlib
matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'figure.dpi': FIGURE_DPI,
    'savefig.dpi': FIGURE_DPI,
    'savefig.bbox': 'tight',
})
