import archive
import manager


def test_compute_priority():
    assert (archive.compute_priority( (3, 1), 1000, 10) >
            archive.compute_priority( (3, 6), 1000, 10) )

def test_rsync_dest():
    arch_dir = '/plotdir/012'
    arch_cfg = { 'rsyncd_module': 'plots_mod',
                 'rsyncd_path'  : '/plotdir',
                 'rsyncd_host'  : 'thehostname',
                 'rsyncd_user'  : 'theusername' }

    # Normal usage
    assert ('rsync://theusername@thehostname:12000/plots_mod/012' ==
            archive.rsync_dest(arch_cfg, arch_dir))

    # Usage for constructing just the prefix, for scanning process tables
    # for matching jobs.
    assert ('rsync://theusername@thehostname:12000/' ==
            archive.rsync_dest(arch_cfg, '/'))
