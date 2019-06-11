#!/bin/env python
"""

 Python 2.7 Script to expand YAML macros

"""
from __future__ import print_function

import os

import re
import sys
import json
import math
import numbers
import datetime
from yaml import load, Loader, dump, load_all

class YampException(Exception):
    pass

def interpolate(astring, bindings):
    """
    Parse a string which may contain embedded variables denoted by curlies {{ }}.
    When these are found expand the variables and return the expanded string.
    If the variables are called up but not defined throw an error.
    :param astring:
    :param bindings:
    :return: astring with added values
    """

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
                raise(YampException('Undefined interpolation variable "{}" in "{}"'.format(variable_name, astring)))
        rebound.append(str(value))
    return(''.join(rebound))

#
# About bindings
#
# The environment dicts, bindings, have the following union structure:
#    key - is a string, the variable name
#    value - one of 
#        - atomic type, String int, float, boolean etc
#        - list
#        - dict 
#        - tuple indicates an executable either a closure (macro) or a builtin 
#            [0] - A type indicator string, one of:
#                     'eager' - meaning expand arguments before execution of macro, expand the result of macro execution
#                     'lazy' - do not execute arguments before macro call but expand the result
#                     'quote' - dont expand arguments or expand the result
#            [1] - a callable Python function value containing the macro or builtin  
#
def lookup(env, key):
    """
    Search an environment stack for a binding of key to a value, 
    following __parent__ links to higher environment. 
    :param env: Start seaching from this env
    :param key: variable name to look for.
    :return: value, ok - if key is found ok is True and value has the value, otherwise ok is False and value is undefined.
    """
    while True:
        if key in env:
            return env[key], True
        elif '__parent__' in env:
            env = env['__parent__']
            continue
        else:
            return None, False

def new_macro(tree, bindings):
    """
    Given a macro definition of the form 
        {
        'name': <string>,
        'macro_type': <eager|lazy|quote>, 
        'args': None|<list of strings>|<string>, 
        'value': <anything>
        },
    create a Python function closed in the current function. The function returned has signature (args),
    where args contains a map with bindings for each of the 'args' supplied. The returned function applies
    expansion of the 'body' with the supplied real arguments in its environment.

    If the 'args' is a single string, not a list, then
    the returned function binds all its actual arguments to the specified args binding.

    If 'args' is None no arguments are bound, but if actual arguments are provided the returned function raises an error.
    :param tree: {'name': <string>, 'macro_type': <eager|lazy|quote>, 'args': None|<list of strings>|<string>, 'value': <anything>}
    :param bindings: environment to update
    :return: A tuple containing a type tag in [0] and in [1] a new function to apply when the macro is called
    """
    name = tree['name']
    body = tree['value']
    parameters = tree['args'] or []
    macro_type = tree.get('macro_type', 'eager')
    def apply(seen_tree, args, dynamic_bindings):
        """
        Given a map of arguments, create a new local environment for this macro expansion, bind the args to the new
        enviroment, then expand the captured body and return the result. If the captured parameters variable is a string, it is
        used for variable arguments which are all bound to it.
        :param seen_tree: Tree as parsed
        :param args: 
        :param dynamic_bindings: bindings for builtins 
        :return:
        """
        if type(parameters) == list and args and type(args) != dict:
            raise(YampException('Expecting dict args for {} [ {} ], got: {}'.format(name, parameters, args)))
        if type(parameters) == list and len(parameters) == 0  and args:
            raise(YampException('Too many args for {}: {}'.format(name, args)))
        if type(parameters) == list and parameters and args:
            if set(parameters or []) != set(args.keys()):
                raise(YampException('Argument mismatch in {} expected {} got {}'.format(name, parameters, args)))
        if type(body) == type(expand): # Is this a built-in python function?
            return body(seen_tree, args, dynamic_bindings)
        else:
            if len(seen_tree.keys()) != 1:
                raise(YampException('ERROR: too many keys in macro call "{}"'.format(seen_tree)))
            macro_env = {'__parent__': bindings}
            if type(parameters) == str: # varargs
                macro_env[parameters] = args
            else:
                if args: # Might be None for no args
                    macro_env.update(args)
            return expand(body, macro_env)
    return (macro_type, apply)


