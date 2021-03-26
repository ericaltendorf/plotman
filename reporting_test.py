from unittest.mock import patch

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

    def test_job_viz_empty(self):
        self.assertEqual('1        2        3       4 ',
            reporting.job_viz([]) )

    @patch('job.Job')
    def job_w_phase(self, ph, MockJob):
        j = MockJob()
        j.progress.return_value = ph
        return j

    def test_job_viz_positions(self):
        jobs = [self.job_w_phase((1, 1)),
                self.job_w_phase((2, 0)),
                self.job_w_phase((2, 4)),
                self.job_w_phase((2, 7)),
                self.job_w_phase((4, 0))]

        self.assertEqual('1 .      2.   .  .3       4.',
            reporting.job_viz(jobs))

    def test_job_viz_counts(self):
        jobs = [self.job_w_phase((2, 2)),
                self.job_w_phase((2, 3)),
                self.job_w_phase((2, 3)),
                self.job_w_phase((2, 4)),
                self.job_w_phase((2, 4)),
                self.job_w_phase((2, 4)),
                self.job_w_phase((2, 5)),
                self.job_w_phase((2, 5)),
                self.job_w_phase((2, 5)),
                self.job_w_phase((2, 5)),
                self.job_w_phase((3, 1)),
                self.job_w_phase((3, 1)),
                self.job_w_phase((3, 1)),
                self.job_w_phase((3, 1)),
                self.job_w_phase((3, 1)),
                self.job_w_phase((3, 1)),
                ]

        self.assertEqual('1        2  .:;!  3 !     4 ',
            reporting.job_viz(jobs))

