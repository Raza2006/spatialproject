"""
Hotspot Analysis Functions

Provides:
- Square grid creation for hotspot analysis
- Getis-Ord Gi* local spatial autocorrelation
- Terrain factor extraction
- Human factor computation
- Regression analysis
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GRID_CELL_SIZE_M, HOTSPOT_SIGNIFICANCE, HOTSPOT_Z_THRESHOLD


def create_local_square_grid(state_gdf, cell_size_m=None, crs_utm=None):
    """
    Create a square grid covering the state boundary.
    
    Args:
        state_gdf: GeoDataFrame with state boundary (single row)
        cell_size_m: Grid cell size in meters (default: from config)
        crs_utm: UTM EPSG code for meter-based grid
        
    Returns:
        gpd.GeoDataFrame with grid cell polygons
    """
    if cell_size_m is None:
        cell_size_m = GRID_CELL_SIZE_M
    
    # Reproject to UTM for meter-based grid
    state_utm = state_gdf.to_crs(epsg=crs_utm)
    bounds = state_utm.total_bounds  # [minx, miny, maxx, maxy]
    
    # Create grid cells
    cells = []
    x = bounds[0]
    while x < bounds[2]:
        y = bounds[1]
        while y < bounds[3]:
            cell = box(x, y, x + cell_size_m, y + cell_size_m)
            cells.append(cell)
            y += cell_size_m
        x += cell_size_m
    
    grid = gpd.GeoDataFrame(geometry=cells, crs=f"EPSG:{crs_utm}")
    
    # Clip to state boundary
    state_geom = state_utm.geometry.unary_union
    grid['geometry'] = grid.geometry.intersection(state_geom)
    
    # Remove empty cells
    grid = grid[~grid.geometry.is_empty].reset_index(drop=True)
    grid['cell_id'] = range(len(grid))
    
    # Calculate cell area
    grid['cell_area_km2'] = grid.geometry.area / 1e6
    
    # Filter out very small edge cells (< 10% of full cell area)
    full_cell_area = (cell_size_m ** 2) / 1e6
    grid = grid[grid['cell_area_km2'] > full_cell_area * 0.1].reset_index(drop=True)
    
    # Convert back to geographic CRS
    grid = grid.to_crs("EPSG:4326")
    
    return grid


def compute_getis_ord_gi_star(grid_gdf, value_column='change_intensity'):
    """
    Compute Getis-Ord Gi* local spatial autocorrelation.
    
    Args:
        grid_gdf: GeoDataFrame with grid cells and value column
        value_column: Column name containing the values to analyze
        
    Returns:
        gpd.GeoDataFrame with added z_score, p_value, and hotspot_class columns
    """
    try:
        import libpysal
        from esda.getisord import G_Local
    except ImportError:
        raise ImportError("Install libpysal and esda: pip install libpysal esda")
    
    result = grid_gdf.copy()
    
    # Build spatial weights matrix (Queen contiguity)
    w = libpysal.weights.Queen.from_dataframe(result)
    w.transform = 'r'  # Row-standardize
    
    # Compute Gi*
    gi = G_Local(result[value_column].values, w, star=True)
    
    result['z_score'] = gi.Zs
    result['p_value'] = gi.p_sim
    
    # Classify hotspot/coldspot
    conditions = [
        (result['z_score'] > HOTSPOT_Z_THRESHOLD) & (result['p_value'] < HOTSPOT_SIGNIFICANCE),
        (result['z_score'] < -HOTSPOT_Z_THRESHOLD) & (result['p_value'] < HOTSPOT_SIGNIFICANCE),
    ]
    choices = ['Hotspot', 'Coldspot']
    result['hotspot_class'] = np.select(conditions, choices, default='Not Significant')
    
    # Confidence levels
    conditions_conf = [
        result['p_value'] < 0.01,
        result['p_value'] < 0.05,
        result['p_value'] < 0.10,
    ]
    choices_conf = ['99% Confidence', '95% Confidence', '90% Confidence']
    result['confidence_level'] = np.select(conditions_conf, choices_conf, default='Not Significant')
    
    return result


def add_terrain_factors(grid_gdf, dem_path=None, slope_path=None):
    """
    Extract mean elevation and slope for each grid cell from DEM rasters.
    
    Args:
        grid_gdf: GeoDataFrame with grid cells
        dem_path: Path to elevation GeoTIFF
        slope_path: Path to slope GeoTIFF
        
    Returns:
        gpd.GeoDataFrame with added elevation_mean and slope_mean columns
    """
    try:
        from rasterstats import zonal_stats
    except ImportError:
        raise ImportError("Install rasterstats: pip install rasterstats")
    
    result = grid_gdf.copy()
    
    if dem_path:
        elev_stats = zonal_stats(result, str(dem_path), stats=['mean'], nodata=-9999)
        result['elevation_mean'] = [s['mean'] for s in elev_stats]
    
    if slope_path:
        slope_stats = zonal_stats(result, str(slope_path), stats=['mean'], nodata=-9999)
        result['slope_mean'] = [s['mean'] for s in slope_stats]
    
    return result


def add_human_factors(grid_gdf, roads_gdf, cities_list, crs_utm):
    """
    Compute human factor variables for each grid cell.
    
    Args:
        grid_gdf: GeoDataFrame with grid cells
        roads_gdf: GeoDataFrame with road network
        cities_list: List of dicts with 'name', 'lat', 'lon'
        crs_utm: UTM EPSG code
        
    Returns:
        gpd.GeoDataFrame with added road_density and distance_to_city columns
    """
    from shapely.geometry import Point
    
    result = grid_gdf.copy()
    
    # Reproject to UTM for distance calculations
    result_utm = result.to_crs(epsg=crs_utm)
    
    # Road density (total road length within cell / cell area)
    if roads_gdf is not None and len(roads_gdf) > 0:
        roads_utm = roads_gdf.to_crs(epsg=crs_utm)
        road_combined = roads_utm.geometry.unary_union
        
        road_densities = []
        for _, cell in result_utm.iterrows():
            try:
                clipped = road_combined.intersection(cell.geometry)
                road_length_km = clipped.length / 1000
                cell_area_km2 = cell.geometry.area / 1e6
                density = road_length_km / cell_area_km2 if cell_area_km2 > 0 else 0
            except Exception:
                density = 0
            road_densities.append(density)
        
        result['road_density_km_per_km2'] = road_densities
    
    # Distance to nearest city
    if cities_list:
        city_points_utm = []
        for city in cities_list:
            pt = gpd.GeoDataFrame(
                geometry=[Point(city['lon'], city['lat'])], crs="EPSG:4326"
            ).to_crs(epsg=crs_utm).geometry.iloc[0]
            city_points_utm.append(pt)
        
        distances = []
        for _, cell in result_utm.iterrows():
            centroid = cell.geometry.centroid
            min_dist = min(centroid.distance(pt) for pt in city_points_utm) / 1000  # km
            distances.append(min_dist)
        
        result['distance_to_city_km'] = distances
    
    return result


def run_regression_analysis(grid_gdf):
    """
    Run multiple regression: change_intensity ~ slope + elevation + road_density + distance_to_city.
    
    Args:
        grid_gdf: GeoDataFrame with all required columns
        
    Returns:
        dict with regression results (coefficients, R², p-values)
    """
    from scipy import stats as scipy_stats
    
    # Prepare data
    required_cols = ['change_intensity', 'slope_mean', 'elevation_mean',
                     'road_density_km_per_km2', 'distance_to_city_km']
    
    df = grid_gdf[required_cols].dropna()
    
    if len(df) < 10:
        return {'error': 'Insufficient data for regression (< 10 complete rows)'}
    
    y = df['change_intensity'].values
    X = df[['slope_mean', 'elevation_mean', 'road_density_km_per_km2', 'distance_to_city_km']].values
    
    # Add constant (intercept)
    X = np.column_stack([np.ones(len(X)), X])
    
    # OLS regression
    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        y_pred = X @ beta
        
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        n = len(y)
        p = X.shape[1]
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p - 1) if n > p + 1 else 0
        
        # Standard errors
        mse = ss_res / (n - p) if n > p else 0
        try:
            var_beta = mse * np.linalg.inv(X.T @ X)
            se = np.sqrt(np.diagonal(var_beta))
            t_stats = beta / se
            p_values = 2 * (1 - scipy_stats.t.cdf(np.abs(t_stats), df=n - p))
        except np.linalg.LinAlgError:
            se = np.full_like(beta, np.nan)
            t_stats = np.full_like(beta, np.nan)
            p_values = np.full_like(beta, np.nan)
        
        var_names = ['intercept', 'slope', 'elevation', 'road_density', 'distance_to_city']
        
        results = {
            'r_squared': r_squared,
            'adj_r_squared': adj_r_squared,
            'n_observations': n,
            'coefficients': {
                name: {
                    'estimate': float(beta[i]),
                    'std_error': float(se[i]),
                    't_statistic': float(t_stats[i]),
                    'p_value': float(p_values[i]),
                }
                for i, name in enumerate(var_names)
            }
        }
        return results
        
    except Exception as e:
        return {'error': str(e)}
