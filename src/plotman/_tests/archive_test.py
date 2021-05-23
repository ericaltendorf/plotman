from plotman import archive, job


def test_compute_priority():
    assert (archive.compute_priority( job.Phase(major=3, minor=1), 1000, 10) >
            archive.compute_priority( job.Phase(major=3, minor=6), 1000, 10) )


# @pytest.fixture(name='remote_configuration')
# def remote_configuration_fixture():
#     return configuration.Archive(
#         env={},
#         disk_space_script=textwrap.dedent("""\
#             #!/bin/bash
#             ssh altendky@server "df -BK | grep \\" ${site_root}/\\" | awk '{ gsub(/K\$/,\\"\\",\$4); print \$6 \":\" \$4*1024 }'"
#         """),
#         transfer_script=textwrap.dedent("""\
#             relative_path=$(realpath --relative-to="${site_root}" "${destination}")
#             "${command}" --bwlimit=80000 --skip-compress plot --remove-source-files --inplace "${source}" "${url_root}/${relative_path}"
#         """),
#         transfer_process_name='{command}',
#         transfer_process_argument_prefix='{url_root}',
#     )
