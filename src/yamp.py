#!/bin/env python
"""

 Python 2.7 Script to expand YAML macros

"""
from __future__ import print_function

import os

import re
import sys
from pprint import pprint as pp
import numbers
from yaml import load, Loader, dump, load_all

def pp(ignore):
    pass


def interpolate(astring, bindings):
    pp(('**** int', astring))
    if type(astring) != str:
        return astring
    tokens = re.split('({{[^{]*}})', astring)
    rebound  = []
    for tok in tokens:
        value = tok
        if tok.startswith('{{') and tok.endswith('}}'):
            variable_name = tok[2:][:-2]
            value = expand_str(variable_name, bindings)
            if value == variable_name:
                raise(Exception('Undefined interpolation variable {} in {}'.format(variable_name, astring)))
        rebound.append(str(value))
    return(''.join(rebound))

def lookup(env, key):
    while True:
        if key in env:
            return (env[key],)
        elif '__parent__' in env:
            env = env['__parent__']
            continue
        else:
            return None

def new_macro(tree, bindings):
#    pprint.pprint(tree)
    name = tree['name']
    body = tree['value']
    parameters = tree['args'] or []
    def apply(args):
        # pprint.pprint("to apply: {} to {} with {}".format(name, args, bindings))
        # pprint.pprint(('**apply', name, parameters, args))
        if args and type(args) != dict:
            raise(Exception('Expecting dict args for {}, got: {}'.format(name, args)))
        if len(parameters) == 0  and args:
            raise(Exception('Too many args for {}: {}'.format(name, args)))
        if parameters and args:
            if set(parameters or []) != set(args.keys()):
                raise(Exception('Argument mismatch in {} expected {} got {}'.format(name, parameters, args)))
        macro_env = {'__parent__': bindings}
        if args: # Might be None for no args
            macro_env.update(args)
        return expand(body, macro_env)
    return apply


def subvar_lookup(original, vars_list, tree, bindings):
    """
    Given ['b', '1' ] , {'b': ['x', 'y']}
        return 'y'
    """
    pp(['*** sl', original, vars_list, tree])
    if len(vars_list) == 0:
        raise(Exception('Subvariable not found in {}'.format(original)))
    if tree == None:
        raise(Exception('Subvariable not found {} in {}'.format(vars_list, original)))

    first = vars_list[0]
    if type(tree) == dict:
        if not first in tree:
            raise(Exception('Subvariable not found {} in {}'.format(first, original)))
        if len(vars_list) == 1: # last one
            return tree[first]
        else:
            return subvar_lookup(original, vars_list[1:], tree[first], bindings)
    elif type(tree) == list:
        if first.isdigit():
            index = int(first)
        elif type(first) == str:
            index = expand(first, bindings)
        else:
            raise(Exception('Subvariable List index not numeric: {} for {} {}'.format(first, original, tree)))
        if len(tree) <= index or index < 0:
            raise(Exception('Subvariable List index out of bounds: {} for {} {}'.format(index, original, tree)))
        if len(vars_list) == 1: # Last one
            return tree[index]
        else:
            return subvar_lookup(original, vars_list[1:], tree[index], bindings)
    else:
        raise(Exception('Subvariable data not indexable {} {}'.format(original, tree)))

def expand_str(tree, bindings):
    pp(['***', tree])
    subvar = tree.split('.')
    pp(['subvar', subvar])
    tv = lookup(bindings, subvar[0])
    pp(['tv', tv])
    if not tv:
        return tree # No variable to expand for this string
    if len(subvar) > 1:
        # It's a dot notation variable like 'host.name'
        res_tuple = lookup(bindings, subvar[0])
        if not res_tuple:
            return tree
        return subvar_lookup(tree, subvar[1:], res_tuple[0], bindings)
    else:
        # An atomic variable line 'foo'
        return tv[0]

