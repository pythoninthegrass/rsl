import pytest
from rsl.main import ResilioAPI, cmd_set_setting
from unittest.mock import MagicMock, patch


class TestSetSetting:
    """Tests for ResilioAPI.set_setting() method."""

    def test_calls_setsettings_endpoint(self):
        api = MagicMock(spec=ResilioAPI)
        api.api.return_value = {"status": 200, "value": {}}

        ResilioAPI.set_setting(api, "worker_threads_count", "1")

        api.api.assert_called_once_with("action=setsettings&worker_threads_count=1")

    def test_url_encodes_value(self):
        api = MagicMock(spec=ResilioAPI)
        api.api.return_value = {"status": 200, "value": {}}

        ResilioAPI.set_setting(api, "some_key", "hello world")

        api.api.assert_called_once_with("action=setsettings&some_key=hello%20world")


class TestCmdSetSetting:
    """Tests for cmd_set_setting() command function."""

    def test_success(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"
        api.set_setting.return_value = {"status": 200, "value": {}}

        result = cmd_set_setting(api, ["worker_threads_count", "1"])

        api.set_setting.assert_called_once_with("worker_threads_count", "1")
        assert result == 0
        out = capsys.readouterr().out
        assert "worker_threads_count=1" in out
        assert "OK" in out

    def test_normalizes_boolean_true(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"
        api.set_setting.return_value = {"status": 200, "value": {}}

        cmd_set_setting(api, ["disk_low_priority", "true"])

        api.set_setting.assert_called_once_with("disk_low_priority", "1")

    def test_normalizes_boolean_false(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"
        api.set_setting.return_value = {"status": 200, "value": {}}

        cmd_set_setting(api, ["disk_low_priority", "false"])

        api.set_setting.assert_called_once_with("disk_low_priority", "0")

    def test_error_response(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"
        api.set_setting.return_value = {
            "status": 200,
            "value": {"error": 1, "message": "invalid key"},
        }

        result = cmd_set_setting(api, ["bad_key", "1"])

        assert result == 1
        out = capsys.readouterr().out
        assert "Failed" in out

    def test_wrong_arg_count(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"

        result = cmd_set_setting(api, ["only_one_arg"])

        assert result == 1
        out = capsys.readouterr().out
        assert "Usage" in out

    def test_too_many_args(self, capsys):
        api = MagicMock(spec=ResilioAPI)
        api.name = "src"

        result = cmd_set_setting(api, ["a", "b", "c"])

        assert result == 1
        out = capsys.readouterr().out
        assert "Usage" in out
