import yaml


def get_path():
    return 'config.yaml'

def load(file):
    cfg = yaml.load(file, Loader=yaml.SafeLoader)
    return cfg
