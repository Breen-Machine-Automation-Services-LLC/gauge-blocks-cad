#!/bin/sh
# Read the common settings before launching the converter.
SETTINGS_MODULE="$(dirname "$0")/settings.py"
CAD_PYTHON="${CAD_DATASET_PYTHON:-python3}"
CAD_PYTHON="$("$CAD_PYTHON" "$SETTINGS_MODULE" python)"
ODA_APP="$("$CAD_PYTHON" "$SETTINGS_MODULE" oda_app)"
exec xvfb-run -a -n "$((100 + $$))" env "LD_PRELOAD=$ODA_IDENTITY_LIB" "$ODA_APP" "$@"
