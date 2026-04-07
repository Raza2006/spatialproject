# LULC Change Analysis — Maharashtra & Sikkim (2016, 2020, 2025)

## Overview

This project analyzes land use/land cover (LULC) changes across three time periods (2016, 2020, 2025) for **Maharashtra** and **Sikkim** at state and district levels using Google Dynamic World V1 satellite-derived classification data.

## Analyses Performed

| Module | Analysis |
|--------|----------|
| 1 | Data acquisition from Google Earth Engine |
| 2 | LULC composition & transition matrix (state + district) |
| 3 | Highest-change district — year-wise gradual/abrupt analysis |
| 4 | Water body size classification (6 classes) |
| 5 | Multi-ring buffer LULC changes around major water bodies |
| 6 | Urban expansion via road buffers & growth gradients |
| 7 | Spatial hotspot detection (Getis-Ord Gi*) + terrain/human factors |
| 8 | Comparative district ranking index |
| 9 | Validation via visual checks |
| 10 | Extra analyses (fragmentation, NDVI, Markov prediction) |

## Data Sources

- **LULC**: Google Dynamic World V1 (`GOOGLE/DYNAMICWORLD/V1`) — 10 m Sentinel-2
- **Road Network**: OpenStreetMap via `osmnx`
- **DEM**: SRTM 30 m (`USGS/SRTMGL1_003`)
- **Boundaries**: FAO GAUL Level 2 / geoBoundaries

## Setup

```bash
pip install -r requirements.txt
```

## Project Structure

```
ISSAT_Project/
├── config.py              # Central configuration
├── notebooks/             # Jupyter notebooks (one per module)
├── scripts/               # Reusable Python modules
├── data/                  # Raw & processed data
├── figures/               # Output maps & charts
├── report/                # Final report
└── validation/            # Validation screenshots
```

## Usage

1. Authenticate with Google Earth Engine
2. Run notebooks sequentially: `01_data_acquisition.ipynb` → `10_extra_analysis.ipynb`
3. All outputs are saved to `data/processed/` and `figures/`
