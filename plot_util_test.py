#!/usr/bin/python3

# from unittest.mock import patch
from pyfakefs.fake_filesystem_unittest import TestCase

from plot_util import GB

import os
import pyfakefs
import unittest

import plot_util

class TestPlotUtil(unittest.TestCase):
    def test_human_format(self):
        self.assertEqual('3G', plot_util.human_format(3442000000, 0))
        self.assertEqual('3.54M', plot_util.human_format(3542000, 2))
        self.assertEqual('354', plot_util.human_format(354, 0))
        self.assertEqual('354.00', plot_util.human_format(354, 2))

    def test_time_format(self):
        self.assertEqual('34s', plot_util.time_format(34))
        self.assertEqual('59s', plot_util.time_format(59))
        self.assertEqual('0:01', plot_util.time_format(60))
        self.assertEqual('0:01', plot_util.time_format(119))
        self.assertEqual('0:02', plot_util.time_format(120))
        self.assertEqual('1:01', plot_util.time_format(3694))

    def test_split_path_prefix(self):
        self.assertEqual(
                ('', []),
                plot_util.split_path_prefix( [] ) )
        self.assertEqual(
                ('', ['/a/0', '/b/1', '/c/2']),
                plot_util.split_path_prefix([ '/a/0', '/b/1', '/c/2' ]) )
        self.assertEqual(
                ('/a/b', ['0', '1', '2']),
                plot_util.split_path_prefix([ '/a/b/0', '/a/b/1', '/a/b/2' ]) )

    def test_columns(self):
        self.assertEqual(
                [ [ 0, 3, 6 ],
                  [ 1, 4, 7 ],
                  [ 2, 5, '--'] ],
                plot_util.column_wrap(list(range(8)), 3, filler='--') )
        self.assertEqual(
                [ [ 0, 3, 6 ],
                  [ 1, 4, 7 ],
                  [ 2, 5, 8 ] ],
                plot_util.column_wrap(list(range(9)), 3, filler='--') )
        self.assertEqual(
                [ [ 0 ],
                  [ 1 ],
                  [ 2 ] ],
                plot_util.column_wrap(list(range(3)), 1, filler='--') )


class TestPlotUtilFiles(TestCase):
    def setUp(self):
        self.setUpPyfakefs()

    def test_list_k32_plots(self):
        self.fs.create_file('/t/plot-k32-0.plot', st_size=108 * GB)
        self.fs.create_file('/t/plot-k32-1.plot', st_size=108 * GB)
        self.fs.create_file('/t/.plot-k32-2.plot', st_size=108 * GB)
        self.fs.create_file('/t/plot-k32-3.plot.2.tmp', st_size=108 * GB)
        self.fs.create_file('/t/plot-k32-4.plot', st_size=100 * GB)
        self.fs.create_file('/t/plot-k32-5.plot', st_size=108 * GB)

        self.assertEqual( [ '/t/plot-k32-0.plot',
                            '/t/plot-k32-1.plot',
                            '/t/plot-k32-5.plot' ],
                plot_util.list_k32_plots('/t/') )


if __name__ == '__main__':
    unittest.main()
