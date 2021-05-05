import pyfakefs

from plotmanx import plot_util
from plotmanx.plot_util import GB


def test_human_format():
    assert (plot_util.human_format(3442000000, 0) == '3G')
    assert (plot_util.human_format(3542000, 2) == '3.54M')
    assert (plot_util.human_format(354, 0) == '354')
    assert (plot_util.human_format(354, 2) == '354.00')


def test_time_format():
    assert (plot_util.time_format(34) == '34s')
    assert (plot_util.time_format(59) == '59s')
    assert (plot_util.time_format(60) == '0:01')
    assert (plot_util.time_format(119) == '0:01')
    assert (plot_util.time_format(120) == '0:02')
    assert (plot_util.time_format(3694) == '1:01')


def test_split_path_prefix():
    assert (plot_util.split_path_prefix([]) ==
            ('', []))
    assert (plot_util.split_path_prefix(['/a/0', '/b/1', '/c/2']) ==
            ('', ['/a/0', '/b/1', '/c/2']))
    assert (plot_util.split_path_prefix(['/a/b/0', '/a/b/1', '/a/b/2']) ==
            ('/a/b', ['0', '1', '2']))


def test_columns():
    assert (plot_util.column_wrap(list(range(8)), 3, filler='--') ==
            [[0, 3, 6],
             [1, 4, 7],
             [2, 5, '--']])
    assert (plot_util.column_wrap(list(range(9)), 3, filler='--') ==
            [[0, 3, 6],
             [1, 4, 7],
             [2, 5, 8]])
    assert (plot_util.column_wrap(list(range(3)), 1, filler='--') ==
            [[0],
             [1],
             [2]])


def test_list_k32_plots(fs: pyfakefs.fake_filesystem.FakeFilesystem):
    fs.create_file('/t/plot-k32-0.plot', st_size=108 * GB)
    fs.create_file('/t/plot-k32-1.plot', st_size=108 * GB)
    fs.create_file('/t/.plot-k32-2.plot', st_size=108 * GB)
    fs.create_file('/t/plot-k32-3.plot.2.tmp', st_size=108 * GB)
    fs.create_file('/t/plot-k32-4.plot', st_size=100 * GB)
    fs.create_file('/t/plot-k32-5.plot', st_size=108 * GB)

    assert (plot_util.list_k32_plots('/t/') ==
            ['/t/plot-k32-0.plot',
             '/t/plot-k32-1.plot',
             '/t/plot-k32-5.plot'])
