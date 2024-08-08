#!/bin/bash
# cleanup all temporary files, venv, builds, etc

# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

APP_NAME="Althea"
APP_NAME_LOWER="althea"
VENV_NAME="venv"

##### Helper Functions

function bail() {
	echo "script exited with error"
	exit 1
}

function delete_folder() {
    # Delete a folder recursively, ensuring it first exists and is relative to the current directory
    local folder_path="./$1"

    if [ -d "$folder_path" ]; then
        echo "Removing folder: $folder_path"
        if [ "$(uname -s)" == "Darwin" ] || [ "$(uname -s)" == "Linux" ]; then
            rm -r "${folder_path}" || bail "Failed to delete folder!"
        else
            # on windows (git bash), "rm -r" is suuuuuuuuper slow, this is a workaround
            find $folder_path -type d,f -delete || bail "Failed to delete folder!"
        fi
    else
        echo "Path does not exist: $folder_path"
    fi
}

function delete_file() {
    # Delete file, ensuring it first exists and is relative to the current directory
    local file_path="./$1"

    if [ -f "$file_path" ]; then
        echo "Removing file: $file_path"
        rm "${file_path}" || bail "Failed to delete file!"
    else
        echo "Path does not exist: $file_path"
    fi
}

###### Entrypoint

echo "Cleaning temporary files"

delete_folder "__pycache__"
delete_folder "${APP_NAME_LOWER}/__pycache__"
delete_folder "${APP_NAME_LOWER}/config/__pycache__"
delete_folder "${APP_NAME_LOWER}/nodes/__pycache__"
delete_folder "${APP_NAME_LOWER}/panes/__pycache__"
delete_folder "${APP_NAME_LOWER}/ui/__pycache__"
delete_folder "${APP_NAME_LOWER}/vartypes/__pycache__"
delete_folder "${VENV_NAME}"
delete_folder "dist"

delete_file "${APP_NAME}.ini"
delete_file "${APP_NAME}.json"
delete_file "${APP_NAME}-AppConfig.json"
delete_file "commit_id"
delete_file "imgui.ini"

echo "Clean completed"
