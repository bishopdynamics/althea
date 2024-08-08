#!/bin/bash
# create python virtualenv with all the modules this app requires

# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

VENV_NAME='venv'


# figure out platform specific details
if [ "$(uname -s)" == "Darwin" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  PY_CMD='python3.12'
elif [ "$(uname -s)" == "Linux" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  PY_CMD='python3.12'
else
  # assume Windows, as actual output will be something like: MINGW64_NT-10.0-19045
  SCR_ACTIVATE="${VENV_NAME}/Scripts/activate"
  PY_CMD='python'
fi

function bail() {
	echo "An unexpected error occurred"
	exit 1
}

$PY_CMD --version || {
  echo "Failed to find python: ${PY_CMD}"
  exit 1
}

function announce() {
  # sometimes you just need a message to be more noticable in the output
  echo ""
  echo "############# $* ##################"
  echo ""
}

# clear any existing virtualenv
if [ -d "$VENV_NAME" ]; then
	announce "removing existing $VENV_NAME"
	rm -r "$VENV_NAME" || bail
fi

announce "checking for virtualenv module"
$PY_CMD -m venv -h >/dev/null || {
  # no virtualenv module, try to install it
  announce "virtualenv module not found, trying to install it for you"
  # always upgrade to latest pip
  $PY_CMD -m pip install --upgrade pip || {
    announce "something went wrong while upgrading pip!"
    echo "try manually: $PY_CMD -m pip install --upgrade pip"
    bail
  }
	$PY_CMD -m pip install venv || {
    announce "something went wrong while trying to install virtualenv module?"
    echo "try manually: $PY_CMD -m pip install virtualenv"
    bail
  }
}

announce "setting up virtualenv"
$PY_CMD -m venv "$VENV_NAME" || {
  announce "failed to create virtualenv, is virtualenv module setup properly?"
  echo "try manually upgrading it: $PY_CMD -m pip install --upgrade virtualenv"
  bail
}

# now activate the venv so we can install stuff inside it

source "$SCR_ACTIVATE" || bail



# install this apps requirements
announce "installing requirements.txt"
pip install -r requirements.txt || bail

# fixes issue by bug in old version
announce "upgrading httplib2"
pip install --upgrade httplib2 || bail

# make sure pyinstaller stuff is latest version
announce "installing pyinstaller requirements"
pip3 install --upgrade PyInstaller pyinstaller-hooks-contrib || bail

deactivate || bail
announce "virtualenv setup complete: $VENV_NAME"
