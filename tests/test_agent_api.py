from platform_agent.agent_api import AgentApi

import mock

SINGLE_CALL = 1


@mock.patch('platform_agent.agent_api.gather_initial_info')
def test_call(patch_gather_initial_info, gather_initial_info_payload, GET_INFO, request_id):
    agent_api = AgentApi(mock.MagicMock(), prod_mode=False)
    agent_api.call(GET_INFO, gather_initial_info_payload, request_id)
    assert patch_gather_initial_info.called
    assert patch_gather_initial_info.call_count == SINGLE_CALL
    assert patch_gather_initial_info.call_args[0] == ()


@mock.patch('platform_agent.agent_api.gather_initial_info')
def test_call_bad(patch_gather_initial_info, gather_initial_info_payload_bad, GET_INFO, request_id):
    agent_api = AgentApi(mock.MagicMock(), prod_mode=False)
    agent_api.call(GET_INFO, gather_initial_info_payload_bad, request_id)
    assert not patch_gather_initial_info.called
    assert patch_gather_initial_info.call_count == 0


@mock.patch('platform_agent.agent_api.gather_initial_info')
def test_call_error(patch_gather_initial_info, gather_initial_info_payload, GET_INFO, request_id):
    agent_api = AgentApi(mock.MagicMock(), prod_mode=False)
    patch_gather_initial_info.return_value = {'error': 'SOME_ERROR'}
    result = agent_api.call(GET_INFO, gather_initial_info_payload, request_id)
    assert result == {'error': 'SOME_ERROR'}
    assert patch_gather_initial_info.called
    assert patch_gather_initial_info.call_count == SINGLE_CALL
    assert patch_gather_initial_info.call_args[0] == ()


@mock.patch('platform_agent.agent_api.json.dumps')
@mock.patch('platform_agent.agent_api.update_tmp_file')
@mock.patch('platform_agent.agent_api.WgConf.clear_peers')
@mock.patch('platform_agent.agent_api.WgConf.clear_interfaces')
@mock.patch('platform_agent.agent_api.WgConf.create_interface')
def test_config_info(patch_create_interface, patch_clear_interfaces, patch_clear_peers, patch_update_tmp_file, patch_json_dumps, config_info_int_check, CONFIG_INFO, request_id):
    agent_api = AgentApi(mock.MagicMock(), prod_mode=False)
    agent_api.call(CONFIG_INFO, config_info_int_check, request_id)
    assert patch_clear_interfaces.called
    assert patch_clear_peers.called
    assert patch_create_interface.call_count == len(config_info_int_check['vpn'])
    assert patch_clear_interfaces.call_args[0][0] == config_info_int_check['vpn']


@mock.patch('platform_agent.agent_api.WireguardPeerWatcher')
def test_WG_INFO(patch_WireguardPeerWatcher, wg_info_payload, WG_INFO, request_id):
    agent_api = AgentApi(mock.MagicMock(), prod_mode=False)
    patch_WireguardPeerWatcher.return_value = mock.MagicMock()
    result = agent_api.call(WG_INFO, wg_info_payload, request_id)
    assert not result
    assert patch_WireguardPeerWatcher.called
    assert patch_WireguardPeerWatcher.call_count == SINGLE_CALL
