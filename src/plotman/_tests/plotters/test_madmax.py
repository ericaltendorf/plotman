import importlib.resources
import pathlib
import typing

import pendulum

import plotman.job
import plotman.plotters.madmax
import plotman._tests.resources


def test_byte_by_byte_full_load():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="madmax.plot.log",
    )

    parser = plotman.plotters.madmax.Plotter(cwd="", tmpdir="", dstdir="")

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.madmax.SpecificInfo(
        phase=plotman.job.Phase(major=5, minor=2),
        started_at=pendulum.datetime(2021, 7, 14, 21, 56, 0, tz=None),
        plot_id='3a3872f5a124497a17fb917dfe027802aa1867f8b0a8cbac558ed12aa5b697b2',
        p1_buckets=256,
        p34_buckets=256,
        threads=8,
        plot_size=32,
        tmp_dir='/farm/yards/902/',
        tmp2_dir='/farm/yards/902/fake_tmp2/',
        dst_dir='/farm/yards/902/fake_dst/',
        phase1_duration_raw=2197.52,
        phase2_duration_raw=1363.42,
        phase3_duration_raw=1320.47,
        phase4_duration_raw=86.9555,
        total_time_raw=4968.41,
        filename='',
        plot_name='plot-k32-2021-07-14-21-56-522acbd6308af7e229281352f746449134126482cfabd51d38e0f89745d21698',
    )


def test_log_phases():
    # TODO: CAMPid 0978413087474699698142013249869897439887
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="madmax.marked",
    )

    parser = plotman.plotters.madmax.Plotter(cwd="/", dstdir="", tmpdir="")

    wrong = []

    for marked_line in read_bytes.splitlines(keepends=True):
        phase_bytes, _, line_bytes = marked_line.partition(b",")
        phases_elements = tuple(int(p) for p in phase_bytes.decode("utf-8").split(":"))
        phase = plotman.job.Phase.from_tuple(t=phases_elements)

        parser.update(chunk=line_bytes)

        if parser.info.phase != phase:
            wrong.append([parser.info.phase, phase, line_bytes.decode("utf-8")])

    assert wrong == []


def test_marked_log_matches():
    # TODO: CAMPid 909831931987460871349879878609830987138931700871340870
    marked_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="madmax.marked",
    )
    log_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="madmax.plot.log",
    )

    for marked_line, log_line in zip(marked_bytes.splitlines(keepends=True), log_bytes.splitlines(keepends=True)):
        _, _, marked_just_line = marked_line.partition(b",")
        assert marked_just_line == log_line
