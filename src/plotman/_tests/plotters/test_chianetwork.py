import importlib.resources

# import pytest

import plotman.plotters.chianetwork
import plotman._tests.resources


clean_specific_info = plotman.plotters.chianetwork.SpecificInfo()


# @pytest.mark.parametrize(
#     argnames=["line"],
#     argvalues=[["Bucket"], [" Bucket"], ["\tBucket"]],
# )
# def test_ignore_line_matches(line):
def test_ignore_line_matches():
    assert (
        plotman.plotters.chianetwork.ignore_line(
            line="\tBucket",
            info=clean_specific_info,
        )
        is not None
    )


def test_ignore_line_does_not_match():
    assert (
        plotman.plotters.chianetwork.ignore_line(
            line="Blue Bucket",
            info=clean_specific_info,
        )
        is None
    )


def test_plot_id_extracts():
    plot_id = "3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24"
    info = plotman.plotters.chianetwork.plot_id(
        line=f"ID: {plot_id}",
        info=clean_specific_info,
    )

    assert info.plot_id == plot_id


def test_byte_by_byte_full_load():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="2021-04-04T19_00_47.681088-0400.log",
    )

    parser = plotman.plotters.chianetwork.Parser()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.chianetwork.SpecificInfo(
        plot_id="3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24",
    )