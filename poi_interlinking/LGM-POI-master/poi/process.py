import os
import ast
from fuzzywuzzy import fuzz, process
import pandas as pd
import geopandas as gpd
from transliterate import translit
from shapely import wkt

from poi.helpers import detect_alphabet, parse_yaml, header
import poi.config as cfg
from poi.spatial import create_index
from poi.osm_utilities import download_osm_polygons


true_pairs = []
least_false_pairs = []
most_false_pairs = []
no_candidate_match = []


def load_data(f, source_crs, target_crs):
    df = pd.read_csv(os.path.join(cfg.input_path, f))
    gdf_origin = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x, df.y), crs=f'epsg:{source_crs}')
    gdf = gdf_origin.to_crs(f'epsg:{target_crs}')
    if 'geom' in gdf.columns:
        gdf.drop('geom', inplace=True, axis=1)

    return gdf, gdf_origin


def transform_to_crs(df, source_crs, target_crs):
    gdf_origin = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x, df.y), crs=f'epsg:{source_crs}')
    gdf = gdf_origin.to_crs(f'epsg:{target_crs}')
    if 'geom' in gdf.columns:
        gdf.drop('geom', inplace=True, axis=1)

    return gdf, gdf_origin


def best_match(ids, poly, osm_polys, yml_dict):
    scores = []
    name_gscores = []
    tag_gscores = []

    # max_distance = poly.geometry.distance(osm_polys.iloc[ids[-1]].geometry)

    for i, idx in enumerate(ids):
        name_score = 0
        tag_score = 0
        curr_score = -1

        names = osm_polys.iloc[idx]['name']
        # tags = ast.literal_eval(osm_polys.iloc[idx]['tags'])
        tags = osm_polys.iloc[idx]['tags']

        if len(names):
            alphabets = detect_alphabet(names)
            #             if not 'GREEK' in alphabets:
            if len(set(detect_alphabet([poly.name])) & set(alphabets)):
                _, name_score = process.extractOne(poly.name, names, scorer=fuzz.token_set_ratio)
            else:
                trans_names = []
                for n in names:
                    trans_names.append(
                        translit(n, reversed=True) if 'GREEK' in alphabets else translit(n, language_code='el'))
                _, name_score = process.extractOne(poly.name, trans_names, scorer=fuzz.token_set_ratio)
        if len(tags):
            poly_tags = [poly.theme, poly.class_name, poly.subclass_n]
            tag_scores = [0]
            for t in tags:
                if t[0] not in yml_dict['el']['geocoder']['search_osm_nominatim']['prefix'] or \
                        t[1] not in yml_dict['el']['geocoder']['search_osm_nominatim']['prefix'][t[0]]:
                    continue

                tag_scores.append(
                    process.extractOne(yml_dict['el']['geocoder']['search_osm_nominatim']['prefix'][t[0]][t[1]],
                                       poly_tags)[1])

            tag_score = max(tag_scores)
        #         curr_score = (1 - i / (len(ids))) * importance_term1 + (res_names / 100.0) * importance_term2 + (res_tags / 100.0) * importance_term3
        curr_score = tag_score / 100.0 if not len(names) else (name_score / 100.0) * cfg.importance_weights[1] + (
                    tag_score / 100.0) * cfg.importance_weights[2]
        #         curr_score = (name_score / 100.0) * importance_term2 + (tag_score / 100.0) * importance_term3 if name_score > tag_score else max(name_score, tag_score)
        scores.append(curr_score if curr_score >= cfg.thres else -1)
        name_gscores.append(name_score)
        tag_gscores.append(tag_score)

    # return max(enumerate(scores), key=operator.itemgetter(1))
    return scores, name_gscores, tag_gscores


def clear_variables():
    del true_pairs[:]
    del least_false_pairs[:]
    del most_false_pairs[:]
    del no_candidate_match[:]


def coord_lister(gdf):
    coords = list(gdf.geometry.coords)
    gdf['x_4326'] = coords[0][0]
    gdf['y_4326'] = coords[0][1]
    return gdf


