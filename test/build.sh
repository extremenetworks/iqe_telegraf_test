#!/usr/bin/env bash

python3 -m venv .venv

source .venv/bin/activate

which python3

python3 -m pip install --upgrade pip

python3 -m pip install --upgrade -r requirements.txt

export DEVICE_IP="10.0.20.136"
export SERVER_IP="10.0.20.112"

# env

pytest -v -s .
