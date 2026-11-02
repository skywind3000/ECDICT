# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import shutil
import struct
import tempfile
import unittest

import stardict


class StarDictExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.output = os.path.join(self.directory, 'dictionary.ifo')

    def tearDown(self):
        shutil.rmtree(self.directory)

    def read_output(self, extension):
        filename = os.path.splitext(self.output)[0] + extension
        with open(filename, 'rb') as stream:
            return stream.read()

    def test_export_preserves_utf8_title_and_binary_offsets(self):
        words = {
            'apple': '苹果',
            'Apple': '大写苹果',
            'éclair': '法式甜点',
            '猫': 'cat',
        }
        self.assertTrue(stardict.tools.export_stardict(
            words, self.output, '英汉词典'))

        expected_index = b''
        expected_dictionary = b''
        for word in sorted(words, key=lambda value: (value.lower(), value)):
            definition = words[word].encode('utf-8')
            expected_index += word.encode('utf-8') + b'\x00'
            expected_index += struct.pack(
                '>II', len(expected_dictionary), len(definition))
            expected_dictionary += definition
        self.assertEqual(self.read_output('.idx'), expected_index)
        self.assertEqual(self.read_output('.dict'), expected_dictionary)

        info = self.read_output('.ifo')
        self.assertNotIn(b'\r\n', info)
        lines = info.decode('utf-8').splitlines()
        self.assertEqual(lines[0], "StarDict's dict ifo file")
        metadata = dict(line.split('=', 1) for line in lines[1:])
        self.assertEqual(metadata['version'], '2.4.2')
        self.assertEqual(metadata['wordcount'], str(len(words)))
        self.assertEqual(metadata['idxfilesize'], str(len(expected_index)))
        self.assertEqual(metadata['bookname'], '英汉词典')
        self.assertEqual(metadata['sametypesequence'], 'm')

    def test_export_empty_dictionary(self):
        self.assertTrue(stardict.tools.export_stardict(
            {}, self.output, 'Empty dictionary'))
        self.assertEqual(self.read_output('.idx'), b'')
        self.assertEqual(self.read_output('.dict'), b'')
        info = self.read_output('.ifo').decode('utf-8')
        self.assertIn('wordcount=0\n', info)
        self.assertIn('idxfilesize=0\n', info)
        self.assertIn('bookname=Empty dictionary\n', info)


if __name__ == '__main__':
    unittest.main()