def get_candidate_pairs(dataset, yml_file='el.yml'):
    if not os.path.exists(cfg.output_path):
        os.makedirs(cfg.output_path)

    clear_variables()

    eratosthenis_target, eratosthenis_polys_source = load_data(dataset, cfg.eratosthenis_source_crs, cfg.target_crs)
    eratosthenis_4326 = eratosthenis_polys_source.to_crs(f'epsg:4326')
    eratosthenis_4326 = eratosthenis_4326.apply(coord_lister, axis=1)

    osm_polys_df = download_osm_polygons(eratosthenis_4326[[f'x_4326', f'y_4326']].to_numpy())
    osm_target, osm_polys_source = transform_to_crs(osm_polys_df, cfg.source_crs, cfg.target_crs)

    osm_idx = create_index(osm_target)
    yml_dict = parse_yaml(os.path.join(cfg.input_path, yml_file))

    for poly in eratosthenis_target.itertuples():
        closest_polys = list(osm_idx.nearest(poly.geometry.bounds, cfg.knearests))
        tot_scores, name_scores, tag_scores = best_match(closest_polys, poly, osm_target, yml_dict)
        best_id, max_scores = max(enumerate(zip(tot_scores, name_scores, tag_scores)), key=lambda t: t[1][0])

        if max_scores[0] == -1:
            #         print(f'Couldnt find a match for poly with id: {poly.poi_id}')
            no_candidate_match.append(poly.poi_id)
        else:
            found_poly = osm_polys_source.iloc[closest_polys[best_id]]
            true_pairs.append([
                poly.poi_id, poly.name, '|'.join([poly.theme, poly.class_name, poly.subclass_n]),
                eratosthenis_4326[eratosthenis_4326['poi_id'] == poly.poi_id].geometry.apply(wkt.dumps).to_list()[0],
                found_poly['id'], found_poly['name'], found_poly['tags'], found_poly['geometry'].wkt,
                max_scores[0], max_scores[1], max_scores[2],
                poly.geometry.distance(osm_target.iloc[closest_polys[best_id]]['geometry']),
                'True'
            ])

            del closest_polys[best_id]
            del tot_scores[best_id]
            del name_scores[best_id]
            del tag_scores[best_id]

            # # get best score candidate that is False
            # found_poly = osm_4326.iloc[closest_polys[0]]
            # least_false_pairs.append([
            #     poly.poi_id, poly.name, '|'.join([poly.theme, poly.class_name, poly.subclass_n]), poly.geometry.wkt,
            #     found_poly['id'], found_poly['name'], found_poly['tags'], found_poly['geometry'].wkt,
            #     tot_scores[0], name_scores[0], tag_scores[0],
            #     poly.geometry.distance(osm_polys.iloc[closest_polys[0]]['geometry']),
            #     'False'
            # ])
            # # get worst score candidate that is False
            # found_poly = osm_4326.iloc[closest_polys[-1]]
            # most_false_pairs.append([
            #     poly.poi_id, poly.name, '|'.join([poly.theme, poly.class_name, poly.subclass_n]), poly.geometry.wkt,
            #     found_poly['id'], found_poly['name'], found_poly['tags'], found_poly['geometry'].wkt,
            #     tot_scores[-1], name_scores[-1], tag_scores[-1],
            #     poly.geometry.distance(osm_polys.iloc[closest_polys[-1]]['geometry']),
            #     'False'
            # ])

    writer()


def writer():
    foutput = os.path.join('output', 'pois_dataset_pairs.csv')

    final_df = pd.concat([
        pd.DataFrame(true_pairs, columns=header),
        pd.DataFrame(least_false_pairs, columns=header),
        pd.DataFrame(most_false_pairs, columns=header)
    ]).sort_index(kind='mergesort')
    final_df.to_csv(foutput, index=False)

    # print(f'Could not find a match for {len(no_candidate_match)} with the following ids:\n{no_candidate_match}')
