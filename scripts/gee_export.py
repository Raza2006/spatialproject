"""
GEE Export Functions for LULC Change Analysis

Provides functions for:
- Authenticating and initializing GEE
- Creating annual LULC composites from Dynamic World V1
- Server-side computation of zonal statistics (Tier 1)
- Exporting rasters at various scales (Tier 2 & 3)
- DEM export
"""

import ee
import json
import pandas as pd
import time
from pathlib import Path


def authenticate_gee(project_id=None):
    """
    Authenticate and initialize Google Earth Engine.
    
    Args:
        project_id: GEE Cloud project ID. If None, uses default.
    """
    try:
        ee.Initialize(project=project_id)
        print("✅ GEE already initialized.")
    except Exception:
        print("🔑 Authenticating with GEE...")
        ee.Authenticate()
        ee.Initialize(project=project_id)
        print("✅ GEE authenticated and initialized.")


def get_state_boundary(state_gaul_name, level="level1"):
    """
    Get state or district boundaries from FAO GAUL dataset.
    
    Args:
        state_gaul_name: State name as it appears in GAUL (e.g., 'Maharashtra')
        level: 'level1' for state boundary, 'level2' for districts
        
    Returns:
        ee.FeatureCollection
    """
    if level == "level1":
        asset = "FAO/GAUL/2015/level1"
        fc = ee.FeatureCollection(asset).filter(
            ee.Filter.eq('ADM1_NAME', state_gaul_name)
        )
    else:
        asset = "FAO/GAUL/2015/level2"
        fc = ee.FeatureCollection(asset).filter(
            ee.Filter.eq('ADM1_NAME', state_gaul_name)
        )
    return fc


def make_annual_composite(year, roi):
    """
    Create an annual LULC mode composite from Dynamic World V1.
    
    Uses the 'label' band and takes the mode (most frequent class)
    across all available scenes in the year.
    
    Args:
        year: Integer year (e.g., 2016)
        roi: ee.Geometry or ee.FeatureCollection for spatial filter
        
    Returns:
        ee.Image with single 'label' band (uint8, values 0-8)
    """
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
    
    composite = (
        dw.filterDate(f'{year}-01-01', f'{year}-12-31')
          .filterBounds(roi)
          .select('label')
          .mode()
          .clipToCollection(roi if isinstance(roi, ee.FeatureCollection) 
                           else ee.FeatureCollection([ee.Feature(roi)]))
          .toUint8()
    )
    
    return composite


# ================================================================
# TIER 1: Server-Side Computation (10m native, export as CSV)
# ================================================================

def compute_state_composition(composite, state_fc, scale=10):
    """
    Compute LULC class pixel counts for the entire state (server-side).
    
    Args:
        composite: ee.Image — annual LULC composite
        state_fc: ee.FeatureCollection — state boundary
        scale: Resolution in meters (default 10m)
        
    Returns:
        dict: {class_value: pixel_count}
    """
    histogram = composite.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=state_fc.geometry(),
        scale=scale,
        maxPixels=1e13
    )
    return histogram.getInfo()


def compute_district_composition(composite, district_fc, scale=10):
    """
    Compute LULC class pixel counts per district (server-side).
    
    Args:
        composite: ee.Image — annual LULC composite
        district_fc: ee.FeatureCollection — district boundaries
        scale: Resolution in meters
        
    Returns:
        ee.FeatureCollection with frequencyHistogram per feature
    """
    def add_histogram(feature):
        hist = composite.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=feature.geometry(),
            scale=scale,
            maxPixels=1e13
        )
        return feature.set('lulc_histogram', hist.get('label'))
    
    result = district_fc.map(add_histogram)
    return result


def compute_transition_matrix_state(composite_t1, composite_t2, state_fc, scale=10):
    """
    Compute state-level transition matrix between two years (server-side).
    
    Creates a combined image: change_code = t1 * 10 + t2
    Then computes frequency histogram of all transition codes.
    
    Args:
        composite_t1: ee.Image — LULC for year 1
        composite_t2: ee.Image — LULC for year 2
        state_fc: ee.FeatureCollection — state boundary
        scale: Resolution in meters
        
    Returns:
        dict: {transition_code: pixel_count}
    """
    change_img = composite_t1.multiply(10).add(composite_t2).rename('transition')
    
    histogram = change_img.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=state_fc.geometry(),
        scale=scale,
        maxPixels=1e13
    )
    return histogram.getInfo()


