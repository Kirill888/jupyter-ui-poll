#!/bin/bash

env_dir="${1:-env}"
python3 -m venv "${env_dir}"
source "${env_dir}/bin/activate"
pip install -U pip
pip install -e .
pip install jupyter jupyterlab ipyleaflet
jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager
jupyter labextension install --no-build jupyter-leaflet
jupyter lab build
