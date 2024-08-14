#!/usr/bin/env bash

python3 -m venv .venv

source .venv/bin/activate

which python3

python3 -m pip install --upgrade pip

python3 -m pip install --upgrade -r requirements.txt

# env

pytest -v -s .
