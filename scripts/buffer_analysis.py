"""
Buffer Analysis Functions

Provides:
- Multi-ring buffer creation (water bodies and roads)
- Urban growth gradient ring creation
- Buffer zone LULC extraction
"""

import geopandas as gpd
import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    WATER_BUFFER_DISTANCES_M,
    ROAD_BUFFER_DISTANCES_M,
    URBAN_RING_DISTANCES_M,
)


def create_multi_ring_buffers(geometry, distances_m, crs_utm):
    """
    Create concentric donut-shaped buffer rings around a geometry.
    
    Args:
        geometry: shapely geometry (in geographic CRS, will be reprojected)
        distances_m: List of buffer distances in meters [2000, 4000, 8000, 10000]
        crs_utm: UTM EPSG code for accurate distance calculation
        
    Returns:
        gpd.GeoDataFrame with columns [ring_label, distance_inner, distance_outer, geometry]
    """
    # Create temporary GeoDataFrame for reprojection
    gdf = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")
    gdf_utm = gdf.to_crs(epsg=crs_utm)
    geom_utm = gdf_utm.geometry.iloc[0]
    
    # Create concentric buffers
    buffers = [geom_utm.buffer(d) for d in distances_m]
    
    # Create donut rings
    rings = []
    sorted_distances = sorted(distances_m)
    
    for i, (dist, buf) in enumerate(zip(sorted_distances, buffers)):
        if i == 0:
            ring = buf
            inner_dist = 0
        else:
            ring = buf.difference(buffers[i - 1])
            inner_dist = sorted_distances[i - 1]
        
        rings.append({
            'ring_label': f"{inner_dist/1000:.0f}-{dist/1000:.0f} km",
            'distance_inner_m': inner_dist,
            'distance_outer_m': dist,
            'geometry': ring,
        })
    
    ring_gdf = gpd.GeoDataFrame(rings, crs=f"EPSG:{crs_utm}")
    # Convert back to geographic CRS for GEE compatibility
    ring_gdf = ring_gdf.to_crs("EPSG:4326")
    
    return ring_gdf


def create_water_body_buffers(water_bodies_gdf, crs_utm,
                               distances_m=None):
    """
    Create multi-ring buffers around major water bodies.
    
    Args:
        water_bodies_gdf: GeoDataFrame of water body polygons (>100 ha)
        crs_utm: UTM EPSG code
        distances_m: List of distances (default: [2000, 4000, 8000, 10000])
        
    Returns:
        gpd.GeoDataFrame with buffer rings for all water bodies combined
    """
    if distances_m is None:
        distances_m = WATER_BUFFER_DISTANCES_M
    
    # Dissolve all water bodies into one geometry
    combined = unary_union(water_bodies_gdf.geometry)
    
    # Create rings
    ring_gdf = create_multi_ring_buffers(combined, distances_m, crs_utm)
    
    # Remove the water body area from the inner ring
    ring_gdf_utm = ring_gdf.to_crs(epsg=crs_utm)
    water_utm = gpd.GeoDataFrame(geometry=[combined], crs="EPSG:4326").to_crs(epsg=crs_utm)
    water_geom = water_utm.geometry.iloc[0]
    
    ring_gdf_utm['geometry'] = ring_gdf_utm.geometry.difference(water_geom)
    ring_gdf = ring_gdf_utm.to_crs("EPSG:4326")
    
    return ring_gdf


def create_road_buffers(roads_gdf, crs_utm, distances_m=None):
    """
    Create buffers around the road network.
    
    Args:
        roads_gdf: GeoDataFrame of road geometries
        crs_utm: UTM EPSG code
        distances_m: List of distances (default: [1000, 2000])
        
    Returns:
        gpd.GeoDataFrame with buffer zones
    """
    if distances_m is None:
        distances_m = ROAD_BUFFER_DISTANCES_M
    
    # Dissolve all roads into one geometry
    combined = unary_union(roads_gdf.geometry)
    
    # Create rings
    ring_gdf = create_multi_ring_buffers(combined, distances_m, crs_utm)
    
    return ring_gdf


def create_urban_growth_rings(city_center, crs_utm, distances_m=None):
    """
    Create concentric growth rings around an urban center.
    
    Args:
        city_center: dict with 'lat' and 'lon' keys
        crs_utm: UTM EPSG code
        distances_m: List of ring distances (default: [1000, 3000, 5000])
        
    Returns:
        gpd.GeoDataFrame with ring polygons
    """
    if distances_m is None:
        distances_m = URBAN_RING_DISTANCES_M
    
    center_point = Point(city_center['lon'], city_center['lat'])
    
    ring_gdf = create_multi_ring_buffers(center_point, distances_m, crs_utm)
    ring_gdf['city'] = city_center.get('name', 'Unknown')
    
    return ring_gdf


def create_distance_gradient_samples(roads_gdf, crs_utm, 
                                      max_distance_m=5000, 
                                      interval_m=500,
                                      sample_spacing_m=2000):
    """
    Create sample points at regular distance intervals from roads.
    
    Used for the distance-vs-built-up-density analysis (Module 6).
    
    Args:
        roads_gdf: GeoDataFrame of road geometries
        crs_utm: UTM EPSG code
        max_distance_m: Maximum distance from roads to sample
        interval_m: Distance interval between sampling bands
        sample_spacing_m: Spacing between sample points along roads
        
    Returns:
        gpd.GeoDataFrame with distance bands
    """
    distances = list(range(interval_m, max_distance_m + interval_m, interval_m))
    combined = unary_union(roads_gdf.geometry)
    
    ring_gdf = create_multi_ring_buffers(combined, distances, crs_utm)
    
    return ring_gdf
