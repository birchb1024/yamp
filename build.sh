#!/bin/bash
#
# Build Script for Yamp
#
# Requires
#
#    python, pyyaml,
#    asciidoc, `source-highlight` and the YAML syntax module.
#    docker
#
set -u
set -e

tag=$(git describe --tag)

python test/test_expand_01.py
asciidoc README.asciidoc && mv README.html doc
docker build -t "docker.io/birchb1024/yamp:${tag}" .

printf "Now \'docker push docker.io/birchb1024/yamp:${tag}\'\n"

