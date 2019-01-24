#!/bin/env python
"""
 Simple script to parse YAMl and print the results nicely.
 Fails if the YAML does not parse. Or if a file is empty.
 Uses stdin if no file argument.

 Exit Status: -1 on failure

 Usage: 

      python2 yam_check.py [File ...]

"""
from __future__ import print_function

import os
import sys
import pprint
from yaml import load, Loader, dump

def fumpfd(filename, file_descriptor):
    try:
        print(dump(load(file_descriptor, Loader=Loader), default_flow_style=False))
    except Exception as e:
        print("ERROR: {}\n{}\n".format(filename, e), file=sys.stderr)
        sys.exit(1)


if len(sys.argv) < 2:
    fumpfd('-', sys.stdin)
    sys.exit(0)

for filename in sys.argv[1:]:
    statinfo = os.stat(filename)
    if statinfo.st_size == 0:
        print("ERROR: empty file {}".format(filename), file=sys.stderr)
        sys.exit(1)
    file_descriptor = open(filename)
    fumpfd(filename, file_descriptor)

