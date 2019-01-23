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
    if len(tokens) == 1:
        # Nothing to interpolate
        return astring
    rebound  = []
    for tok in tokens:
        value = tok
        if tok.startswith('{{') and tok.endswith('}}'):
            variable_name = tok[2:][:-2].strip()
            value = expand_str(variable_name, bindings)
            if value == variable_name:
                raise(Exception('Undefined interpolation variable "{}" in "{}"'.format(variable_name, astring)))
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
        pp("to apply: {} to {} with {}".format(name, args, bindings))
        pp(('**apply', name, parameters, args))
        if args and type(args) != dict:
            raise(Exception('Expecting dict args for {}, got: {}'.format(name, args)))
        if type(parameters) == list and len(parameters) == 0  and args:
            raise(Exception('Too many args for {}: {}'.format(name, args)))
        if type(parameters) == list and parameters and args:
            if set(parameters or []) != set(args.keys()):
                raise(Exception('Argument mismatch in {} expected {} got {}'.format(name, parameters, args)))
        macro_env = {'__parent__': bindings}
        if type(parameters) == str: # varargs
            macro_env[parameters] = args
        else:
            if args: # Might be None for no args
                macro_env.update(args)
        return expand(body, macro_env)
    return apply


def subvar_lookup(original, vars_list, tree, bindings):
    """
    Given 'b.1', ['b', '1' ] , {'b': ['x', 'y']}
        return 'y'
    """
    pp(['*** sl', original, vars_list, tree])
    if len(vars_list) == 0:
        raise(Exception('Subvariable not found in {}'.format(original)))
    if tree == None:
        raise(Exception('Subvariable "{}" not found in {}'.format(vars_list, original)))

    # If the subvar is a variable binding, use it
    ftv = lookup(bindings, vars_list[0])
    if ftv:
        first =  ftv[0]
    else:
        first = vars_list[0]
    if type(tree) == dict:
        if not first in tree:
            raise(Exception('Subvariable "{}" not found in {}'.format(first, original)))
        if len(vars_list) == 1: # last one
            return tree[first]
        else:
            return subvar_lookup(original, vars_list[1:], tree[first], bindings)
    elif type(tree) == list or type(tree) == tuple:
        if type(first) == int:
            index = first
        elif type(first) == str and first.isdigit():
            index = int(first)
        else:
            raise(Exception('Subvariable List index not numeric: "{}" for {} {}'.format(first, original, tree)))
        if len(tree) <= index or index < 0:
            raise(Exception('Subvariable List index out of bounds: {} for {} {}'.format(index, original, tree)))
        if len(vars_list) == 1: # Last one
            return tree[index]
        else:
            return subvar_lookup(original, vars_list[1:], tree[index], bindings)
    else:
        raise(Exception('Subvariable data not indexable {} {}'.format(original, tree)))

def expand_str(tree, bindings):
    pp(['*** es', tree])
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
        # An atomic variable line 'host'
        return tv[0]

def expand_repeat(tree, bindings):
    if 'key' in tree['repeat']:
        return expand_repeat_dict(tree, bindings)
    else:
        return expand_repeat_list(tree, bindings)

def expand_repeat_dict(tree, bindings):
    statement = tree['repeat']
    parameters = ['for', 'in', 'body', 'key']
    if set(parameters) != set(statement.keys()):
        raise(Exception('Argument mismatch in {} \n\texpected {} got {}'.format(tree, parameters, statement.keys())))
    rang = expand(expand(statement['in'], bindings), bindings)
    pp(('*** rang', rang))
    var = statement['for']
    body = statement['body']
    key = statement['key']
    if type(rang) != list:
        raise(Exception('Syntax error "in" not list in {}'.format(rang)))
    if type(var) != str:
        raise(Exception('Syntax error "for" not string in {}'.format(statement)))
    if type(key) != str:
        raise(Exception('Syntax error "key" not string in {}'.format(statement)))
    result = {}
    loop_binding = {'__parent__': bindings}
    for item in rang:
        loop_binding[var] = item
        keyvalue = expand(expand(key, loop_binding), loop_binding)
        result[keyvalue] = expand(expand(body, loop_binding), loop_binding)
    return result

def expand_repeat_list(tree, bindings):
    statement = tree['repeat']
    parameters = ['for', 'in', 'body']
    if set(parameters) != set(statement.keys()):
        raise(Exception('Argument mismatch in {} \n\texpected {} got {}'.format(tree, parameters, statement.keys())))
    rang = expand(expand(statement['in'], bindings), bindings)
    pp(('*** rang', rang))
    var = statement['for']
    body = statement['body']
    if type(rang) != list:
        raise(Exception('Syntax error "in" not list in {}'.format(rang)))
    if type(var) != str:
        raise(Exception('Syntax error "for" not string in {}'.format(statement)))
    result = []
    loop_binding = {'__parent__': bindings}
    for item in rang:
        loop_binding[var] = item
        result.append(expand(body, loop_binding))
    return result

def expand_python(tree, bindings):
    statement = tree['python']
    if type(statement) != str:
        raise(Exception('Syntax error not string in {}'.format(tree)))
    if len(tree.keys()) != 1:
            raise(Exception('Syntax error too many keys in {}'.format(tree)))
    return eval('(' + statement + ')', globals(), bindings)

