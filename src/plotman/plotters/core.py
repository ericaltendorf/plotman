import functools
import typing

import click
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
        if not isinstance(version, tuple):
            raise Exception(f'Version must be a tuple: {version!r}')

        return functools.partial(self._decorator, version=version)

    def _decorator(self, command: CommandProtocol, *, version: typing.Sequence[int]) -> None:
        self.by_version[version] = command
        # self.by_version = dict(sorted(self.by_version.items()))

    def __getitem__(self, item: typing.Sequence[int]) -> typing.Callable[[], None]:
        return self.by_version[item]

    def latest_command(self) -> CommandProtocol:
        return max(self.by_version.items())[1]