def subvar_lookup(original, vars_list, tree, bindings):
    """
    Parse and expand a 'dot notation' variable string. Recursively walk the tree of the main variable value,
    as given by the subvariable list. Return the last value if possible.

    :param original: The dot notation string - ie. 'b.1' - used for debug
    :param vars_list: a list of 'sub' variables - ie ['1']
    :param tree: the value of the major variable - ie. value of 'b' => ['x', 'y']
    :param bindings: the current environment
    :return: Example - Given 'b.1', ['b', '1' ] , {'b': ['x', 'y']} => returns 'y'
    """
    if len(vars_list) == 0:
        raise(YampException('Subvariable not found in {}'.format(original)))
    if tree == None:
        raise(YampException('Subvariable "{}" not found in {}'.format(vars_list, original)))

    # If the subvar is a variable binding, use it
    ftv, ok = lookup(bindings, vars_list[0])
    if ok:
        first =  ftv
    else:
        first = vars_list[0]
    if type(first) not in (str, int):
        raise(YampException('Subvariable "{}" not a string or int in {}'.format(first, original)))
    if type(tree) == dict:
        if not first in tree.keys():
            raise(YampException('Subvariable "{}" not found in {}'.format(first, original)))
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
            raise(YampException('Subvariable List index not numeric: "{}" for {} {}'.format(first, original, tree)))
        if len(tree) <= index or index < 0:
            raise(YampException('Subvariable List index out of bounds: {} for {} {}'.format(index, original, tree)))
        if len(vars_list) == 1: # Last one
            return tree[index]
        else:
            return subvar_lookup(original, vars_list[1:], tree[index], bindings)
    else:
        raise(YampException('Subvariable data not indexable {} {}'.format(original, tree)))

def expand_str(variable_name, bindings):
    """
    Given a simple string variable get its value from the binding, it has dot notation look in the
    variable value for the selection.
    :param tree: - the variable name in a simple case, or the dotnotation variable.
    :param bindings: - current environment
    :return:
    """
    value, ok = lookup(bindings, variable_name)
    if ok:
        return value # a simple variable like 'host' or a variable like 'a.c.e' matches first

    # nothing simple, look for subvariables.
    subvar = variable_name.split('.')
    if len(subvar) > 1:
        # It's a dot notation variable like 'host.name'
        topvalue, ok = lookup(bindings, subvar[0])
        if not ok:
            return variable_name # No variable found
        return subvar_lookup(variable_name, subvar[1:], topvalue, bindings)
    else:
        return variable_name

def expand_repeat_dict(tree, statement, bindings):
    """
    Expand a repeat loop and return a map, with a parameteriseed key. Create a local environment for the
    expansion, bind the for variable name to the iteration value each time round.
    :param tree: The repeat form such as {repeat: {for: X, in: [1,2], key: 'Foo {{X}}', body: [stuff, X]}
    :param bindings:
    :return: The Expanse
    """
    rang = expand(expand(statement['in'], bindings), bindings)
    var = statement['for']
    body = statement['body']
    key = statement['key']
    if type(rang) != list:
        raise(YampException('Syntax error "in" not list in {}'.format(rang)))
    if type(var) != str:
        raise(YampException('Syntax error "for" not string in {}'.format(statement)))
    if type(key) != str:
        raise(YampException('Syntax error "key" not string in {}'.format(statement)))
    result = {}
    loop_binding = {'__parent__': bindings}
    for item in rang:
        loop_binding[var] = item
        keyvalue = expand(expand(key, loop_binding), loop_binding)
        if keyvalue in result:
            raise(YampException('ERROR: key "{}" duplication in {}'.format(keyvalue,tree)))
        result[keyvalue] = expand(expand(body, loop_binding), loop_binding)
    return result

def expand_repeat_list(tree, statement, bindings):
    """
    Expand a repeat loop and return a list one item each time. Create a local environment for the
    expansion, bind the for variable name to the iteration value each time round.
    :param tree: The repeat form such as {repeat: {for: X, in: [1,2], body: [stuff, X]}
    :param bindings:
    :return: The Expanse
    """
    rang = expand(expand(statement['in'], bindings), bindings)
    var = statement['for']
    body = statement['body']
    if type(rang) != list:
        raise(YampException('Syntax error "in" not list in {}'.format(rang)))
    if type(var) != str:
        raise(YampException('Syntax error "for" not string in {}'.format(statement)))
    result = []
    loop_binding = {'__parent__': bindings}
    for item in rang:
        loop_binding[var] = item
        result.append(expand(body, loop_binding))
    return result

