from alphabet_detector import AlphabetDetector
import yaml


def detect_alphabet(lstr):
    ad = AlphabetDetector()
    lalphabets = []
    for l in lstr:
        ab = ad.detect_alphabet(l)
        if "CYRILLIC" in ab:
            lalphabets.append("CYRILLIC")
        else:
            lalphabets.append(ab.pop() if len(ab) != 0 else 'UND')
    return lalphabets


def parse_yaml(yml_file):
    yml_dict = None

    with open(yml_file, 'r') as stream:
        try:
            yml_dict = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    return yml_dict


header = [
    'geodata_id',
    'geodata_name',
    'geodata_tags',
    'geodata_geom',
    'osm_id',
    'osm_name',
    'osm_tags',
    'osm_geom',
    'tot_score',
    'name_dist',
    'tag_dist',
    'spatial_dist (meters)',
    'status',
]