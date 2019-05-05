import os, sys
import yaml
import StringIO
import unittest
import filecmp
import tempfile
from pprint import pprint

curr_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(curr_path + '/../src')

from yamp import *

real_expand = expand

def expand(tree, env):
    """
    Provide expand() function for testing that incorporates builtins.
    """
    global_env =  new_globals()
    global_env.update(env)
    return real_expand(tree, global_env)


class TestYamp(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testPassthrough(self):
        self.assertEqual([{'nothing': 23}], expand([{'nothing': 23}], {}))

    def testScalars(self):
        self.assertEqual([23], expand([{'define': {'name': 'var', 'value': 23}}, 'var'], {}))
        self.assertEqual(expand('FOO', {'FOO':12, 'BAR': 22}),  12)
        self.assertEqual(expand(['FOO'], {'FOO':12, 'BAR': 22}) ,  [12])
        self.assertEqual(expand({'FOO': 'bar'}, {'FOO':12, 'BAR': 22}) ,  {'FOO': 'bar'})
        self.assertEqual(expand({'quux': {'FOO': 'bar'}}, {'FOO':12, 'BAR': 22}) , {'quux': {'FOO': 'bar'}})
        self.assertEqual(expand([{'quux': {'FOO': 'bar'}}], {'FOO':12, 'BAR': 22}) ,  [{'quux': {'FOO': 'bar'}}])

    def testQuote(self):
        self.assertEqual({'+': 'var', 'value': 23}, expand({'quote': {'+': 'var', 'value': 23}}, {}))
        self.assertEqual([{'+': 'var', 'value': 23}], expand([{'quote': {'+': 'var', 'value': 23}}], {}))
        self.assertEqual({'a': {'+': 'var', 'value': 23}}, expand({'a': {'quote': {'+': 'var', 'value': 23}}}, {}))
        self.assertEqual([1022], expand([
            {'define': {'X' : {'quote': {'+': [22,1000]}}}}, 
            'X'], {}))

    def testScalarsBad(self):
        with self.assertRaises(Exception) as context:
            self.assertEqual([99], expand([{'define': {'name': 123, 'value': 23}}, 123], {}))

    def testMultiDefine(self):
        self.assertEqual(expand([{'define': {'name': 'v1', 'value': 11}},
            {'define': {'v2': 12}},'v1', 'v2'], {}), [11,12])
        self.assertEqual(expand([
            {'define': {
                'v1': 11,
                'v2': 12
            }},'v1', 'v2'], {}), [11, 12])

    def testMultiDefineSwap(self):
        self.assertEqual(expand([
            {'define': {
                'a': 9,
                'b': 40
            }},
           {'define': {
                'a': 'b',
                'b': 'a'
            }},
             'a', 'b'],{}), [40 , 9])

    def testMultiDefineData(self):
        self.assertEqual(expand([
            {'define': 'data'},
             'apple', 'pear'],
             {'data': {'apple': 12, 'pear': 88}}), [12 , 88])

    def testExpandKeys(self):
        self.assertEqual(expand({'varikey_{{FOO}}' : None}, {'FOO':12, 'BAR': 77}),  {'varikey_12': None})
        self.assertEqual(expand({'varikey_{{FOO}}' : {'varikey2_{{BAR}}' : None}}, {'FOO':12, 'BAR': 77}),  {'varikey_12': {'varikey2_77' : None}})
        self.assertEqual(expand({'{{FOO}}' : [1,3]}, {'FOO': 'range', 'BAR': 77}),  {'range': [1, 3]})

    def testLevels(self):
        self.assertEqual([42], expand(['one'], {'one': 'two', 'two': 'three', 'three': 42}))

    def testRepeats(self):
        self.assertEqual([42, 42, 42, {2: {'m': [42, 42]}, 'm': 42}], 
            expand(['m', 'm', 'm', {'m': 'm', 2: {'m': ['m', 'm'] } } ], {'m': 42}))

    def testList(self):
        self.assertEqual([[1, 2, 3, 4]],
            expand([{'define' : {'name': 'xl', 'value': [1,2,3,4]}},
                'xl'],{}))

    def testComplexValue(self):
        self.assertEqual([{'date': '1/1/1970', 'level2': {'p1': 34, 'p2': 44}, 'list': [1, 2, 3]}],
            expand([{'define' : {'name': 'comp', 'value': {
                'date' : '1/1/1970', 
                'list': [1,2,3], 
                'level2': {
                    'p1': 34,
                    'p2': 44
                }}}},
                'comp'],{}))

    def testBoolean(self):
        self.assertEqual([True, False],
            expand([{'define' : {'name': 't', 'value': True}},
                    {'define' : {'name': 'f', 'value': False}},
                't', 'f'],{}))

    def testIf(self):
        self.assertEqual(12, expand({'if' : True, 'then': 12, 'else': 99},{}))
        self.assertEqual(99, expand({'if' : False, 'then': 12, 'else': 99},{}))
        self.assertEqual(99, expand({'if' : None, 'then': 12, 'else': 99},{}))
        self.assertEqual(22, expand({'if' : True, 'then': 'y', 'else': 99},{'x': 22, 'y': 'x'}))
        self.assertEqual(99, expand({'if' : False, 'then': 'y', 'else': 99},{'x': 22, 'y': 'x'}))
        self.assertEqual(99, expand({'if' : False, 'else': 99}, {'x': 22, 'y': 'x'}))
        self.assertEqual(None, expand({'if' : True, 'else': 99}, {'x': 22, 'y': 'x'}))
        self.assertEqual(None, expand({'if' : False, 'then': 99}, {'x': 22, 'y': 'x'}))
        self.assertEqual(None, expand({'if' : None, 'then': 99}, {'x': 22, 'y': 'x'}))
        self.assertEqual(22, expand({'if' : True, 'then': 'y'},{'x': 22, 'y': 'x'}))

    def testIfBad(self):
        with self.assertRaises(Exception) as context:
            expand({'if' : True}, {'x': 22, 'y': 'x'})
        self.assertTrue('Syntax' in context.exception.message)
        with self.assertRaises(Exception) as context:
            expand({'if' : True, 'then': 12, 'else': 99, 'banana':None}, {'x': 22, 'y': 'x'})
        self.assertTrue('Syntax' in context.exception.message)
        for item in [32, 'ss', [1], {'a':2}]:
            with self.assertRaises(Exception) as context:
                expand({'if' : item, 'then': 12, 'else': 99}, {'x': 22, 'y': 'x'})
            self.assertTrue('If condition' in context.exception.message)


    def testEqual(self):
        self.assertEqual(False, expand({'==' : [12, 0]}, {}))
        self.assertEqual(True, expand({'==' : [12, 12]}, {}))
        self.assertEqual(False, expand({'==' : ['x', 0]}, {'x': 12}))
        self.assertEqual(True, expand({'==' : ['x', 12]}, {'x': 12}))
        self.assertEqual(True, expand({'==' : ['x', 12, 12 , 12 , 12]}, {'x': 12}))
        self.assertEqual(False, expand({'==' : ['x', 12, 12 , 12 , 99]}, {'x': 12}))

    def testPlus(self):
        self.assertEqual(49, expand({'+' : [12, 37]}, {}))
        self.assertEqual(8, expand({'+' : [-12, 20]}, {}))
        self.assertEqual(6.2, expand({'+' : [5, 1.2]}, {}))

    def testBadPlus(self):
        with self.assertRaises(Exception) as context:
            expand({'+' : ['12', 37]}, {})
        self.assertTrue('Was expecting number in' in context.exception.message)

    def testIfEqual(self):
        self.assertEqual(99, expand({'if' : {'==' : ['x', 0]}, 'then': 12, 'else': 99},{'x': 12}))
        self.assertEqual(12, expand({'if' : {'==' : ['x', 12]}, 'then': 12, 'else': 99},{'x': 12}))

    def testMacroNoArgs(self):
        self.assertEqual([[1, 2, 3, {4: 5}]], expand([
            {'defmacro':
                {'name' : 'amac',
                'args' : [],
                'value' : [1,2,3,{4: 5}]}},
             {'amac': None}], {}))

    def testMacroTooManyArgs(self):
        with self.assertRaises(Exception) as context:
            expand([
                {'defmacro':
                    {'name' : 'amac',
                    'args' : [],
                    'value' : [1,2,3,{4: 5}]}},
                 {'amac': {'extra': None}}], {})
        self.assertTrue('Too many args for' in context.exception.message)

    def testMacroTooManyArgs02(self):
        with self.assertRaises(Exception) as context:
            expand([
                {'defmacro':
                    {'name' : 'maco',
                    'args' : ['p1', 'p2'],
                    'value' : [1,2]}},
                {'maco': {'p1': 1, 'p2': 2, 'extra': None}}], {})
        self.assertTrue('Argument mismatch in' in context.exception.message)

    def testMacroBadKeys(self):
        with self.assertRaises(Exception) as context:
            expand([
                {'defmacro':
                    {'name' : 'maco',
                    'args' : ['p1', 'p2'],
                    'value' : [1,2]}},
                {'maco': {'p1': 1, 'p2': 2}, 'extra': 2}], {})
        self.assertTrue('too many keys in macro' in context.exception.message)

    def testMacroBadArgs(self):
        with self.assertRaises(Exception) as context:
            expand([
                {'defmacro':
                    {'name' : 'maco',
                    'args' : ['p1', 'p2'],
                    'value' : [1,2]}},
                {'maco': 'p1, p2'}], {})
        self.assertTrue('Expecting dict' in context.exception.message)

    def testMacro01(self):
        self.assertEquals(
            [[1, [1, 2, {'a': 3, 'b': 4}]]],
            expand([
                {'defmacro':
                    {'name' : 'maco1',
                    'args' : ['p1', 'p2'],
                    'value' : ['p1','p2']}},
                {'maco1': {'p1': 1, 'p2': ['p1',2,{'a': 3, 'b': 4}]}}], {'a': 33}))

    def testMacroVarargsNone(self):
        self.assertEquals(
            [],
            expand([
                {'defmacro':
                    {'name' : 'vmac',
                    'args' : 'all',
                    'value' : 'all'}},
                {'vmac': None}], {'a': 33}))

    def testMacroVarargs(self):
        self.assertEquals(
            [{'a': 3, 'b': 4}],
            expand([
                {'defmacro':
                    {'name' : 'vmac',
                    'args' : 'all',
                    'value' : 'all.p2.2'}},
                {'vmac': {'p1': 1, 'p2': ['p1',2,{'a': 3, 'b': 4}]}}], {'a': 33}))

    def testMacroVarargsList(self):
        self.assertEquals(
            [33],
            expand([
                {'defmacro':
                    {'name' : 'vmac',
                    'args' : 'all',
                    'value' : 'all.0' }},
                {'vmac': ['a', 'b']}], {'a': 33}))

    def testMacroInDict(self):
        self.assertEquals(
            [{1: None}, [1, [1, 2, {'a': 3, 'b': 4}]]],
            expand([
                {1: {'defmacro':
                    {'name' : 'maco1',
                    'args' : ['p1', 'p2'],
                    'value' : ['p1','p2']}}},
                {'maco1': {'p1': 1, 'p2': ['p1',2,{'a': 3, 'b': 4}]}}], {'a': 33}))

    def testMacroScalar(self):
        self.assertEquals(
            [987],
            expand([
                {'defmacro':
                    {'name' : 'mac1',
                    'args' : ['x'],
                    'value' : 'x'}},
                {'mac1': {'x': 987}}], {}))

    def testMacroNested(self):
        self.assertEquals(
            [[[23, 33], [23, 111]]],
            expand([
                {'defmacro':
                    {'name' : 'mac1',
                    'args' : ['x'],
                    'value' : 'x'}},
                {'defmacro':
                    {'name' : 'mac2',
                    'args' : ['p1', 'p2'],
                    'value' : [{'mac1': {'x': 23}},'p2']}},
                {'defmacro':
                    {'name' : 'mac3',
                    'args' : ['x1', 'x2'],
                    'value' : [
                        {'mac2': {'p1': 'x1', 'p2': 'x2'}},
                        {'mac2': {'p1': 'x2', 'p2': 'x1'}}]}},
                {'mac3': {'x1': 111, 'x2': 'a'}}], {'a': 33}))

    def testMacroLexicalScope(self):
        self.assertEquals(
            [[1000, 42]],
            expand([
                {'define': {'name': 'x', 'value': 1000}},
                {'define': {'name': 'y', 'value': 2000}},
                {'defmacro':
                    {'name' : 'outer',
                    'args' : ['y'],
                    'value' : [
                        {'defmacro':
                            {'name' : 'inner',
                            'args' : None,
                            'value' : 'x'}},
                        {'inner': None}, 'y']}},
                {'outer': {'y': 42}}], {'x': 33, 'y': 34}))

    def testSubVarExactFirst(self):
        global_env = {'l0sub.l1sub.l2': 'takes precedence',
                       'l0sub.l1sub.': 99, 
                        'l0sub': {'l1': 1, 'l1sub': {'l2': 2}}}
        self.assertEquals(99, expand('l0sub.l1sub.', global_env))
        self.assertEquals('takes precedence', expand('l0sub.l1sub.l2', global_env))
        self.assertEquals({'l1': 1, 'l1sub': {'l2': 2}}, expand('l0sub', global_env))

    def testSubVarDict1(self):
        global_env = {'l0': 0, 'l0sub': {'l1': 1, 'l1sub': {'l2': 2}}}
        self.assertEquals(0, expand('l0', global_env))
        self.assertEquals({'l1': 1, 'l1sub': {'l2': 2}}, expand('l0sub', global_env))
        self.assertEquals(1, expand('l0sub.l1', global_env))
        self.assertEquals(2, expand('l0sub.l1sub.l2', global_env))

    def testSubVarDict2(self):
        global_env = {'avar': 'l1sub', 'l0sub': {'l1': 1, 'l1sub': {'l2': 2}}}
        self.assertEquals({'l2': 2}, expand('l0sub.avar', global_env))
        self.assertEquals(2, expand('l0sub.avar.l2', global_env))

    def testSubVarBad(self):
        global_env = {'l0': 0, 'l0sub': {'l1': 1, 'l1sub': {'l2': 2}}}
        with self.assertRaises(Exception) as context:
            expand('l0.ZZZ', global_env)
        self.assertTrue('Subvariable' in context.exception.message)

    def testSubVarBadDeep(self):
        global_env = {'l0': 0, 'l0sub': {'l1': 1, 'l1sub': {'l2': 2}}}
        with self.assertRaises(Exception) as context:
            expand('l0sub.l1sub.ZZZ', global_env)
        self.assertTrue('Subvariable' in context.exception.message)

    def testSubVarList(self):
        global_env = {'top': [0,1,2,3]}
        self.assertEquals([0,1,2,3], expand('top', global_env))
        self.assertEquals(0, expand('top.0', global_env))

    def testSubVarListBound(self):
        global_env = {'top': [0,1,2,3], 'two': 2}
        self.assertEquals([0,1,2,3], expand('top', global_env))
        self.assertEquals(2, expand('top.two', global_env))

    def testSubVarListDeep(self):
        global_env = {'top': {'two': {'three': [0,1,2,3]}}}
        self.assertEquals([0,1,2,3], expand('top.two.three', global_env))
        self.assertEquals(2, expand('top.two.three.2', global_env))

    def testSubVarCombined(self):
        global_env = {'top': [0, {'two': 42}]}
        self.assertEquals({'two': 42}, expand('top.1', global_env))
        self.assertEquals(42, expand('top.1.two', global_env))

    def testComplexSubvar(self):
        global_env = {'comp': {'date': '1/1/1970', 'level2': {'p1': 34, 'p2': 44}, 'list': [1, 2, 3]}}
        self.assertEqual('1/1/1970', expand('comp.date', global_env))
        self.assertEqual({'p1': 34, 'p2': 44}, expand('comp.level2', global_env))
        self.assertEqual(34, expand('comp.level2.p1', global_env))
        self.assertEqual(3, expand('comp.list.2', global_env))

    def testEnvironment(self):
        fake_global = {'env': {'HOME': '/home/elvis'}}
        self.assertEquals({'HOME': '/home/elvis'}, expand('env', fake_global))
        self.assertEquals('/home/elvis', expand('env.HOME', fake_global))

    def testReflection(self):
        fake_global = {'__FILE__' : 'testReflection', 'env': {'USERNAME': 'epresley'}}
        self.assertEquals('epresley', expand('env.USERNAME', fake_global))
        self.assertEquals('testReflection', expand('__FILE__', fake_global))

    def testStringInterpolation(self):
        bindings = {'A': 1, 'B' : 2, 'C' : { 'D' : 3}}
        self.assertEquals('', interpolate('', bindings))
        self.assertEquals('none', interpolate('none', bindings))
        self.assertEquals('{{A', interpolate('{{A', bindings))
        self.assertEquals('A}}', interpolate('A}}', bindings))
        self.assertEquals(' 1 ', interpolate(' {{A}} ', bindings))
        self.assertEquals(' 1 ', interpolate(' {{  A }} ', bindings))
        self.assertEquals('A = 1 B = 2', interpolate('A = {{A}} B = {{B}}', bindings))
        self.assertEquals("A = 1 B = 2 C = {'D': 3}", interpolate('A = {{A}} B = {{B}} C = {{C}}', bindings))
        self.assertEquals("A = 1 C.D = 3", interpolate('A = {{A}} C.D = {{C.D}}', bindings))

    def testStringInterpolationExpansion(self):
        bindings = {'A': 1, 'B' : 2, 'C' : { 'D' : 3}}
        self.assertEquals(' 1 ', expand(' {{A}} ', bindings))
        self.assertEquals('A = 1 B = 2', expand('A = {{A}} B = {{B}}', bindings))
        self.assertEquals("A = 1 B = 2 C = {'D': 3}", expand('A = {{A}} B = {{B}} C = {{C}}', bindings))
        self.assertEquals("A = 1 C.D = 3", expand('A = {{A}} C.D = {{C.D}}', bindings))

    def testStringInterpolationUndefined(self):
        bindings = {'A': 1}
        with self.assertRaises(Exception) as context:
            expand(' {{QUUX}} ', bindings)
        self.assertTrue('ndefined' in context.exception.message)

    def testRepeatListNull(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [],
            'body': ['hello mum', 'iteration {{ loop_variable }}']
            }}
        expected = []
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatList(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [1,2],
            'body': ['hello mum', 'iteration {{ loop_variable }}']
            }}
        expected = [['hello mum', 'iteration 1'],
                    ['hello mum', 'iteration 2']]
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatListBig(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [1,2],
            'body': {'data': ['hello mum', {'data': 'iteration {{ loop_variable }}'}]}
            }}
        expected = [{'data': ['hello mum', {'data': 'iteration 1'}]},
                    {'data': ['hello mum', {'data': 'iteration 2'}]}]
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatListNested(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'outer_loop_variable',
            'in': [1,2],
            'body': {'repeat':
                {'for': 'inner_loop_variable',
                 'in': [1,2],
                 'body': 'iteration {{ inner_loop_variable }} {{ outer_loop_variable }}'}}}}
        expected = [['iteration 1 1', 'iteration 2 1'],
                    ['iteration 1 2', 'iteration 2 2']]
        self.assertEquals(expected, expand(expression, bindings))

    def testRange(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'range': [1,3]}
        expected = [1,2,3]
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatListRange(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'outer_loop_variable',
            'in': {'range': [1, 3]},
            'body': 'iteration {{ outer_loop_variable }}'}}
        expected = ['iteration 1', 'iteration 2', 'iteration 3']
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatDictNull(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [],
            'key': 'qq',
            'body': ['hello mum', 'iteration {{ loop_variable }}']
            }}
        expected = {}
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatDictRange(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': {'range': [1,2]},
            'key': 'K{{loop_variable}}',
            'body': ['hello mum', 'iteration {{ loop_variable }}']
            }}
        expected = {'K1': ['hello mum', 'iteration 1'],
                    'K2' : ['hello mum', 'iteration 2']}
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatDict(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [1,2],
            'key': 'K{{loop_variable}}',
            'body': ['hello mum', 'iteration {{ loop_variable }}']
            }}
        expected = {'K1': ['hello mum', 'iteration 1'],
                    'K2' : ['hello mum', 'iteration 2']}
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatDictNested(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [1,2],
            'key': 'K{{loop_variable}}',
            'body': { 'repeat':
                {'for': 'inner_variable',
                'in': ['a', 'b'],
                'key': 'K{{inner_variable}}',
                'body':
                    ['hello mum', 'iteration {{ loop_variable }} {{ inner_variable }}']}}}}
        expected = {'K1': {'Ka': ['hello mum', 'iteration 1 a'],
                           'Kb': ['hello mum', 'iteration 1 b']},
                    'K2': {'Ka': ['hello mum', 'iteration 2 a'],
                           'Kb': ['hello mum', 'iteration 2 b']}}
        self.assertEquals(expected, expand(expression, bindings))

    def testRepeatDictListNested(self):
        bindings = {'A': 1, 'B' : 2}
        expression = {'repeat':{
            'for': 'loop_variable',
            'in': [1,2],
            'key': 'K{{loop_variable}}',
            'body': { 'repeat':
                {'for': 'inner_variable',
                'in': ['a', 'b'],
                'body':
                    ['hello mum', 'iteration {{ loop_variable }} {{ inner_variable }}']}}}}
        expected = {'K1': [['hello mum', 'iteration 1 a'],
                          ['hello mum', 'iteration 1 b']],
                    'K2': [['hello mum', 'iteration 2 a'],
                          ['hello mum', 'iteration 2 b']]}
        self.assertEquals(expected, expand(expression, bindings))

    def testPython(self):
        bindings = {'A': 1, 'B' : 2}
        self.assertEquals([1, 2], expand({'python': '[A, B]'}, bindings))
        self.assertEquals(3, expand({'python': 'B + A'}, bindings))

    def testInclude(self):
        global_environment = {
            '__FILE__' : os.path.abspath(__file__),
            'FILENAME' : 'file2',
            '__current_output__' : StringIO.StringIO()}
        current_directory = os.path.dirname(os.path.abspath(__file__))

        self.assertEquals([
            os.path.join(current_directory, 'fixtures/file1.yamp'),
            os.path.join(current_directory, 'fixtures/file2.yaml')],
             expand([
                {'include': ['fixtures/file1.yamp', 'fixtures/{{FILENAME}}.yaml']},
                '$f1',
                '$f2'], global_environment))

    def testLoad(self):
        global_environment = {
            '__FILE__' : os.path.abspath(__file__),
            'DIRNAME' : 'fixtures',
            '__current_output__' : sys.stdout}
        add_builtins_to_env(global_environment)
        self.assertEquals(
             [{'dev':   {'webserver': {'hostname': 'web02', 'ip': '1.1.2.4'}},
               'perf0': {'webserver': {'hostname': 'web01', 'ip': '1.1.2.3'}}},
              {'qa1':   {'webserver': {'hostname': 'web04', 'ip': '1.2.2.4'}},
               'sit':   {'webserver': {'hostname': 'web03', 'ip': '1.2.2.3'}}}],
             expand({'load': '{{DIRNAME}}/data1.yaml'}, global_environment))

    def testLoadJSON(self):
        global_environment = {
            '__FILE__' : os.path.abspath(__file__),
            '__current_output__' : sys.stdout}
        add_builtins_to_env(global_environment)
        self.assertEquals(
             'Blade Runner',
             expand({'load': 'fixtures/blade-runner.json'}, global_environment)[u'name'])
        self.assertEquals(
             'Blade Runner 2049',
             expand({'load': 'fixtures/blade-runner-2049.json'}, global_environment)[u'name'])

    def testFlattenList(self):
        self.assertEquals([1,2,3,4], flatten_list([1,[2],[[3]],[[[4]]]], {}))
        self.assertEquals([1,'a',3,4], flatten_list([1,['a'],[[3]],[[[4]]]], {}))
        self.assertEquals([1,2,{'x':22},4], flatten_list([1,[2],[[{'x':22}]],[[[4]]]], {}))

    def testFlatoneList(self):
        self.assertEquals([1,2,[3],[[4]]], flat_list(1, [1,[2],[[3]],[[[4]]]]))
        self.assertEquals([1,'a',[3],[[4]]], flat_list(1, [1,['a'],[[3]],[[[4]]]]))
        self.assertEquals([1,2,{'x':22},[4]], flat_list(2, [1,[2],[[{'x':22}]],[[[4]]]]))

    def testFlatten(self):
        self.assertEquals(
             [1,2,3],
             expand({'flatten': [1,[2],[[3]]]}, {}))

    def testMergeDict(self):
        self.assertEquals(
            {'a': 1, 'b': 2, 'c': 3},
            expand({'merge': [{'a':1},{'b':2},{'c':3}]}, {}))

    def testMergeDictInternal(self):
        self.assertEquals({'a':1, 'b':2, 'c':3}, merge_maps([{'a':1},{'b':2},{'c':3}],{}))
        self.assertEquals({'a':1, 'b':2, 'c':3}, merge_maps([{'a':1, 'c':99},{'b':2},{'c':3}],{}))

    def testMergeDictBad(self):
        with self.assertRaises(Exception) as context:
            merge_maps([12,{'a':1, 'c':99},{'b':2},{'c':3}],{})
        self.assertTrue('Error: non-map' in context.exception.message)

    def runFileRegression(self, file_to_test, fixture):
        tempout = tempfile.mkstemp()
        outputfilestream = open(tempout[1], 'w+')
        path_to_test = os.path.join(curr_path, file_to_test)
        path_fixture = os.path.join(curr_path, fixture)
        global_environment = { 'argv': [], '__FILE__' :  path_to_test } # Fake environments
        add_builtins_to_env(global_environment)    
        expand_file(path_to_test, global_environment, expandafterload=True, outputfile=outputfilestream)
        outputfilestream.close()
        
        self.assertTrue(filecmp.cmp(tempout[1], path_fixture, shallow=False),
            'Output file from "{}" not matching fixture: "{}" "{}"'.format(file_to_test, tempout[1], fixture))


    def testREADME(self):
        self.runFileRegression('../examples/readme.yaml','fixtures/readme.output.yaml')

    def testAllExamples(self):
        self.runFileRegression('../test/all-examples.yaml','fixtures/all-examples.output.yaml')



if __name__ == '__main__':
    unittest.main()