def map_define(arglist, bindings):
    """
    define:
        a: 1
        b: 2
    """
    #
    definitions = expand(arglist, bindings)
    if type(definitions) != dict:
        raise(Exception('Syntax error bad define arguments "{}" from {}'.format(definitions, arglist)))
    bindings.update(definitions)
    return None


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

        if 'range' in tree.keys():
            statement = tree['range']
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if type(statement) != list:
                    raise(Exception('Syntax error was expecting list in {}'.format(tree)))
            if len(statement) < 2:
                    raise(Exception('Syntax error was expecting list(2) in {}'.format(tree)))
            start = str(expand(statement[0], bindings)) # TODO
            end = str(expand(statement[1], bindings))
            pp((start, end))
            for item in [start, end]:
                if not item.isdigit():
                    raise(Exception('Syntax error was expecting integer range in {}, got {}'.format(tree, item)))
            return list(range(int(start), int(end)+1))

        if 'python' in tree.keys():
            return expand_python(tree, bindings)

        if 'if' in tree.keys():
            pp(('>> if', tree))
            if 'else' not in tree.keys() and 'then' not in tree.keys():
                raise(Exception('Syntax error "then" or "else" missing in {}'.format(tree)))
            if set(tree.keys()) - set(['if', 'then', 'else']):
                raise(Exception('Syntax error extra keys in {}'.format(tree)))
            condition = expand(tree['if'], bindings)
            if condition not in [True, False, None]:
                raise(Exception('If condition not "true", "false" or "null". Got: "{}" in {}'.format(condition, tree)))
            if condition == True and 'then' in tree.keys():
                expanded = expand(tree['then'], bindings)
                return expand(expanded, bindings)
            elif (condition == False or condition == None) and 'else' in tree.keys():
                expanded = expand(tree['else'], bindings)
                return expand(expanded, bindings)
            return None

        if 'define' in tree.keys():
            pp(('== define', tree))
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if 'name' not in tree['define'] and 'value' not in tree['define']:
                return map_define(tree['define'], bindings)
            for required in ['name', 'value']:
                if required not in tree['define']:
                    raise(Exception('Syntax error "{}" missing in {}'.format(required, tree)))
            if type(tree['define']['name']) != str:
                raise(Exception('Syntax error "{}" not a string in {}'.format(tree['define']['name'], tree)))
            pp(('defining', tree['define']['name'], expand(tree['define']['value'], bindings)))
            bindings[tree['define']['name']] = expand(tree['define']['value'], bindings)
            return None

        if 'repeat' in tree.keys():
            return expand_repeat(tree, bindings)

        if 'defmacro' in tree.keys():
            for required in ['name', 'args', 'value']:
                if required not in tree['defmacro']:
                    raise(Exception('Syntax error {} missing in {}'.format(required, tree)))
            bindings[tree['defmacro']['name']] = new_macro(tree['defmacro'], bindings)
            return None

        if 'include' in tree.keys():
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if type(tree['include']) != list:
                    raise(Exception('Syntax error was expecting list in {}'.format(tree)))
            for filename in tree['include']:
                if type(filename) != str:
                    raise(Exception('Syntax error was list of string in {}'.format(tree)))
                expand_file(expand(filename, bindings))
            return None

        if 'load' in tree.keys():
            if len(tree.keys()) != 1:
                    raise(Exception('Syntax error too many keys in {}'.format(tree)))
            if type(tree['load']) != str:
                    raise(Exception('Syntax error was expecting string in {}'.format(tree)))
            pp(tree['load'])
            return expand_file(expand(tree['load'], bindings), False)

        for k,v in tree.iteritems():
            new_k = expand(k, bindings)
            if type(new_k) == type(expand):
                if len(tree.keys()) != 1:
                    raise Exception('ERROR: too many keys in macro call {}'.format(tree))
                return(expand(new_k(expand(v, bindings)), bindings))
            interp_k = interpolate(k, bindings)
            if interp_k != k:
                # string containing {{ }} - onle these keys are expanded
                if interp_k in newdict:
                    raise Exception('ERROR: duplicate map key "{}" in {}'.format(interp_k, tree))
                newdict[interp_k] = expand(v, bindings)
                continue
            if k in newdict:
                raise Exception('ERROR: duplicate map key "{}" in {}'.format(k, tree))
            newdict[k] = expand(v, bindings)
        return newdict
    else:
        return tree


def expand_file(filename, expandafterload=True):
    """
    Read and optionally expand a file in the global environment.

    If filename begins with '/' treat as absolute, otherwise
    treat as relative to the current file. If there is no
    current file (top-level) use the current directory.

    No return value

    """
    global global_environment

    current_file = global_environment['__FILE__']
    if current_file == None:
        current_dir = os.getcwd()
    else:
        current_dir = os.path.dirname(current_file)
    if filename.startswith('/'):
        path = filename
    else:
        path = os.path.join(current_dir, filename)
    if expandafterload:
        global_environment['__FILE__'] = path
    statinfo = os.stat(path)
    if statinfo.st_size == 0:
        print("ERROR: empty file {}".format(path), file=sys.stderr)
        sys.exit(1)
    try:
        docs = load_all(open(path), Loader=Loader)
        if expandafterload:
            for tree in docs:
                expanded_tree = expand(tree, global_environment)
                if expanded_tree:
                    print('---')
                    print(dump(expanded_tree, default_flow_style=False))
        else:
            return [tree for tree in docs]
        global_environment['__FILE__'] = current_file
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR: {}\n{} line {}\n".format(path, e, exc_tb.tb_lineno), file=sys.stderr)
        sys.exit(1)

global_environment = {'env': os.environ.copy() } # copy() to get a dictionary


if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('ERROR: no files to scan', file=sys.stderr)
        sys.exit(1)

    global_environment['argv'] = sys.argv
    filename  = sys.argv[1]
    global_environment['__FILE__'] = None
    expand_file(filename)