def map_define(arglist, bindings):
    """
    Given a tree of the form {name:value, name: value}, expand and
    bind the names provided to the values
    in the current environment.
    :param arglist: dict of name values
    :param bindings: current environment to be updated
    :return: None
    """
    definitions = expand(arglist, bindings)
    if type(definitions) != dict:
        raise(YampException('Syntax error bad define arguments "{}" from {}'.format(definitions, arglist)))
    bindings.update(definitions)
    return None

def flatten_list(listy, bindings):
    """
    Recursively expand and flatten a list of lists. Lists in maps are not flattened.
    :param listy: list of lists to expand and flatten
    :param bindings:
    :return:
    """
    result = []
    for rawitem in listy:
        item = expand(rawitem, bindings)
        if not type(item) == list:
            result.append(item) # atoms or maps
        else:
            result.extend(flatten_list(item, bindings)) # list
    return result

def flat_list(depth, listy):
    """
    Flatten a variable level list of lists.
    Depth gives how many levels to descend.
    Lists in maps are not flattened.
    :param listy: list of lists to expand and flatten
    :param bindings:
    :return:
    """
    if depth == 0:
        return listy
    result = []
    for item in listy:
        if not type(item) == list:
            result.append(item) # atoms or maps
        else:
            result.extend(flat_list(depth -1, item)) # list
    return result

def merge_maps(mappy, bindings):
    """
    Expand and combine multiple maps into one map. Not recursive. Later maps overwrite earlier.
    :param mappy: list of maps to be merged.
    :param bindings:
    :return: new map with merged content
    """
    result = {}
    for rawitem in mappy:
        item = expand(rawitem, bindings)
        if not type(item) == dict:
            raise(YampException('Error: non-map passed to merge "{}" from {}'.format(item, rawitem)))
        else:
            for k,v in item.iteritems():
                result[k] = v
    return result

def validate_single(tree):
    """
    Raise an exception if there are not a single key in tree.
    :return: None
    """
    if len(tree.keys()) != 1:
            raise(YampException('Syntax error too many keys in {}'.format(tree)))

def validate_params(tree, tree_proto, args, args_proto):
    """
    Given a protype for a form and arguments, raise execptions if they dont match.
    Checks: 
        - the number of keys in the tree,
        - the type of the args
        - the number of agrs if a list
    
    e.g. validate_params({'a': None}, {'a': None}, [1], [1]) is OK
    :return: None
    """
    if len(tree.keys()) != len(tree_proto):
            raise(YampException('Syntax error incorrect number of keys in {}'.format(tree)))
    if type(args) != type(args_proto):
            raise(YampException('Syntax error incorrect argument type. Expected {} in {}'.format(type(args_proto), tree)))
    if type(args) in [list, dict]:         # Is it something with a length?
        if len(args) < len(args_proto):
                raise(YampException('Syntax error too few arguments. Expected {} in {}'.format(len(args_proto), tree)))

def validate_keys(specification, amap):
    """
    Raise an exception if the keys in the specification are not present in the args, or if there are
    additional keys not in the spec. Optional keys are wrapped in a tuple.
    Example:
       ['for', 'in', ('step')]
    """
    extras = set(amap.keys())
    for key in specification:
      if type(key) == str:
        if not key in amap:
           raise(YampException('Syntax error missing argument {} in {}'.format(key, amap)))
        extras.discard(key)
      elif type(key) == tuple:
         optional = key[0]
         if type(optional) != str:
            raise(YampException('Invalid spec {}'.format(specification)))
         extras.discard(optional)
      else:
          raise(YampException('Invalid {} spec {}'.format(type(key), specification)))      
    if len(extras) > 0:
        raise(YampException('Unexpected keys {} in {}'.format(extras, amap)))

def equals_builtin(tree, args, bindings):
    """
    :return: True or False depending if args are the same. 
    """
    validate_params(tree, {'': None}, args, [1, 2])
    expect = args[0]
    for item in args:
        if item != expect:
            return False
    return True

def plus_builtin(tree, args, bindings):
    """
    :return: the sum of the arguments.
    """
    validate_params(tree, {'': None}, args, [1, 2])
    sum = 0
    for item in args:
        if not isinstance(item, numbers.Number):
            raise(YampException('Was expecting number in {}'.format(tree)))
        sum += item
    return sum

