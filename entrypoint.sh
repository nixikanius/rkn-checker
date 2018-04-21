#!/bin/sh
if [ ! -z "${REGISTRY_URL}" ]; then
    python checker.py --registry-url=${REGISTRY_URL} fetch
else
    python checker.py fetch
fi

python checker.py check "$@"
