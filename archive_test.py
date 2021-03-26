#!/usr/bin/env python3

from unittest.mock import patch

import unittest
import archive
import manager

class TestArchive(unittest.TestCase):
    def test_compute_priority(self):
        self.assertGreater(
                archive.compute_priority( (3, 1), 1000, 10),
                archive.compute_priority( (3, 6), 1000, 10) )

    def test_rsync_dest(self):
        arch_dir = '/plotdir/012'
        arch_cfg = { 'rsyncd_module': 'plots_mod',
                     'rsyncd_path'  : '/plotdir',
                     'rsyncd_host'  : 'thehostname',
                     'rsyncd_user'  : 'theusername' }

        # Normal usage
        self.assertEqual('rsync://theusername@thehostname:12000/plots_mod/012',
                archive.rsync_dest(arch_cfg, arch_dir))

        # Usage for constructing just the prefix, for scanning process tables
        # for matching jobs.
        self.assertEqual('rsync://theusername@thehostname:12000/',
                archive.rsync_dest(arch_cfg, '/'))

if __name__ == '__main__':
    unittest.main()