def range_builtin(tree, statement, bindings):
    """
    :return: a list from  statement[0] to statement[1]
    """
    if not statement:
       raise(YampException('Syntax error was expecting integers list in {}, got {}'.format(tree, statement)))
    validate_params(tree, {'range': None}, statement, [1,2])
    start = str(expand(statement[0], bindings))
    end = str(expand(statement[1], bindings))
    for item in [start, end]:
        if not item.isdigit():
            raise(YampException('Syntax error was expecting integer range in {}, got {}'.format(tree, item)))
    return list(range(int(start), int(end)+1))

def flatten_builtin(tree, args, bindings):
    """
    See flatten_list
    """
    validate_params(tree, {'': None}, args, [])
    return flatten_list(args, bindings)

def flatone_builtin(tree, args, bindings):
    """
    See flat_list
    """
    validate_params(tree, {'': None}, args, [])
    return flat_list(1, args)

def merge_builtin(tree, args, bindings):
    """
    See merge_maps
    """
    validate_params(tree, {'': None}, args, [])
    return merge_maps(args, bindings)

def include_builtin(tree, args, bindings):
    """
    Sequentially expand a list of YAML files in the current environment.
    return: None
    """
    validate_params(tree, {'': None}, args, [])
    for filename in args:
        if type(filename) != str:
            raise(YampException('Syntax error was list of string in {}'.format(tree)))
        expand_file(expand(filename, bindings), bindings)
    return None

def load_builtin(tree, args, bindings):
    """
    Read a file of data, no macro expansions.
    :return: the data as read
    """
    validate_params(tree, {'': None}, args, '')
    return expand_file(args, bindings, expandafterload=False)


class Env(dict):
  """
    Class to make python_eval find variables easily
  """
  def __missing__(self, key):
    """
    Called by dict when the key is not found.
    Return the value from higher environment. 
    """
    value, ok = lookup(self, key)
    if not ok:
         raise(KeyError('python_eval: variable not found "{}"'.format(key)))
    return value

def python_builtin(tree, args, bindings):
    """
    Expand a tree of the form {python: 'some expression'} by executing Python eval() with the current bindings
    used as the Python local variables.
    :param tree: the original source form {python: 'some expression'}
    :param args: The actual arguments
    :param bindings:
    :return: Expanse
    """
    validate_params(tree, {'': None}, args, '')
    return eval('(' + args + ')', globals(), Env(bindings))

def repeat_builtin(tree, args, bindings):
    """
    Expand a repeat macro, this function selects the appropriate expander for lists and maps.
    If the repeat has the 'key' key, then execute as for maps, else lists.
    :param tree: The repeat form such as {repeat: {for: X, in: [1,2], key: 'Foo {{X}}', body: [stuff, X]}
    :param bindings:
    :return: The Expanse
    """
    validate_keys(['for', 'in', 'body', ('key',)], args)
    
    if 'key' in tree['repeat']:
        return expand_repeat_dict(tree, args, bindings)
    else:
        return expand_repeat_list(tree, args, bindings)

def define_builtin(tree, args, bindings):
    """
    Define one or more variables in the current scope.
    :return: None
    """
    validate_single(tree)
    if 'name' not in args and 'value' not in args:
        return map_define(args, bindings)
    validate_keys(['name', 'value'], args)
    if type(args['name']) != str:
        raise(YampException('Syntax error "{}" not a string in {}'.format(args['name'], tree)))
    bindings[args['name']] = expand(args['value'], bindings)
    return None

def undefine_builtin(tree, args, bindings):
    """
    Remove binding in the current environment only.
    :return: None
    """
    validate_single(tree)
    if type(args) != str:
            raise(YampException('Syntax error was expecting string in {} got {}'.format(tree, args)))
    if args in bindings:
        del bindings[args]
    return None

def defmacro_builtin(tree, args, bindings):
    """
    Define a new macro. 
    :return: None
    """
    if not args:
        raise(YampException('Syntax error empty defmacro {}'.format(tree)))
    validate_keys(['name', 'args', 'value'], args)
    bindings[args['name']] = new_macro(args, bindings)
    return None

