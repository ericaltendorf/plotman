import click
import pytest

import plotman.plotters.core


def test_command_version_already_registered_raises() -> None:
    commands = plotman.plotters.core.Commands()
    version = (1, 2, 3)

    @commands.register(version=version)
    @click.command
    def f() -> None:
        pass

    with pytest.raises(Exception, match=r"Version already registered:"):

        @commands.register(version=version)
        @click.command
        def g() -> None:
            pass


def test_command_version_not_a_tuple_raises() -> None:
    commands = plotman.plotters.core.Commands()

    with pytest.raises(Exception, match=r"Version must be a tuple:"):
        commands.register(version="1.2.3")  # type: ignore[arg-type]


def test_command_getitem_works() -> None:
    commands = plotman.plotters.core.Commands()
    version = (1, 2, 3)

    @commands.register(version=version)
    @click.command
    def f() -> None:
        pass

    assert commands[version] == f
