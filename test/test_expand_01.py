import os, sys
import yaml
import unittest

curr_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(curr_path + '/../src')

from yamp import *


def expand_str(yamlstr, env={}):
    return expand(yaml.load(yamlstr), {})

class testEval(unittest.TestCase):

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
        self.assertEqual(22, expand({'if' : True, 'then': 'y', 'else': 99},{'x': 22, 'y': 'x'}))
        self.assertEqual(99, expand({'if' : False, 'then': 'y', 'else': 99},{'x': 22, 'y': 'x'}))

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

    def testMacroTooManyArgs(self):
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

    def testMacroInDict(self):
        self.assertEquals(
            [{1:None}, [1, [1, 2, {'a': 3, 'b': 4}]]],
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



if __name__ == '__main__':
    unittest.main()