def if_builtin(tree, args, bindings):
    """
    Conditional expression
    :return: either the expansion of the 'then' or 'else' elements. 
    """
    if 'else' not in tree.keys() and 'then' not in tree.keys():
        raise(YampException('Syntax error "then" or "else" missing in {}'.format(tree)))
    extras = set(tree.keys()) - set(['if', 'then', 'else'])
    if extras:
        raise(YampException('Syntax error extra keys {} in {}'.format(extras, tree)))
    condition = expand(tree['if'], bindings)
    if condition not in [True, False, None]:
        raise(YampException('If condition not "true", "false" or "null". Got: "{}" in {}'.format(condition, tree)))
    if condition == True and 'then' in tree.keys():
        expanded = expand(tree['then'], bindings)
        return expand(expanded, bindings)
    elif (condition == False or condition == None) and 'else' in tree.keys():
        expanded = expand(tree['else'], bindings)
        return expand(expanded, bindings)
    return None

def quote_builtin(tree, args, bindings):
    """
    :return: the args without expansion
    """
    validate_single(tree)
    return args

def add_builtins_to_env(env):
    """
    Utility function to add all the builtins to an environment
    :env: Environment to add to
    :return: The environment
    """
    def add_new_builtin(name, fn, func_type='eager'):
        env[name] = new_macro({'name': name, 'args': 'varargs', 'value': fn, 'macro_type': func_type},  env) 

    add_new_builtin('flatten', flatten_builtin)
    add_new_builtin('flatone', flatone_builtin)
    add_new_builtin('merge', merge_builtin)
    add_new_builtin('==', equals_builtin)
    add_new_builtin('+', plus_builtin)
    add_new_builtin('range', range_builtin)
    add_new_builtin('include', include_builtin)
    add_new_builtin('load', load_builtin)
    add_new_builtin('define', define_builtin, 'lazy')
    add_new_builtin('undefine', undefine_builtin, 'lazy')
    add_new_builtin('defmacro', defmacro_builtin, 'lazy')
    add_new_builtin('if', if_builtin, 'lazy')
    add_new_builtin('repeat', repeat_builtin, 'lazy')
    add_new_builtin('python_eval', python_builtin, 'quote')
    add_new_builtin('quote', quote_builtin, 'quote')
    
    return env

def is_function(tree, bindings):
    """
    Return function tuple and rhs if this is a function call, else False
    """
    def lookup_function(k):
        """
        Return the function def from its binding, or None
        """
        if type(k) == str and k.startswith('^'):
            variable_name = k[1:]
            func, ok = lookup(bindings, variable_name)
            if not ok:
                raise(YampException('ERROR: Variable {} not defined in {}'.format(variable_name, tree)))
        else: 
            func = expand(k, bindings)
        return func

    func = None
    k = None    
    if len(tree.keys()) == 1:
        k = tree.keys()[0]
    elif "if" in tree: # Special case :-(
        k = "if"
    func = lookup_function(k)
    if type(func) == tuple:
        return func, tree[k]
    # At this point we have len(keys()) > 1 and its not an "if"
    # so we cannot have a function under any key...
    for k,v in tree.iteritems():
        func = lookup_function(k)        
        if type(func) == tuple:
            raise(YampException('ERROR: too many keys in macro {}'.format(tree)))
    return False, None

def expand(tree, bindings):
    """
    This is the eval function of the macro-processor.  It takes a any kind of YAML-generated combination of
    dictionaries, lists and atoms, and recursively substitutes keys in the symbol table (bindings) with the
    stored values. If the value is a previously defined macro function it is applied to the form.  If the result
    of an expansion is None, no list item is generated.
    :param tree: Any tree as generated by reading YAML.
    :param bindings: A hierarchy of symbol-tables of variables and bindings, connected by their __parent__ keys.
    :return:     Return a new tree
    """
    if type(tree) == str:
        result = expand_str(tree, bindings)
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
                newlist.append(expanded)
        return newlist
    elif type(tree) == dict:
        newdict = {}

        # Lookahead for functions have Lazy maps we dont want to expand yet...
        func, rhs = is_function(tree, bindings)
        if func :
            if func[0] == 'eager':
                return(expand(func[1](tree, expand(rhs, bindings), bindings), bindings))
            elif func[0] == 'lazy':
                return(expand(func[1](tree, rhs, bindings), bindings))
            else: # quote
                return(func[1](tree, rhs, bindings))

        # Just a normal map - not a function
        for k,v in tree.iteritems():

            if type(k) == str and k.startswith('^'):
                variable_name = k[1:]
                value, ok = lookup(bindings, variable_name)
                if not ok:
                    raise(YampException('ERROR: Variable {} not defined in {}'.format(variable_name, tree)))
                newdict[value] = expand(v, bindings)
                continue

            interp_k = interpolate(k, bindings)
            if interp_k != k:
                # string contains {{ }} - only these keys are expanded
                if interp_k in newdict:
                    raise(YampException('ERROR: duplicate map key "{}" in {}'.format(interp_k, tree)))
                newdict[interp_k] = expand(v, bindings)
                continue
            if k in newdict:
                raise(YampException('ERROR: duplicate map key "{}" in {}'.format(k, tree)))
            newdict[k] = expand(v, bindings)
        return newdict
    else:
        return tree

