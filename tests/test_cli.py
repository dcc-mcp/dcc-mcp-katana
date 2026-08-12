import json
import os

from dcc_mcp_katana import cli


def test_resource_path_contains_katana_plugin():
    assert (cli.resource_path() / "Plugins" / "dcc_mcp_katana.py").is_file()


def test_doctor_reports_active_resource(monkeypatch, capsys):
    monkeypatch.setenv("KATANA_RESOURCES", str(cli.resource_path()))
    assert cli.main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is True


def test_doctor_fails_when_resource_is_not_configured(monkeypatch):
    monkeypatch.delenv("KATANA_RESOURCES", raising=False)
    assert cli.main(["doctor", "--json"]) == 1


def test_doctor_handles_multiple_resource_paths(monkeypatch):
    value = os.pathsep.join([str(cli.resource_path().parent), str(cli.resource_path())])
    monkeypatch.setenv("KATANA_RESOURCES", value)
    assert cli.doctor_report()["checks"]["resource_path_active"] is True