def compute_transition_matrix_districts(composite_t1, composite_t2, district_fc, scale=10):
    """
    Compute district-level transition matrices (server-side).
    
    Args:
        composite_t1, composite_t2: ee.Image — LULC composites
        district_fc: ee.FeatureCollection — district boundaries
        scale: Resolution in meters
        
    Returns:
        ee.FeatureCollection with transition histogram per feature
    """
    change_img = composite_t1.multiply(10).add(composite_t2).rename('transition')
    
    def add_transition_hist(feature):
        hist = change_img.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=feature.geometry(),
            scale=scale,
            maxPixels=1e13
        )
        return feature.set('transition_histogram', hist.get('transition'))
    
    result = district_fc.map(add_transition_hist)
    return result


def compute_buffer_zone_stats(composite, buffer_fc, scale=10):
    """
    Compute LULC composition within buffer zones (server-side).
    
    Args:
        composite: ee.Image — LULC composite
        buffer_fc: ee.FeatureCollection — buffer ring polygons
        scale: Resolution in meters
        
    Returns:
        ee.FeatureCollection with LULC histograms per buffer ring
    """
    def add_buffer_hist(feature):
        hist = composite.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=feature.geometry(),
            scale=scale,
            maxPixels=1e13
        )
        return feature.set('lulc_histogram', hist.get('label'))
    
    result = buffer_fc.map(add_buffer_hist)
    return result


def compute_grid_change_intensity(composite_t1, composite_t2, grid_fc, scale=10):
    """
    Compute change intensity per grid cell (server-side, for hotspot analysis).
    
    change_intensity = count of changed pixels / total pixels in cell
    
    Args:
        composite_t1, composite_t2: ee.Image — LULC composites
        grid_fc: ee.FeatureCollection — grid cells
        scale: Resolution in meters
        
    Returns:
        ee.FeatureCollection with change_intensity per cell
    """
    changed = composite_t1.neq(composite_t2).rename('changed')
    total = composite_t1.gte(0).rename('total')  # All valid pixels
    
    combined = changed.addBands(total)
    
    def add_change_stats(feature):
        stats = combined.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=feature.geometry(),
            scale=scale,
            maxPixels=1e13
        )
        changed_px = ee.Number(stats.get('changed'))
        total_px = ee.Number(stats.get('total'))
        intensity = changed_px.divide(total_px.max(1))  # Avoid division by zero
        return feature.set({
            'changed_pixels': changed_px,
            'total_pixels': total_px,
            'change_intensity': intensity
        })
    
    result = grid_fc.map(add_change_stats)
    return result


# ================================================================
# TIER 2 & 3: Raster Export Functions
# ================================================================

