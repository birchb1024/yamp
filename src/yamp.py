#!/bin/env python
"""

 Python 2.7 Script to 

"""
from __future__ import print_function

import os
import sys
import pprint
from yaml import load, Loader, dump, load_all


def new_macro(tree, bindings):
#    pprint.pprint(tree)
    name = tree['name']
    body = tree['value']
    def apply(args):
        # pprint.pprint("to apply: {} to {} with {}".format(name, args, bindings))
        macro_env = bindings.copy()
        macro_env.update(args)
        return expand(body, macro_env)
    return apply

def expand(tree, bindings):
    """
    Recursivley substitute values in the symbol table bindings
    Return a new tree

    """
    #pprint.pprint([tree, bindings])
    if type(tree) == str:
        if tree in bindings:
            return expand(bindings[tree], bindings)
        else:
            return tree
    elif type(tree) == list:
        newlist = []
        for item in tree:
            expanded = expand(item, bindings)
            if expanded: newlist.append(expand(expanded, bindings))
        return newlist
    elif type(tree) == dict:
        newdict = {}
        if 'define' in tree.keys():
            if 'name' not in tree['define'] or 'value' not in tree['define']:
                raise(Exception('Syntax error in {}'.format(tree)))
            bindings[tree['define']['name']] = tree['define']['value']
            #pprint.pprint(bindings)
            return None
        if 'defmacro' in tree.keys():
            for required in ['name', 'args', 'value']:
                if required not in tree['defmacro']:
                    raise(Exception('Syntax error {} missing in {}'.format(tree)))
            bindings[tree['defmacro']['name']] = new_macro(tree['defmacro'], bindings)
            #pprint.pprint(bindings)
            return None
        for k,v in tree.iteritems():
            new_k = expand(k, bindings)
            if new_k in newdict:
                print('ERROR: name collision after expansion of {} with {}'.format(k, newdict), file=sys.stderr)
                sys.exit(1)
            if type(new_k) == type(expand):
                return(expand(new_k(v), bindings))
            newdict[new_k] = expand(v, bindings)
        return newdict
    else:
        return tree

assert(expand('FOO', {'FOO':12, 'BAR': 22}) == 12)
assert(expand(['FOO'], {'FOO':12, 'BAR': 22}) == [12])
assert(expand({'FOO': 'bar'}, {'FOO':12, 'BAR': 22}) == {12: 'bar'})
assert(expand({'quux': {'FOO': 'bar'}}, {'FOO':12, 'BAR': 22}) == {'quux': {12: 'bar'}})
assert(expand([{'quux': {'FOO': 'bar'}}], {'FOO':12, 'BAR': 22}) == [{'quux': {12: 'bar'}}])
try:
    expand([{'quux': {'FOO': 'bar', 'BAR' : 89}}], {'FOO': 'BAR', 'BAR': 22})
except:
    pass

if len(sys.argv) < 2:
    print('ERROR: no files to scan', file=sys.stderr)
    sys.exit(1)

global_environment = {'PIPELINE_NAME': 'Hello_World_{}',
            'GROUP_COUNTER': 'Group_{}'}

for filename in sys.argv[1:]:
    statinfo = os.stat(filename)
    if statinfo.st_size == 0:
        print("ERROR: empty file {}".format(filename), file=sys.stderr)
        sys.exit(1)
#    try:
    docs = load_all(open(filename), Loader=Loader)
    for tree in docs:
        expanded_tree = expand(tree, global_environment)
        print('---')
        print(dump(expanded_tree, default_flow_style=False))
#    except Exception as e:
#        print("ERROR: {}\n{}\n".format(filename, e), file=sys.stderr)
#        sys.exit(1)


