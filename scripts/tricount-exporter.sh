#!/bin/sh

set -eu

INSTALL_NAME="tricount-exporter"
APP_HOME="${TRICOUNT_EXPORTER_APP_HOME:-${HOME}/.local/share/${INSTALL_NAME}}"
APP_VENV="${APP_HOME}/venv"
APP_PYTHON="${APP_VENV}/bin/python"
APP_SITE_PACKAGES="$("${APP_PYTHON}" -c 'import site; print(site.getsitepackages()[0])')"

export PYTHONPATH="${APP_SITE_PACKAGES}${PYTHONPATH:+:${PYTHONPATH}}"

exec "${APP_PYTHON}" -m tricount_exporter "$@"
