# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "plotman"
copyright = "2021, Eric Altendorf"
author = "Eric Altendorf"

# on_rtd is whether we are on readthedocs.org
on_rtd = os.environ.get("READTHEDOCS", None) == "True"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx-jsonschema",
    "sphinxcontrib.redoc",
    "sphinxcontrib.openapi",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
if not on_rtd:  # only set the theme if we"re building docs locally
    html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# -- Build stuff -------------------------------------------------------------

import collections
import pathlib
import sys

import apispec
import apispec.ext.marshmallow
import desert
import yaml

import plotman.configuration


schema_class = desert.schema_class(plotman.configuration.PlotmanConfig)

spec = apispec.APISpec(
    title="plotman Configuration",
    version=str(plotman.configuration.expected_major_version),
    openapi_version="3.0.2",
    plugins=[apispec.ext.marshmallow.MarshmallowPlugin()],
)

spec.components.schema(
    component_id="plotman Configuration",
    schema=schema_class,
)

yaml.add_representer(
    collections.OrderedDict,
    lambda dumper, data: dumper.represent_dict(
        getattr(data, "viewitems" if sys.version_info < (3,) else "items")()
    ),
    Dumper=yaml.SafeDumper,
)

openapi_path = pathlib.Path(__file__).parent.joinpath("openapi.yaml")

with open(openapi_path, "w") as f:
    yaml.safe_dump(data=spec.to_dict(), stream=f)

redoc = [
    {
        "name": "plotman configuration",
        "page": "api",
        "spec": os.fspath(openapi_path),
        "embed": True,
    },
    # {
    #     'name': 'Example API',
    #     'page': 'example/index',
    #     'spec': 'http://example.com/openapi.yml',
    #     'opts': {
    #         'lazy': False,
    #         'nowarnings': False,
    #         'nohostname': False,
    #         'required-props-first': True,
    #         'expand-responses': ["200", "201"],
    #     }
    # },
]

import json

import marshmallow_jsonschema

json_schema = marshmallow_jsonschema.JSONSchema()
dumped_schema = json_schema.dump(schema_class())
print(dumped_schema)
jsonschema_path = pathlib.Path(__file__).parent.joinpath("jsonschema.json")

with open(jsonschema_path, "w") as f:
    json.dump(obj=dumped_schema, fp=f, indent=4, skipkeys=True)
