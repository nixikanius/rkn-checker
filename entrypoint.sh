#!/bin/sh
if [ ! -z "${REGISTRY_URL}" ]; then
    python check.py --registry-url=${REGISTRY_URL} fetch
else
    python check.py fetch
fi

python check.py check "$@"
