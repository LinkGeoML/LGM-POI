import os
import pandas as pd
import numpy as np
import json
import requests
from shapely.geometry import LineString, Polygon, Point
import re
import time
from sklearn.cluster import KMeans

import poi.config as cfg


def query_osm_data(query, fpath):
    """
    Queries Overpass API for *query*.

    Args:
        query (str): The query to be passed to API
        fpath (str): File path to write the API response

    Returns:
        None
    """
    status = 0
    try:
        overpass_url = 'http://overpass-api.de/api/interpreter'
        response = requests.get(overpass_url, params={'data': query}).json()
        with open(fpath, 'w', encoding='utf8') as f:
            json.dump(response, f)
    except ValueError:
        print('Overpass api error: Trying again with a greater timeout...')
        time.sleep(3)
        status = 1
    return status


def parse_osm_streets(fpath):
    """
    Parses the API response from *fpath* and converts it to a dataframe.

    Args:
        fpath (str): File path to read

    Returns:
        pandas.DataFrame: Contains all streets as well as their geometries
    """
    # Helper function
    def convert_to_wkt_geometry(row):
        lons = [p['lon'] for p in row['geometry']]
        lats = [p['lat'] for p in row['geometry']]
        if len(lons) < 2 or len(lats) < 2:
            return None
        return LineString(list(zip(lons, lats)))

    with open(fpath, encoding='utf-8') as f:
        streets = json.load(f)['elements']

    data = [(street['id'], street['geometry']) for street in streets]
    cols = ['id', 'geometry']
    street_df = pd.DataFrame(data=data, columns=cols)
    street_df['geometry'] = street_df.apply(convert_to_wkt_geometry, axis=1)
    street_df = street_df.dropna()
    return street_df


def parse_osm_polys(fpath):
    # Helper function
    def extract_name_tags(row):
        names = list(set([tag[1] for tag in row['tags'] if re.search('name', tag[0])]))
        return names

    # Helper function
    def convert_to_wkt_geometry(row):
        lons = [p['lon'] for p in row['geometry']]
        lats = [p['lat'] for p in row['geometry']]
        return Polygon(list(zip(lons, lats)))

    with open(fpath, encoding='utf-8') as f:
        polys = json.load(f)['elements']

    data = []
    for poly in polys:
        coords = []
        if poly['type'] == 'node':
            lon = poly['lon']
            lat = poly['lat']
        else:
            lon = poly['center']['lon']
            lat = poly['center']['lat']
        if 'tags' in poly:
            poly_tags = [(k, v) for k, v in poly['tags'].items()]
            data.append((poly['id'], poly_tags, lon, lat))

    cols = ['id', 'tags', 'x', 'y']
    poly_df = pd.DataFrame(data=data, columns=cols)
    poly_df['name'] = poly_df.apply(extract_name_tags, axis=1)
    # poly_df['geometry'] = poly_df.apply(convert_to_wkt_geometry, axis=1)
    return poly_df


def download_osm_polygons(points):
    labels = cluster_points(points)
    clusters_bboxes = get_clusters_bboxes(points, labels)
    poly_dfs = []
    for cluster, bbox in clusters_bboxes.items():
        print('Getting bbox', cluster + 1, 'out of', len(clusters_bboxes))
        cell_polys_df = download_cell(bbox, os.path.join(cfg.output_path, "osm_polys.json"))
        if cell_polys_df is not None:
            print('Number of polygons:', len(cell_polys_df))
            poly_dfs.append(cell_polys_df)
        else:
            print('Number of polygons:', 0)

    # delete file
    if os.path.exists(os.path.join(cfg.output_path, "osm_polys.json")):
        os.remove(os.path.join(cfg.output_path, "osm_polys.json"))

    poly_df = pd.concat(poly_dfs, ignore_index=True)
    poly_df.drop_duplicates(subset='id', inplace=True)
    poly_df.reset_index(drop=True, inplace=True)
    poly_df.sort_values(by=['id']).to_csv(
        f'{os.path.join(cfg.output_path, "osm_polys.csv")}', columns=poly_df.columns, index=False)
    print(f'Extracted {len(poly_df.index)} unique POIs')

    return poly_df


def download_cell(cell, fpath):
    """
    Downloads *cell* from Overpass API, writes results in *fpath* and then \
    parses them into a pandas.DataFrame.

    Args:
        cell (list): Contains the bounding box coords
        fpath (str): Path to write results and then to read from in order to \
            parse them

    Returns:
        pandas.DataFrame: Contains all street elements included in *cell*
    """
    west, south, east, north = cell
    counter = 0
    status = 1
    while status and (counter < cfg.max_overpass_tries):
        counter += 1
        query = (
            f'[out:json][timeout:{cfg.osm_timeout * counter}][bbox: {south},{west},{north},{east}];'
            # gather results
            # f'[bbox:{bbox_coords[0]},{bbox_coords[1]},{bbox_coords[2]},{bbox_coords[3]}];'
            # 'way(if:is_closed());'
            f'('
                f'node["access"!="private"]["amenity"!="bench"][~"^(amenity|shop|building|leisure|sport|historic|tourism|man_made)$"~"."];'
                f'way["access"!="private"]["amenity"!="bench"][~"^(amenity|shop|leisure|sport|historic|tourism|man_made)$"~"."];'
                f'relation["access"!="private"]["amenity"!="bench"][~"^(amenity|shop|building|leisure|sport|historic|tourism|man_made)$"~"."];'
            f');'
            # f'out geom;'
            f'out center;'
        )
        status = query_osm_data(query, fpath)

    if status:
        print('Overpass api error: Exiting.')
        exit()
    return parse_osm_polys(fpath)


def cluster_points(X):
    """
    Clusters points given in *X*.

    Args:
        X (numpy.ndarray): Contains the points to be clustered

    Returns:
        numpy.ndarray: The predicted clusters labels
    """
    n_clusters = int(cfg.clusters_pct * X.shape[0])
    labels = KMeans(n_clusters=n_clusters, random_state=cfg.seed_no, n_init=10, max_iter=500).fit_predict(X)
    return labels


def get_clusters_bboxes(X, labels):
    """
    Extracts a bounding box for each one of the clusters.

    Args:
        X (numpy.ndarray): Contains the clustered points
        labels (numpy.ndarray): Contains the cluster label for each point in \
            *X*
    Returns:
        dict: Contains the cluster labels as keys and the corresponding \
            bounding box as values
    """
    bboxes = {}
    for i in range(len(set(labels))):
        cluster_points = np.vstack([p for j, p in enumerate(X) if labels[j] == i])
        xmin, ymin = cluster_points.min(axis=0) - cfg.osm_buffer
        xmax, ymax = cluster_points.max(axis=0) + cfg.osm_buffer
        bboxes[i] = [xmin, ymin, xmax, ymax]
    # print({k: v for k, v in sorted(bboxes.items(), key=lambda item: item[1][0])})
    # print(sorted(bboxes.items(), key=lambda item: item[1][1])[0][1][1],
    #       sorted(bboxes.items(), key=lambda item: item[1][0])[0][1][0],
    #       sorted(bboxes.items(), key=lambda item: item[1][3], reverse=True)[0][1][3],
    #       sorted(bboxes.items(), key=lambda item: item[1][2], reverse=True)[0][1][2],)
    return bboxes
