from shapely.geometry import shape
from rtree import index


def create_index(poly_gdf):
    idx = index.Index(interleaved=True)
    for poly in poly_gdf.itertuples():
        idx.insert(poly.Index, shape(poly.geometry).bounds)
    return idx
