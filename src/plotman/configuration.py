import yaml


def load(file):
    cfg = yaml.load(file, Loader=yaml.FullLoader)
