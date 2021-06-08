import functools

import click
from pathlib import Path


class Commands:
    def __init__(self):
        self.by_version = {}

    def register(self, version):
        if version in self.by_version:
            raise Exception(f'Version already registered: {version!r}')
        if not isinstance(version, tuple):
            raise Exception(f'Version must be a tuple: {version!r}')

        return functools.partial(self._decorator, version=version)

    def _decorator(self, command, *, version):
        self.by_version[version] = command
        # self.by_version = dict(sorted(self.by_version.items()))

    def __getitem__(self, item):
        return self.by_version[item]

    def latest_command(self):
        return max(self.by_version.items())[1]


commands = Commands()


@commands.register(version=(1, 1, 2))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.2/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.2/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=4608, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass


@commands.register(version=(1, 1, 3))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.3/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.3/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=4608, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass


@commands.register(version=(1, 1, 4))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.4/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.4/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=3389, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass


@commands.register(version=(1, 1, 5))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.5/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.5/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=3389, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass


@commands.register(version=(1, 1, 6))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.6/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.6/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=3389, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass


@commands.register(version=(1, 1, 7))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.7/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.7/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option("--override-k", help="Force size smaller than 32", default=False, show_default=True, is_flag=True)
@click.option("-n", "--num", help="Number of plots or challenges", type=int, default=1, show_default=True)
@click.option("-b", "--buffer", help="Megabytes for sort/plot buffer", type=int, default=3389, show_default=True)
@click.option("-r", "--num_threads", help="Number of threads to use", type=int, default=2, show_default=True)
@click.option("-u", "--buckets", help="Number of buckets", type=int, default=128, show_default=True)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option("-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None)
@click.option("-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-2", "--tmp2_dir", help="Second temporary directory for plotting files", type=click.Path(), default=None)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=Path("."),
    show_default=True,
)
@click.option("-i", "--plotid", help="PlotID in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-m", "--memo", help="Memo in hex for reproducing plots (debugging only)", type=str, default=None)
@click.option("-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True)
@click.option(
    "-x", "--exclude_final_dir", help="Skips adding [final dir] to harvester for farming", default=False, is_flag=True
)
# end copied code
def _cli():
    pass
