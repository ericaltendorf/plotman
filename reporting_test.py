#!/usr/bin/python3

# from unittest.mock import patch
from pyfakefs.fake_filesystem_unittest import TestCase

from plot_util import GB

import os
import pyfakefs
import unittest

import reporting

class TestReporting(unittest.TestCase):
    def test_phases_str(self):
        self.assertEqual('1:2 2:3 3:4 4:0',
            reporting.phases_str([(1,2), (2,3), (3,4), (4,0)]))
        self.assertEqual('1:2 [+1] 3:4 4:0',
            reporting.phases_str([(1,2), (2,3), (3,4), (4,0)], 3))
        self.assertEqual('1:2 [+2] 4:0',
            reporting.phases_str([(1,2), (2,3), (3,4), (4,0)], 2))