def expand(tree, bindings):
    """
    Recursivley substitute values in the symbol table bindings
    Return a new tree

    """
    pp(('** expa', tree))
    if type(tree) == str:
        result = expand_str(tree, bindings)
        pp(('ex result', result))
        if result == tree:
            return interpolate(tree, bindings)
        if type(result) == str:
            return interpolate(expand(result, bindings), bindings)
        else:
            return expand(result, bindings)

    elif type(tree) == list:
        newlist = []
        for item in tree:
            expanded = expand(item, bindings)
            if expanded != None:
                newlist.append(expand(expanded, bindings))
        return newlist
    elif type(tree) == dict:
        newdict = {}
        if '==' in tree.keys():
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if type(tree['==']) != list:
                    raise(Exception('Syntax error was expecting list in {}'.format(tree)))
            if len(tree['==']) < 2:
                    raise(Exception('Syntax error was expecting list(2) in {}'.format(tree)))
            expect = expand(tree['=='][0], bindings)
            for item in tree['==']:
                if expand(item, bindings) != expect:
                    return False
            return True

        if '+' in tree.keys():
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if type(tree['+']) != list:
                    raise(Exception('Syntax error was expecting list in {}'.format(tree)))
            if len(tree['+']) < 2:
                    raise(Exception('Syntax error was expecting list(2) in {}'.format(tree)))
            sum = 0
            for item in tree['+']:
                item_ex = expand(item, bindings)
                #pprint.pprint(('++++', item, item_ex, bindings))
                if not isinstance(item_ex, numbers.Number):
                    raise(Exception('Was expecting number in {}'.format(tree)))
                sum += item_ex
            return sum

        if 'if' in tree.keys():
            for required in ['else', 'then']:
                if required not in tree:
                    raise(Exception('Syntax error {} missing in {}'.format(required, tree)))
            if expand(tree['if'], bindings) == True:
                expanded = expand(tree['then'], bindings)
                return expand(expanded, bindings)
            else:
                expanded = expand(tree['else'], bindings)
                return expand(expanded, bindings)
            #pprint.pprint(bindings)
            return None
        if 'define' in tree.keys():
            if len(tree) == 0:
                raise(Exception('Empty define {}'.format(tree)))
            if 'name' not in tree['define'] or 'value' not in tree['define']:
                raise(Exception('Syntax error in {}'.format(tree)))
            bindings[tree['define']['name']] = tree['define']['value']
            #pprint.pprint(bindings)
            return None
        if 'defmacro' in tree.keys():
            for required in ['name', 'args', 'value']:
                if required not in tree['defmacro']:
                    raise(Exception('Syntax error {} missing in {}'.format(required, tree)))
            bindings[tree['defmacro']['name']] = new_macro(tree['defmacro'], bindings)
            #pprint.pprint(bindings)
            return None
        for k,v in tree.iteritems():
            new_k = expand(k, bindings)
            if new_k in newdict:
                raise Exception('ERROR: name collision after expansion of {} with {}'.format(k, newdict))
            if type(new_k) == type(expand):
                if len(tree.keys()) != 1:
                    raise Exception('ERROR: too many keys in macro call {}'.format(tree))
                return(expand(new_k(expand(v, bindings)), bindings))
            newdict[k] = expand(v, bindings)
        return newdict
    else:
        return tree


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('ERROR: no files to scan', file=sys.stderr)
        sys.exit(1)

    global_environment = {'env': os.environ.copy() } # copy() to get a dictionary

    for filename in sys.argv[1:]:
        global_environment['__FILE__'] = filename
        statinfo = os.stat(filename)
        if statinfo.st_size == 0:
            print("ERROR: empty file {}".format(filename), file=sys.stderr)
            sys.exit(1)
        try:
            docs = load_all(open(filename), Loader=Loader)
            for tree in docs:
                expanded_tree = expand(tree, global_environment)
                print('---')
                print(dump(expanded_tree, default_flow_style=False))
        except Exception as e:
            print("ERROR: {}\n{}\n".format(filename, e), file=sys.stderr)
            sys.exit(1)


