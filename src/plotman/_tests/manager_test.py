# TODO: migrate away from unittest patch
from unittest.mock import patch

import pytest

from plotman import configuration, job, manager


@pytest.fixture
def sched_cfg():
    return configuration.Scheduling(
        global_max_jobs=1,
        global_stagger_m=2,
        polling_time_s=2,
        tmpdir_stagger_phase_major=3,
        tmpdir_stagger_phase_minor=0,
        tmpdir_max_jobs=3
    )

@pytest.fixture
def dir_cfg():
    return configuration.Directories(
        tmp=["/var/tmp", "/tmp"],
        dst=["/mnt/dst/00", "/mnt/dst/01", "/mnt/dst/03"],
        tmp_overrides={"/mnt/tmp/04": configuration.TmpOverrides(tmpdir_max_jobs=4)}
    )

def test_permit_new_job_post_milestone(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (3, 8), (4, 1) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_pre_milestone(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (2, 3), (4, 1) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs_zerophase(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (3, 0), (3, 1), (3, 3) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs_nonephase(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (None, None), (3, 1), (3, 3) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_override_tmp_dir(sched_cfg, dir_cfg):
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/04', sched_cfg, dir_cfg)
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3), (3, 6) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/04', sched_cfg,
        dir_cfg)

@patch('plotman.job.Job')
def job_w_tmpdir_phase(tmpdir, phase, MockJob):
    j = MockJob()
    j.progress.return_value = phase
    j.tmpdir = tmpdir
    return j

@patch('plotman.job.Job')
def job_w_dstdir_phase(dstdir, phase, MockJob):
    j = MockJob()
    j.progress.return_value = phase
    j.dstdir = dstdir
    return j

def test_dstdirs_to_furthest_phase():
    all_jobs = [ job_w_dstdir_phase('/plots1', (1, 5)),
                 job_w_dstdir_phase('/plots2', (1, 1)),
                 job_w_dstdir_phase('/plots2', (3, 1)),
                 job_w_dstdir_phase('/plots2', (2, 1)),
                 job_w_dstdir_phase('/plots3', (4, 1)) ]

    assert (manager.dstdirs_to_furthest_phase(all_jobs) ==
            { '/plots1' : (1, 5),
              '/plots2' : (3, 1),
              '/plots3' : (4, 1) } )


def test_dstdirs_to_youngest_phase():
    all_jobs = [ job_w_dstdir_phase('/plots1', (1, 5)),
                 job_w_dstdir_phase('/plots2', (1, 1)),
                 job_w_dstdir_phase('/plots2', (3, 1)),
                 job_w_dstdir_phase('/plots2', (2, 1)),
                 job_w_dstdir_phase('/plots3', (4, 1)) ]

    assert (manager.dstdirs_to_youngest_phase(all_jobs) ==
            { '/plots1' : (1, 5),
              '/plots2' : (1, 1),
              '/plots3' : (4, 1) } )
