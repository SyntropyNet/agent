from platform_agent.files.tmp_files import get_peer_metadata

import mock


@mock.patch('platform_agent.files.tmp_files.read_tmp_file')
def test_config_info(patch_read_tmp_file, agent_dump, peer_file_read):
    patch_read_tmp_file.return_value = agent_dump
    peer_data = get_peer_metadata()
    assert peer_data == peer_file_read
