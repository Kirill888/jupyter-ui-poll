#!/bin/bash

env_dir="${1:-env}"
python3 -m venv "${env_dir}"
source "${env_dir}/bin/activate"
pip install -U pip setuptools wheel
pip install -e .
pip install jupyter ipywidgets ipyleaflet

if [ "${2:-notebook}" = "lab" ]; then
  pip install jupyterlab
  jupyter labextension install --no-build @jupyter-widgets/jupyterlab-manager
  jupyter labextension install --no-build jupyter-leaflet
  jupyter lab build
fi
