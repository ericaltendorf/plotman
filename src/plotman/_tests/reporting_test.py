# TODO: migrate away from unittest patch
import os
from unittest.mock import patch

from plotman import reporting
from plotman import job


def test_phases_str_basic():
    phases = job.Phase.list_from_tuples([(1,2), (2,3), (3,4), (4,0)])
    assert reporting.phases_str(phases) == '1:2 2:3 3:4 4:0'

def test_phases_str_elipsis_1():
    phases = job.Phase.list_from_tuples([(1,2), (2,3), (3,4), (4,0)])
    assert reporting.phases_str(phases, 3) == '1:2 [+1] 3:4 4:0'

def test_phases_str_elipsis_2():
    phases = job.Phase.list_from_tuples([(1,2), (2,3), (3,4), (4,0)])
    assert reporting.phases_str(phases, 2) == '1:2 [+2] 4:0'

def test_phases_str_none():
    phases = job.Phase.list_from_tuples([(None, None), (3, 0)])
    assert reporting.phases_str(phases) == '?:? 3:0'

def test_job_viz_empty():
    assert(reporting.job_viz([]) == '1        2        3       4 ')

@patch('plotman.job.Job')
def job_w_phase(ph, MockJob):
    j = MockJob()
    j.progress.return_value = job.Phase.from_tuple(ph)
    return j

def test_job_viz_positions():
    jobs = [job_w_phase((1, 1)),
            job_w_phase((2, 0)),
            job_w_phase((2, 4)),
            job_w_phase((2, 7)),
            job_w_phase((4, 0))]

    assert(reporting.job_viz(jobs) == '1 .      2.   .  .3       4.')

def test_job_viz_counts():
    jobs = [job_w_phase((2, 2)),
            job_w_phase((2, 3)),
            job_w_phase((2, 3)),
            job_w_phase((2, 4)),
            job_w_phase((2, 4)),
            job_w_phase((2, 4)),
            job_w_phase((2, 5)),
            job_w_phase((2, 5)),
            job_w_phase((2, 5)),
            job_w_phase((2, 5)),
            job_w_phase((3, 1)),
            job_w_phase((3, 1)),
            job_w_phase((3, 1)),
            job_w_phase((3, 1)),
            job_w_phase((3, 1)),
            job_w_phase((3, 1)),
            ]

    assert(reporting.job_viz(jobs) == '1        2  .:;!  3 !     4 ')