def export_raster_to_drive(image, description, region, scale, 
                           folder="LULC_Exports", crs="EPSG:4326"):
    """
    Export an ee.Image to Google Drive as a GeoTIFF.
    
    Args:
        image: ee.Image to export
        description: Export task description/filename
        region: ee.Geometry — export region
        scale: Resolution in meters
        folder: Google Drive folder name
        crs: Coordinate reference system
        
    Returns:
        ee.batch.Task
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        region=region,
        scale=scale,
        crs=crs,
        fileFormat='GeoTIFF',
        formatOptions={'cloudOptimized': True},
        maxPixels=1e13
    )
    task.start()
    print(f"📤 Export started: {description} (scale={scale}m)")
    return task


def export_feature_collection_to_drive(fc, description, folder="LULC_Exports",
                                       file_format="GeoJSON"):
    """
    Export a FeatureCollection to Google Drive.
    
    Args:
        fc: ee.FeatureCollection to export
        description: Export task description/filename
        folder: Google Drive folder name
        file_format: 'GeoJSON', 'SHP', or 'CSV'
        
    Returns:
        ee.batch.Task
    """
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=description,
        folder=folder,
        fileFormat=file_format
    )
    task.start()
    print(f"📤 Export started: {description} ({file_format})")
    return task


def monitor_tasks(tasks, poll_interval=30):
    """
    Monitor running GEE export tasks until all complete.
    
    Args:
        tasks: List of ee.batch.Task objects
        poll_interval: Seconds between status checks
    """
    pending = list(tasks)
    
    while pending:
        still_running = []
        for task in pending:
            status = task.status()
            state = status['state']
            desc = status['description']
            
            if state == 'COMPLETED':
                print(f"  ✅ {desc} — COMPLETED")
            elif state == 'FAILED':
                print(f"  ❌ {desc} — FAILED: {status.get('error_message', 'Unknown error')}")
            elif state in ('READY', 'RUNNING'):
                still_running.append(task)
            else:
                print(f"  ⚠️ {desc} — {state}")
        
        pending = still_running
        
        if pending:
            print(f"\n⏳ {len(pending)} tasks still running... (checking again in {poll_interval}s)")
            time.sleep(poll_interval)
    
    print("\n🏁 All tasks finished.")


# ================================================================
# DEM EXPORT
# ================================================================

def get_srtm_dem(roi):
    """
    Get SRTM DEM and derived slope for a region.
    
    Args:
        roi: ee.FeatureCollection — region of interest
        
    Returns:
        tuple: (elevation ee.Image, slope ee.Image)
    """
    srtm = ee.Image('USGS/SRTMGL1_003').clipToCollection(roi)
    slope = ee.Terrain.slope(srtm).clipToCollection(roi)
    return srtm, slope


# ================================================================
# WATER BODY VECTORIZATION (Tier 1, 10m native)
# ================================================================

def vectorize_water_bodies(composite, state_fc, scale=10):
    """
    Extract water pixels and vectorize into polygons (server-side at 10m).
    
    Args:
        composite: ee.Image — annual LULC composite
        state_fc: ee.FeatureCollection — state boundary
        scale: Resolution in meters
        
    Returns:
        ee.FeatureCollection of water body polygons with area_ha attribute
    """
    water_mask = composite.eq(0).selfMask()
    
    water_vectors = water_mask.reduceToVectors(
        geometry=state_fc.geometry(),
        scale=scale,
        maxPixels=1e13,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='class',
        bestEffort=True
    )
    
    # Add area in hectares
    def add_area(feature):
        area_m2 = feature.geometry().area()
        area_ha = ee.Number(area_m2).divide(10000)
        return feature.set('area_ha', area_ha)
    
    water_vectors = water_vectors.map(add_area)
    return water_vectors


# ================================================================
# GRID CREATION
# ================================================================

def create_square_grid(roi, cell_size_m=5000):
    """
    Create a square grid covering the ROI for hotspot analysis.
    
    Args:
        roi: ee.FeatureCollection — region of interest
        cell_size_m: Grid cell size in meters
        
    Returns:
        ee.FeatureCollection of grid cells
    """
    # Get bounding box
    bounds = roi.geometry().bounds()
    
    # Create grid using ee.FeatureCollection
    grid = bounds.coveringGrid(
        proj=ee.Projection('EPSG:4326').atScale(cell_size_m),
        scale=cell_size_m
    )
    
    # Clip grid to ROI
    def clip_to_roi(cell):
        clipped = cell.geometry().intersection(roi.geometry(), ee.ErrorMargin(100))
        return cell.setGeometry(clipped)
    
    grid = grid.map(clip_to_roi)
    
    # Filter out empty cells
    grid = grid.filter(ee.Filter.gt('', 0))  # placeholder filter
    
    return grid


# ================================================================
# HELPER: Convert GEE FeatureCollection to Pandas DataFrame
# ================================================================

def fc_to_dataframe(fc, columns=None):
    """
    Convert a small GEE FeatureCollection to a Pandas DataFrame.
    
    WARNING: Only use for small collections (< 5000 features).
    For larger collections, export to Drive first.
    
    Args:
        fc: ee.FeatureCollection
        columns: List of property names to include
        
    Returns:
        pd.DataFrame
    """
    features = fc.getInfo()['features']
    
    records = []
    for f in features:
        props = f['properties']
        if columns:
            props = {k: v for k, v in props.items() if k in columns}
        records.append(props)
    
    return pd.DataFrame(records)
