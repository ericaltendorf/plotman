#!/usr/bin/python3

from unittest.mock import patch
import unittest
import manager
import job

class TestManager(unittest.TestCase):
    @patch('job.Job')
    def job_w_tmpdir_phase(self, tmpdir, phase, MockJob):
        j = MockJob()
        j.progress.return_value = phase
        j.tmpdir = tmpdir
        return j

    def test_job_phases_for_dir_filter_and_sort(self):
        all_jobs = [ self.job_w_tmpdir_phase('/tmp1', (1, 5)),
                     self.job_w_tmpdir_phase('/tmp2', (1, 1)),
                     self.job_w_tmpdir_phase('/tmp2', (3, 1)),
                     self.job_w_tmpdir_phase('/tmp2', (2, 1)),
                     self.job_w_tmpdir_phase('/tmp3', (4, 1)) ]
        
        result = manager.job_phases_for_dir('/tmp2', all_jobs)
        self.assertEqual(result, [(1, 1), (2, 1), (3, 1)])

    def test_permit_new_job_yes(self):
        self.assertTrue(manager.phases_permit_new_job(
            [ (3, 1), (4, 1) ] ))
        self.assertTrue(manager.phases_permit_new_job(
            [ (2, 1), (3, 1) ] ))

    def test_permit_new_job_multiple_in_phase_2(self):
        self.assertFalse(manager.phases_permit_new_job(
            [ (2, 1), (2, 1), (3, 1) ] ))

    def test_permit_new_job_current_job_in_phase_1(self):
        self.assertFalse(manager.phases_permit_new_job(
            [ (1, 1), (4, 1) ] ))

    def test_permit_new_job_too_many_total_jobs(self):
        self.assertFalse(manager.phases_permit_new_job(
            [ (4, 1), (4, 2), (4, 3), (4, 4) ] ))

    def test_tmpdir_phases_str(self):
        self.assertEqual('/tmp/foo: (1:3, 2:5, 4:1)',
                manager.tmpdir_phases_str(('/tmp/foo', [(1, 3), (2, 5), (4, 1)])))

    def test_tmpdir_phases_str_sorting(self):
        self.assertEqual('/tmp/foo: (1:3, 2:5, 4:1)',
                manager.tmpdir_phases_str(('/tmp/foo', [(2, 5), (4, 1), (1, 3)])))

if __name__ == '__main__':
    unittest.main()