def byteify(input):
    """
    Function to replace all Unicode strings with plain-old-ascii (UTF-8) ones. See author's description:
    https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json/13105359#13105359 
    """
    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

def expand_file(filename, bindings, expandafterload=True, outputfile=None):
    """
    Read and optionally expand a file in the global environment.

    If filename begins with '/' treat as absolute, otherwise
    treat as relative to the current file. If there is no
    current file (top-level) use the current directory.

    :param filename:
    :param bindings:
    :param expandafterload:
    :param outputfile:
    :return:     No return value
    """
    def expand_yaml():
        """
        Process YAML data - with macro-expansion - empty documents are removed.
        """
        try:
            if path == '-':
                fd = sys.stdin
            else:
                statinfo = os.stat(path)
                if statinfo.st_size == 0:
                    print("ERROR: empty file {}".format(path), file=sys.stderr)
                    sys.exit(1)
                fd = open(path)
            doc_gen = load_all(fd, Loader=Loader)
            if expandafterload:
                expanded = []
                for tree in doc_gen:
                    expanded_tree = expand(tree, bindings)
                    if expanded_tree and expanded_tree != [] and expanded_tree != {}:
                        expanded.append(expanded_tree)
                for output_doc in expanded:
                   if len(expanded) > 1 :
                        outputfile.write('---\n')
                   outputfile.write(dump(output_doc, default_flow_style=False))
            else:
                return [tree for tree in doc_gen]
        except Exception as e:
            print("ERROR: {}\n{}\n{}\n".format(path, type(e), e), file=sys.stderr)
            sys.exit(1)

    def expand_json():
        """
        Process JSON data (no expansions)
        """
        try:
            data = byteify(json.load(open(path)))
            return data
        except YampException as e:
            print("ERROR: {}\n{}\n".format(path, e), file=sys.stderr)
            sys.exit(1)

    # Now try to figure out the file type
    file_types = {  'yaml' : expand_yaml, 
                    'yml'  : expand_yaml,
                    'yamp' : expand_yaml,
                    '-' : expand_yaml,
                    'json' : expand_json}
    suffix = filename.split('.')[-1]
    if not suffix in file_types:
        sys.stdout.write('Yamp: unknown file type "{}", file types are {}. Attempting YALM...\n'.format(filename, file_types.keys()))
        file_types[suffix] = expand_yaml
        
    if not outputfile:
        # Probably an include - assume we can inherit the output.
        outputfile = bindings['__current_output__']
    elif '__current_output__' not in bindings:
        # First time called
        bindings['__current_output__'] = outputfile

    current_file = bindings['__FILE__'] # Remember prior file
    if current_file == None:
        current_dir = os.getcwd()
    else:
        current_dir = os.path.dirname(current_file)

    if filename.startswith('/') or filename == '-':
        path = filename
    else:
        path = os.path.abspath(os.path.join(current_dir, filename)) # resolve relative paths
    if expandafterload:
        bindings['__FILE__'] = path # New file now

    # Do the load/parse
    result = file_types[suffix]()
    bindings['__FILE__'] = current_file # restore prior file
    return result


def new_globals():
    """
    Construct a new Yamp environment of globals.
    :return: New global dict
    """
    global_environment = {'__FILE__': None, 'argv' : sys.argv, 'env': os.environ.copy()}
    add_builtins_to_env(global_environment)    
    return global_environment


if __name__ == '__main__':

    if len(sys.argv) < 2:
        print('ERROR: no files to scan', file=sys.stderr)
        sys.exit(1)

    filename  = sys.argv[1]
    expand_file(filename, new_globals(), expandafterload=True, outputfile=sys.stdout)


