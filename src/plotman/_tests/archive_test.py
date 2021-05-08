from plotman import archive, configuration, manager
import pytest


def test_compute_priority():
    assert (archive.compute_priority( (3, 1), 1000, 10) >
            archive.compute_priority( (3, 6), 1000, 10) )

def _archive_legacy():
    return configuration.Archive(
        rsyncd_module='plots_mod',
        rsyncd_path='/plotdir',
        rsyncd_host='thehostname',
        rsyncd_user='theusername',
        rsyncd_bwlimit=80000
    )

def test_rsync_dest():
    arch_dir = '/plotdir/012'
    arch_cfg = _archive_legacy()

    # Normal usage
    assert ('rsync://theusername@thehostname:12000/plots_mod/012' ==
            archive.rsync_dest(arch_cfg, arch_dir))

    # Usage for constructing just the prefix, for scanning process tables
    # for matching jobs.
    assert ('rsync://theusername@thehostname:12000/' ==
            archive.rsync_dest(arch_cfg, '/'))


def test_archive_legacy_default():
    arch_cfg = _archive_legacy()
    assert arch_cfg.mode == 'legacy'

def _archive_badmode():
    return configuration.Archive(
        rsyncd_module='plots_mod',
        rsyncd_path='/plotdir',
        rsyncd_host='thehostname',
        rsyncd_user='theusername',
        rsyncd_bwlimit=80000,
        mode='thismodedoesntexist'
    )

def test_archive_bad_mode():
    arch_cfg = _archive_badmode()
    assert arch_cfg.mode == 'thismodedoesntexist'


def test_archive_bad_mode_load():
    arch_cfg = _archive_badmode()
    with pytest.raises(AttributeError):
        getattr(arch_cfg, arch_cfg.mode)


def _archive_emptymode():
    return configuration.Archive(
        rsyncd_module='plots_mod',
        rsyncd_path='/plotdir',
        rsyncd_host='thehostname',
        rsyncd_user='theusername',
        rsyncd_bwlimit=80000,
        mode='local'
    )

def test_archive_local_mode_absent():
    arch_cfg = _archive_emptymode()
    arch_cfg_local = getattr(arch_cfg, arch_cfg.mode)
    assert not arch_cfg_local

def _archive_localmode():
    return configuration.Archive(
        rsyncd_module='plots_mod',
        rsyncd_path='/plotdir',
        rsyncd_host='thehostname',
        rsyncd_user='theusername',
        rsyncd_bwlimit=80000,
        mode='local',
        local=configuration.ArchiveLocal(
            path='/farm'
        )
    )

def test_archive_local_mode_load():
    arch_cfg = _archive_localmode()
    arch_cfg_local = getattr(arch_cfg, arch_cfg.mode)
    assert isinstance(arch_cfg_local, configuration.ArchiveLocal)
