import typing
# TODO: migrate away from unittest patch
from unittest.mock import patch

import pytest

from plotman import configuration, job, manager


@pytest.fixture
def sched_cfg() -> configuration.Scheduling:
    return configuration.Scheduling(
        global_max_jobs=1,
        global_stagger_m=2,
        polling_time_s=2,
        tmpdir_stagger_phase_major=3,
        tmpdir_stagger_phase_minor=0,
        tmpdir_max_jobs=3,
        tmp_overrides={"/mnt/tmp/04": configuration.TmpOverrides(tmpdir_max_jobs=4)}
    )

@pytest.fixture
def dir_cfg() -> configuration.Directories:
    return configuration.Directories(
        tmp=["/var/tmp", "/tmp"],
        dst=["/mnt/dst/00", "/mnt/dst/01", "/mnt/dst/03"]
    )

def test_permit_new_job_post_milestone(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (3, 8), (4, 1) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_pre_milestone(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (2, 3), (4, 1) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs_zerophase(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (3, 0), (3, 1), (3, 3) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_too_many_jobs_nonephase(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (None, None), (3, 1), (3, 3) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/00', sched_cfg, dir_cfg)

def test_permit_new_job_override_tmp_dir(sched_cfg: configuration.Scheduling, dir_cfg: configuration.Directories) -> None:
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3) ])
    assert manager.phases_permit_new_job(
        phases, '/mnt/tmp/04', sched_cfg, dir_cfg)
    phases = job.Phase.list_from_tuples([ (3, 1), (3, 2), (3, 3), (3, 6) ])
    assert not manager.phases_permit_new_job(
        phases, '/mnt/tmp/04', sched_cfg,
        dir_cfg)

@patch('plotman.job.Job')
def job_w_tmpdir_phase(tmpdir: str, phase: job.Phase, MockJob: typing.Any) -> typing.Any:
    j = MockJob()
    j.progress.return_value = phase
    j.tmpdir = tmpdir
    return j

@patch('plotman.job.Job')
def job_w_dstdir_phase(dstdir: str, phase: job.Phase, MockJob: typing.Any) -> typing.Any:
    j = MockJob()
    j.progress.return_value = phase
    j.dstdir = dstdir
    return j

def test_dstdirs_to_furthest_phase() -> None:
    all_jobs = [ job_w_dstdir_phase('/plots1', job.Phase(1, 5)),
                 job_w_dstdir_phase('/plots2', job.Phase(1, 1)),
                 job_w_dstdir_phase('/plots2', job.Phase(3, 1)),
                 job_w_dstdir_phase('/plots2', job.Phase(2, 1)),
                 job_w_dstdir_phase('/plots3', job.Phase(4, 1)) ]

    assert (manager.dstdirs_to_furthest_phase(all_jobs) ==
            { '/plots1' : job.Phase(1, 5),
              '/plots2' : job.Phase(3, 1),
              '/plots3' : job.Phase(4, 1) } )


def test_dstdirs_to_youngest_phase() -> None:
    all_jobs = [ job_w_dstdir_phase('/plots1', job.Phase(1, 5)),
                 job_w_dstdir_phase('/plots2', job.Phase(1, 1)),
                 job_w_dstdir_phase('/plots2', job.Phase(3, 1)),
                 job_w_dstdir_phase('/plots2', job.Phase(2, 1)),
                 job_w_dstdir_phase('/plots3', job.Phase(4, 1)) ]

    assert (manager.dstdirs_to_youngest_phase(all_jobs) ==
            { '/plots1' : job.Phase(1, 5),
              '/plots2' : job.Phase(1, 1),
              '/plots3' : job.Phase(4, 1) } )
