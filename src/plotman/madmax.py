# mypy: allow_untyped_decorators
#
# Madmax is written in C++.  Below is a mapping of its CLI options to Python.
# See: https://github.com/madMAx43v3r/chia-plotter/tree/master/src
# Note: versions are git commit refs, not semantic versioning
# 

import functools
import typing

import click
from pathlib import Path
import typing_extensions


class CommandProtocol(typing_extensions.Protocol):
    def make_context(self, info_name: str, args: typing.List[str]) -> click.Context:
        ...

    def __call__(self) -> None:
        ...


class Commands:
    def __init__(self) -> None:
        self.by_version: typing.Dict[typing.Sequence[int], CommandProtocol] = {}

    def register(self, version: typing.Sequence[int]) -> typing.Callable[[CommandProtocol], None]:
        if version in self.by_version:
            raise Exception(f'Version already registered: {version!r}')

        return functools.partial(self._decorator, version=version)

    def _decorator(self, command: CommandProtocol, *, version: typing.Sequence[int]) -> None:
        self.by_version[version] = command

    def __getitem__(self, item: typing.Sequence[int]) -> typing.Callable[[], None]:
        return self.by_version[item]

    def latest_command(self) -> CommandProtocol:
        return max(self.by_version.items())[1]


commands = Commands()
# Madmax Git on 2021-06-19 -> https://github.com/madMAx43v3r/chia-plotter/commit/c8121b987186c42c895b49818e6c13acecc51332
# TODO: make Commands able to handle this.  maybe configure with a list defining order?
#       for now we can just access directly.
# @commands.register(version=("c8121b9"))
@click.command()
# https://github.com/madMAx43v3r/chia-plotter/blob/master/LICENSE
# https://github.com/madMAx43v3r/chia-plotter/blob/master/src/chia_plot.cpp#L180
@click.option("-n", "--count", help="Number of plots to create (default = 1, -1 = infinite)", 
    type=int, default=1, show_default=True)
@click.option("-r", "--threads", help="Number of threads (default = 4)", 
    type=int, default=4, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets (default = 256)", 
    type=int, default=256, show_default=True)
@click.option("-v", "--buckets3", help="Number of buckets for phase 3+4 (default = buckets)", 
    type=int, default=256)
@click.option("-t", "--tmpdir", help="Temporary directory, needs ~220 GiB (default = $PWD)",
    type=click.Path(), default=Path("."), show_default=True)
@click.option("-2", "--tmpdir2", help="Temporary directory 2, needs ~110 GiB [RAM] (default = <tmpdir>)", 
    type=click.Path(), default=None)
@click.option("-d", "--finaldir", help="Final directory (default = <tmpdir>)",
    type=click.Path(), default=Path("."), show_default=True)
@click.option("-p", "--poolkey", help="Pool Public Key (48 bytes)", 
    type=str, default=None)
@click.option("-f", "--farmerkey", help="Farmer Public Key (48 bytes)", 
    type=str, default=None)
@click.option("-c", "--contract", help="Pool Contract Address (64 chars)",
    type=str, default=None)
@click.option("-G", "--tmptoggle", help="Alternate tmpdir/tmpdir2", 
    type=str, default=None)
def _cli_c8121b9() -> None:
    pass
