from plotman import archive, job


def test_compute_priority():
    assert (archive.compute_priority( job.Phase(major=3, minor=1), 1000, 10) >
            archive.compute_priority( job.Phase(major=3, minor=6), 1000, 10) )
