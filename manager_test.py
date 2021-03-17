#!/usr/bin/python3

from unittest.mock import patch
import unittest
import manager
import job

class TestManager(unittest.TestCase):
    def setUp(self):
        self.sched_cfg = {
                'tmpdir_stagger_phase_major': 3,
                'tmpdir_stagger_phase_minor': 0,
                'tmpdir_max_jobs': 3 }
        self.dir_cfg = {
                'tmp_overrides': {
                        '/mnt/tmp/04': {
                                'tmpdir_max_jobs': 4 }}}

    @patch('job.Job')
    def job_w_tmpdir_phase(self, tmpdir, phase, MockJob):
        j = MockJob()
        j.progress.return_value = phase
        j.tmpdir = tmpdir
        return j

    @patch('job.Job')
    def job_w_dstdir_phase(self, dstdir, phase, MockJob):
        j = MockJob()
        j.progress.return_value = phase
        j.dstdir = dstdir
        return j

    def test_permit_new_job_post_milestone(self):
        self.assertTrue(manager.phases_permit_new_job(
            [ (3, 8), (4, 1) ], '/mnt/tmp/00', self.sched_cfg, self.dir_cfg))

    def test_permit_new_job_pre_milestone(self):
        self.assertFalse(manager.phases_permit_new_job(
            [ (2, 3), (4, 1) ], '/mnt/tmp/00', self.sched_cfg, self.dir_cfg))

    def test_permit_new_job_too_many_jobs(self):
        self.assertFalse(manager.phases_permit_new_job(
            [ (3, 1), (3, 2), (3, 3) ], '/mnt/tmp/00', self.sched_cfg,
            self.dir_cfg))

    def test_permit_new_job_override_tmp_dir(self):
        self.assertTrue(manager.phases_permit_new_job(
            [ (3, 1), (3, 2), (3, 3) ], '/mnt/tmp/04', self.sched_cfg,
            self.dir_cfg))
        self.assertFalse(manager.phases_permit_new_job(
            [ (3, 1), (3, 2), (3, 3), (3, 6) ], '/mnt/tmp/04', self.sched_cfg,
            self.dir_cfg))

    def test_dstdirs_to_furthest_phase(self):
        all_jobs = [ self.job_w_dstdir_phase('/plots1', (1, 5)),
                     self.job_w_dstdir_phase('/plots2', (1, 1)),
                     self.job_w_dstdir_phase('/plots2', (3, 1)),
                     self.job_w_dstdir_phase('/plots2', (2, 1)),
                     self.job_w_dstdir_phase('/plots3', (4, 1)) ]

        self.assertEqual(
                { '/plots1' : (1, 5),
                  '/plots2' : (3, 1),
                  '/plots3' : (4, 1) },
                manager.dstdirs_to_furthest_phase(all_jobs))


if __name__ == '__main__':
    unittest.main()
