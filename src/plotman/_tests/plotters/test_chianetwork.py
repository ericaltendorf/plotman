import importlib.resources

import pendulum
# import pytest

import plotman.job
import plotman.plotters.chianetwork
import plotman._tests.resources


clean_specific_info = plotman.plotters.chianetwork.SpecificInfo()


# @pytest.mark.parametrize(
#     argnames=["line"],
#     argvalues=[["Bucket"], [" Bucket"], ["\tBucket"]],
# )
# def test_ignore_line_matches(line):
# def test_ignore_line_matches():
#     assert (
#         plotman.plotters.chianetwork.ignore_line(
#             match=,
#             info=clean_specific_info,
#         )
#         is not None
#     )
#
#
# def test_ignore_line_does_not_match():
#     assert (
#         plotman.plotters.chianetwork.ignore_line(
#             line="Blue Bucket",
#             info=clean_specific_info,
#         )
#         is None
#     )
#
#
# def test_plot_id_extracts():
#     plot_id = "3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24"
#     info = plotman.plotters.chianetwork.plot_id(
#         line=f"ID: {plot_id}",
#         info=clean_specific_info,
#     )
#
#     assert info.plot_id == plot_id


def test_byte_by_byte_full_load():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="2021-04-04T19_00_47.681088-0400.log",
    )

    parser = plotman.plotters.chianetwork.Parser()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.chianetwork.SpecificInfo(
        process_id=None,
        phase=plotman.job.Phase(major=0, minor=0, known=False),
        started_at=pendulum.datetime(2021, 4, 4, 19, 0, 50, tz=None),
        plot_id='3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24',
        buckets=128,
        threads=4,
        buffer=4000,
        plot_size=32,
        tmp_dir1='/farm/yards/901',
        tmp_dir2='/farm/yards/901',
        phase1_duration_raw=17571.981,
        phase2_duration_raw=6911.621,
        phase3_duration_raw=14537.188,
        phase4_duration_raw=924.288,
        total_time_raw=39945.08,
        copy_time_raw=501.696,
        filename='/farm/wagons/801/plot-k32-2021-04-04-19-00-3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24.plot',
    )
