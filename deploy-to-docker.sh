#!/bin/sh

if [ $# -eq 0 ]; then
  echo "Usage: $0 TOKEN"
  exit 0
fi

curl -H "Content-Type: application/json" --data '&#123;"build": true&#125;' -X POST https://registry.hub.docker.com/u/chimecms/chime/trigger/${1}/
