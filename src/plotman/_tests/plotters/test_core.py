import pytest

import plotman.plotters.core


def test_command_version_already_registered_raises():
    commands = plotman.plotters.core.Commands()
    version = (1, 2, 3)

    @commands.register(version=version)
    def f():
        pass

    with pytest.raises(Exception, match=r"Version already registered:"):
        @commands.register(version=version)
        def g():
            pass


def test_command_version_not_a_tuple_raises():
    commands = plotman.plotters.core.Commands()

    with pytest.raises(Exception, match=r"Version must be a tuple:"):
        commands.register(version="1.2.3")


def test_command_version_already_registered_raises():
    commands = plotman.plotters.core.Commands()
    version = (1, 2, 3)

    @commands.register(version=version)
    def f():
        pass

    assert commands[version] == f
