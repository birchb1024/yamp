#
# Yamp Dockerfile
#
# Usage:
#
# $ docker run --rm -u $(id -u):$(id -g) -v "$PWD":/work docker.io/birchb1024/yamp /work/path/to/your.yaml
#
#   using stdin:
#
#   $ echo env | docker run -i --rm -u $(id -u):$(id -g) -v "$PWD":/work docker.io/birchb1024/yamp -
#
# Build:
#
# $ git clone https://github.com/birchb1024/yamp.git
# $ cd yamp
# $ docker build -t yamp .
#
# Debug in the container:
#
# $ docker run -it --entrypoint /bin/bash --rm -u $(id -u):$(id -g) -v "$PWD":/work docker.io/birchb1024/yamp
#
FROM python:2.7-slim-stretch

# Install pre-requisites
RUN pip install pyyaml

# Install the application
ADD doc/*.html /yamp/doc/
ADD src/*.py /yamp/src/
ADD examples /yamp/examples/
ADD test /yamp/test/

# Run a few tests
RUN python /yamp/test/test_expand_01.py

# Specify the runtime
ENTRYPOINT ["/usr/local/bin/python", "/yamp/src/yamp.py"] 