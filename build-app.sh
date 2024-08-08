#!/bin/bash
# Build the app for macos / linux / windows

# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

APP_NAME='Althea'
VENV_NAME='venv'

function bail() {
	echo "An unexpected error occurred"
	exit 1
}

function announce() {
  # for when you want to say something loudly
  MSG="$*"
  echo ""
  echo "####################################################################"
  echo "    $MSG"
  echo "####################################################################"
  echo ""
}

# create venv if missing
if [ ! -d "$VENV_NAME" ]; then
  announce "Rebuilding virtualenv: ${VENV_NAME}"
  ./setup-venv.sh || bail
fi

# figure out platform specific details
if [ "$(uname -s)" == "Darwin" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  SPEC_FILE="${APP_NAME}.macos.spec"
elif [ "$(uname -s)" == "Linux" ]; then
  SCR_ACTIVATE="${VENV_NAME}/bin/activate"
  SPEC_FILE="${APP_NAME}.linux.spec"
else
  # assume Windows, as actual output will be something like: MINGW64_NT-10.0-19045
  SCR_ACTIVATE="${VENV_NAME}/Scripts/activate"
  SPEC_FILE="${APP_NAME}.windows.spec"
fi


source "$SCR_ACTIVATE" || bail


# make sure our build workspace is clean
announce "Cleaning workspace"
rm -rf build dist

# store the current commit id into a file: COMMIT_ID which will end up inside the app under "data"
GIT_COMMIT=$(git rev-parse --short HEAD)
echo "$GIT_COMMIT" > COMMIT_ID
announce "Building from commit: $GIT_COMMIT"


pyinstaller "$SPEC_FILE" || {
  deactivate
  bail
}


# done withbuild, deactivate the venv
announce "Deactivating virtualenv"
deactivate

announce "Cleaning temp workspace"
rm -r 'build' || bail  # clean up temp files
# rm -r "dist/${APP_NAME}" || bail  # clean up temp files



if [ "$(uname -s)" == "Darwin" ]; then
  # on macos, we must properly zip the resulting app in order to distribute it
  ZIP_FILE_NAME="${APP_NAME}_${GIT_COMMIT}.zip"
  announce "Creating archive: ${ZIP_FILE_NAME}"
  pushd 'dist' || bail
  # this command is exactly the same as when you right-click and Compress in the UI
  #   https://superuser.com/questions/505034/compress-files-from-os-x-terminal
  ditto -c -k --sequesterRsrc --keepParent ${APP_NAME}.app "${ZIP_FILE_NAME}" || {
    echo "failed to compress app using \"ditto\" command"
    bail
  }
  popd || bail
fi


if [ "$(uname -s)" == "Darwin" ]; then
  echo "Success, resulting app: \"dist/${APP_NAME}.app"
elif [ "$(uname -s)" == "Linux" ]; then
  echo "Success, resulting binary: \"dist/${APP_NAME}"
else
  # assume Windows
  echo "Success, resulting executable: \"dist/${APP_NAME}.exe"
fi
