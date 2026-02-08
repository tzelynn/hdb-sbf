#!/usr/bin/env python3
"""
Script to find the nearest MRT station to each location in the CSV file
and calculate walking and public transport distances and durations.
Uses Singapore OneMap API for routing and MRT station data.
"""

import requests
import pandas as pd
import time
from math import radians, cos, sin, asin, sqrt
from typing import Tuple, Dict, Optional
import json
from pathlib import Path


def get_onemap_token() -> str:
    with open('.onemap_token') as file:
        token = file.readlines()
    return token[0]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on earth (in meters).
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in meters
    r = 6371000
    return c * r

def get_nearest_mrt(lat: float, lon: float, token: str) -> Optional[Dict]:
    """
    Find the nearest MRT station using OneMap's Nearby Transport API.
    Returns information about the nearest MRT station.
    """
    # OneMap Nearby Transport API endpoint
    nearby_url = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestMrtStops"
    
    params = {
        'latitude': lat,
        'longitude': lon,
        'radius_in_meters': 2000, # Search radius in meters
    }
    
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        response = requests.get(nearby_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            mrt_stations = response.json()
            
            if mrt_stations:
                # The API returns stations sorted by distance
                nearest = mrt_stations[0]
                
                # Calculate actual distance
                station_lat = float(nearest.get('lat', 0))
                station_lon = float(nearest.get('lon', 0))
                
                return {
                    'name': nearest.get('name', 'Unknown MRT'),
                    'latitude': station_lat,
                    'longitude': station_lon,
                    'distance_meters': haversine_distance(lat, lon, station_lat, station_lon),
                    'code': nearest.get('id', ''),
                    'type': nearest.get('type', 'MRT')
                }
    except Exception as e:
        print(f"Error getting nearest MRT: {e}")
    
    return None


def get_route_info_walk(start_lat: float, start_lon: float, end_lat: float, end_lon: float, token: str = None) -> Dict:
    """
    Get routing information from OneMap API.
    """
    url = 'https://www.onemap.gov.sg/api/public/routingsvc/route'
    params = {
        'start': f"{start_lat},{start_lon}",
        'end': f"{end_lat},{end_lon}",
        'routeType': 'walk',
        'numItineraries': 1
    }
    
    headers = {"Authorization": token}
    
    try:
        print('params', params)
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()

            # Extract route information
            route_summary = data.get('route_summary', {})
            return {
                'distance_meters': route_summary.get('total_distance', 0),
                'duration_seconds': route_summary.get('total_time', 0),
                'duration_minutes': round(route_summary.get('total_time', 0) / 60, 1)
            }
    except Exception as e:
        print(f"Error getting route info ({route_type}): {e}")


def get_route_info_pt(start_lat: float, start_lon: float, end_lat: float, end_lon: float, token: str = None) -> Dict:
    """
    Get routing information from OneMap API.
    """
    url = 'https://www.onemap.gov.sg/api/public/routingsvc/route'
    params = {
        'start': f"{start_lat},{start_lon}",
        'end': f"{end_lat},{end_lon}",
        'routeType': 'pt',
        'numItineraries': 1,
        'date': '02-02-2026',
        'time': '12:00:00',
        'mode': 'BUS'
    }
    
    headers = {"Authorization": token}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()

            # Extract route information
            itinerary = data['plan']['itineraries'][0]
            return {
                'duration_seconds': itinerary.get('duration', 0),
                'duration_minutes': round(itinerary.get('duration', 0) / 60, 1)
            }
    except Exception as e:
        print(f"Error getting route info ({route_type}): {e}")


def process_csv(input_file: str, output_file: str):
    """
    Process the CSV file and add nearest MRT station information.
    """
    print("Loading CSV file...")
    df = pd.read_csv(input_file)
    
    # Get OneMap token (optional, for better routing)
    token = get_onemap_token()
    
    # Initialize new columns
    df['Nearest_MRT'] = ''
    df['MRT_Station_Code'] = ''
    df['MRT_Distance_m'] = 0.0
    df['Walk_Distance_m'] = 0.0
    df['Walk_Duration_min'] = 0.0
    df['bus_duration_min'] = 0.0
    
    print("\nProcessing each location...")
    for idx, row in df.iterrows():
        lat = row['Latitude']
        lon = row['Longitude']
        project_name = row['Project Name']
        
        print(f"\nProcessing {idx + 1}/{len(df)}: {project_name}")
        
        # Find nearest MRT using Nearby Transport API
        nearest_mrt = get_nearest_mrt(lat, lon, token)
        
        if nearest_mrt:
            df.at[idx, 'Nearest_MRT'] = nearest_mrt['name']
            df.at[idx, 'MRT_Station_Code'] = nearest_mrt.get('code', '')
            df.at[idx, 'MRT_Distance_m'] = round(nearest_mrt['distance_meters'], 1)
            
            print(f"  Nearest MRT: {nearest_mrt['name']} ({nearest_mrt.get('code', '')}) - {round(nearest_mrt['distance_meters'], 0)}m")
            
            # Get walking route
            print("  Getting walking route...")
            walk_route = get_route_info_walk(lat, lon, nearest_mrt['latitude'], 
                                       nearest_mrt['longitude'], token)
            df.at[idx, 'Walk_Distance_m'] = round(walk_route['distance_meters'], 1)
            df.at[idx, 'Walk_Duration_min'] = walk_route['duration_minutes']
            
            # Get public transport route
            print("  Getting public transport route...")
            time.sleep(0.5)  # Rate limiting
            pt_route = get_route_info_pt(lat, lon, nearest_mrt['latitude'], 
                                     nearest_mrt['longitude'], token)
            df.at[idx, 'bus_duration_min'] = pt_route['duration_minutes']
            
            print(f"  Walking: {walk_route['duration_minutes']} min")
            print(f"  Public Transport: {pt_route['duration_minutes']} min")
        else:
            print(f"  Warning: No MRT station found within search radius")
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.5)
    
    # Save results
    print(f"\nSaving results to {output_file}...")
    df.to_csv(output_file, index=False)
    print("Done!")
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total locations processed: {len(df)}")
    print(f"\nAverage walking time to MRT: {df['Walk_Duration_min'].mean():.1f} minutes")
    print(f"Average public transport time to MRT: {df['bus_duration_min'].mean():.1f} minutes")
    print(f"Average straight-line distance to MRT: {df['MRT_Distance_m'].mean():.0f} meters")
    print("\nClosest to MRT:")
    closest = df.loc[df['MRT_Distance_m'].idxmin()]
    print(f"  {closest['Project Name']}: {closest['MRT_Distance_m']:.0f}m to {closest['Nearest_MRT']}")
    print("\nFarthest from MRT:")
    farthest = df.loc[df['MRT_Distance_m'].idxmax()]
    print(f"  {farthest['Project Name']}: {farthest['MRT_Distance_m']:.0f}m to {farthest['Nearest_MRT']}")


if __name__ == "__main__":
    by_estate_dir = Path('data/by_estate')

    for estate_file in by_estate_dir.rglob('*.csv'):
        print(f'\nProcessing estate file: {estate_file}')
        input_file = str(estate_file)
        output_file = input_file.replace('by_estate', 'by_estate_mrt')
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        if Path(output_file).exists():
            print(f'{output_file} exists, skipping...')
            continue
        process_csv(input_file, output_file)
