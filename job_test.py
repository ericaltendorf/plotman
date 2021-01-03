#!/usr/bin/python3

from unittest.mock import patch
import unittest
import manager
import job

class TestJob(unittest.TestCase):
    def setUp(self):
        pass

    def test_job_phases_for_dir_filter_and_sort(self):
        all_jobs = [ self.job_w_tmpdir_phase('/tmp1', (1, 5)),
                     self.job_w_tmpdir_phase('/tmp2', (1, 1)),
                     self.job_w_tmpdir_phase('/tmp2', (3, 1)),
                     self.job_w_tmpdir_phase('/tmp2', (2, 1)),
                     self.job_w_tmpdir_phase('/tmp3', (4, 1)) ]
        
        result = manager.job_phases_for_tmpdir('/tmp2', all_jobs)
        self.assertEqual(result, [(1, 1), (2, 1), (3, 1)])


