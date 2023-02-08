import functools
import typing

import click
import typing_extensions


CommandOrGroup = typing.Union[click.Command, click.Group]
_T_CommandOrGroup = typing.TypeVar("_T_CommandOrGroup", bound=CommandOrGroup)


class Commands:
    def __init__(self) -> None:
        self.by_version: typing.Dict[typing.Sequence[int], CommandOrGroup] = {}

    def register(
        self, version: typing.Sequence[int]
    ) -> typing.Callable[[_T_CommandOrGroup], _T_CommandOrGroup]:
        if version in self.by_version:
            raise Exception(f"Version already registered: {version!r}")
        if not isinstance(version, tuple):
            raise Exception(f"Version must be a tuple: {version!r}")

        # TODO: would prefer the partial over def/closure but hinting prefers this way
        # return functools.partial(self._decorator, version=version)
        def decorator(x: _T_CommandOrGroup) -> _T_CommandOrGroup:
            return self._decorator(command=x, version=version)

        return decorator

    def _decorator(
        self, command: _T_CommandOrGroup, *, version: typing.Sequence[int]
    ) -> _T_CommandOrGroup:
        self.by_version[version] = command
        # self.by_version = dict(sorted(self.by_version.items()))
        return command

    def __getitem__(self, item: typing.Sequence[int]) -> CommandOrGroup:
        return self.by_version[item]

    def latest_command(self) -> CommandOrGroup:
        return max(self.by_version.items())[1]
