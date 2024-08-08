#!/bin/bash
# test as python script, without building the app

# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

function bail() {
	echo "script exited with error"
	exit 1
}

APP_NAME="Althea"
VENV_NAME="venv"

# figure out platform specific details
if [ "$(uname -s)" == "Darwin" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  PY_CMD='python3'
elif [ "$(uname -s)" == "Linux" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  PY_CMD='python3'
else
  # assume Windows, as actual output will be something like: MINGW64_NT-10.0-19045
  SCR_ACTIVATE="${VENV_NAME}/Scripts/activate"
  PY_CMD='python'
fi


# create venv if missing
if [ ! -d "$VENV_NAME" ]; then
  ./setup-venv.sh || bail
fi

echo "activating virtualenv..."
# we need modules in the venv

source "$SCR_ACTIVATE" || bail

echo "running script..."
$PY_CMD "${APP_NAME}.py" "$@" || {
  deactivate
  bail
}

echo "script exited cleanly"
