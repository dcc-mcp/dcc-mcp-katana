import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from dcc_mcp_katana import __version__, cli, install_environment, install_lifecycle, plugin

_STALE_ADAPTER_VERSION = "0.3.0"


def test_install_dry_run_preserves_existing_katana_resources(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    existing = [tmp_path / "studio-resources", tmp_path / "show-resources"]
    original_value = os.pathsep.join(str(path) for path in existing)
    monkeypatch.setenv("KATANA_RESOURCES", original_value)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    code = cli.main(
        [
            "install",
            "--dry-run",
            "--json",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ]
    )

    report = json.loads(capsys.readouterr().out)
    environment = next(step for step in report["steps"] if step["id"] == "persist-katana-resources")
    assert code == 0
    assert report["schema_version"] == 1
    assert report["dcc_type"] == "katana"
    assert report["verb"] == "install"
    assert report["status"] == "planned"
    assert environment["status"] == "planned"
    assert environment["before"] == [str(path.resolve()) for path in existing]
    assert environment["after"] == [
        *(str(path.resolve()) for path in existing),
        str(cli.resource_path().resolve()),
    ]
    assert environment["owner"] == "adapter-launcher"
    assert os.environ["KATANA_RESOURCES"] == original_value


def test_preflight_rejects_target_adapter_version_mismatch(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": _STALE_ADAPTER_VERSION,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    code = cli.main(
        [
            "install",
            "--dry-run",
            "--json",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert code == 10
    assert report["failure"]["stage"] == "adapter"
    assert _STALE_ADAPTER_VERSION in report["failure"]["reason"]
    assert install_environment.receipt_path().exists() is False


def test_install_writes_owned_launcher_and_receipt_idempotently(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    existing = tmp_path / "studio-resources"
    original_value = str(existing)
    monkeypatch.setenv("KATANA_RESOURCES", original_value)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    arguments = [
        "install",
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]

    assert cli.main(arguments) == 0
    first_report = json.loads(capsys.readouterr().out)
    assert cli.main(arguments) == 0
    second_report = json.loads(capsys.readouterr().out)

    launcher = Path(first_report["launcher_path"])
    receipt = Path(first_report["receipt_path"])
    launcher_text = launcher.read_text(encoding="utf-8")
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert first_report["status"] == "ok"
    assert second_report["status"] == "ok"
    assert launcher.is_file()
    assert str(host.resolve()) in launcher_text
    assert str(cli.resource_path().resolve()) in launcher_text
    assert "KATANA_RESOURCES" in launcher_text
    assert receipt_payload["environment"]["owner"] == "adapter-launcher"
    assert receipt_payload["environment"]["launcher_path"] == str(launcher)
    assert receipt_payload["dcc_path"] == str(host.resolve())
    assert receipt_payload["python"] == str(Path(sys.executable).resolve())
    assert receipt_payload["files"][0]["sha256"]
    assert os.environ["KATANA_RESOURCES"] == original_value
    next_command = first_report["next_steps"][0]["command"]
    if os.name == "nt":
        assert next_command == [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(launcher),
        ]
        assert "setx" not in launcher_text.lower()
        assert "reg " not in launcher_text.lower()
    else:
        assert next_command == [str(launcher)]
        assert launcher.stat().st_mode & 0o100
        assert ".profile" not in launcher_text


def test_status_uses_receipt_without_launching_katana(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert (
        cli.main(
            [
                "install",
                "--yes",
                "--json",
                "--dcc-path",
                str(host),
                "--python",
                sys.executable,
            ]
        )
        == 0
    )
    capsys.readouterr()
    monkeypatch.delenv("KATANA_RESOURCES", raising=False)

    def unexpected_run(*_args, **_kwargs):
        raise AssertionError("status must not launch a host or interpreter")

    monkeypatch.setattr(subprocess, "run", unexpected_run)
    assert cli.main(["status", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ok"
    assert report["installation_state"] == "current"
    assert report["checks"]["receipt_valid"] is True
    assert report["checks"]["launcher_hash_matches"] is True


def test_uninstall_consumes_receipt_without_host_preflight(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert (
        cli.main(
            [
                "install",
                "--yes",
                "--json",
                "--dcc-path",
                str(host),
                "--python",
                sys.executable,
            ]
        )
        == 0
    )
    installed = json.loads(capsys.readouterr().out)
    launcher = Path(installed["launcher_path"])
    receipt = Path(installed["receipt_path"])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("uninstall must be receipt driven")
        ),
    )

    assert cli.main(["uninstall", "--yes", "--json"]) == 0
    first_report = json.loads(capsys.readouterr().out)
    assert cli.main(["uninstall", "--yes", "--json"]) == 0
    second_report = json.loads(capsys.readouterr().out)

    assert first_report["status"] == "ok"
    assert first_report["installation_state"] == "fresh"
    assert second_report["status"] == "ok"
    assert launcher.exists() is False
    assert receipt.exists() is False


def test_upgrade_refreshes_stale_version_stamp(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    arguments = [
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]
    assert cli.main(["install", *arguments]) == 0
    installed = json.loads(capsys.readouterr().out)
    receipt = Path(installed["receipt_path"])
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    receipt_payload["adapter_version"] = _STALE_ADAPTER_VERSION
    receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")

    assert cli.main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["installation_state"] == "upgrade"
    assert cli.main(["upgrade", "--dry-run", *arguments]) == 0
    assert json.loads(capsys.readouterr().out)["installation_state"] == "upgrade"
    assert cli.main(["upgrade", *arguments]) == 0

    report = json.loads(capsys.readouterr().out)
    refreshed = json.loads(receipt.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["verb"] == "upgrade"
    assert refreshed["adapter_version"] == __version__


def test_verify_reaches_target_import_and_typed_readiness(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        if Path(command[0]) == host:
            payload = "Katana 8.0v1\n"
        elif "import dcc_mcp_katana" in command[-1]:
            payload = json.dumps({"success": True, "version": __version__})
        else:
            payload = json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    arguments = [
        "--yes",
        "--json",
        "--dcc-path",
        str(host),
        "--python",
        sys.executable,
    ]
    assert cli.main(["install", *arguments]) == 0
    capsys.readouterr()
    readiness_calls = []

    def ready(**kwargs):
        readiness_calls.append(kwargs)
        return {"success": True, "status": "ready", "ready": True}

    monkeypatch.setattr(install_lifecycle, "wait_for_sidecar_ready", ready)

    assert cli.main(["verify", "--json", "--timeout", "0.25"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["verify"]["directly_usable"] is True
    assert report["verify"]["artifact"]["success"] is True
    assert report["verify"]["import"]["success"] is True
    assert report["verify"]["readiness"]["success"] is True
    assert readiness_calls == [
        {
            "dcc_type": "katana",
            "timeout_secs": 0.25,
            "probe_tool": "katana_nodegraph__get_status",
        }
    ]


def test_katana_startup_captures_bootstrap_errors(tmp_path, monkeypatch):
    error_log = tmp_path / "katana-bootstrap-errors.jsonl"
    monkeypatch.setenv("DCC_MCP_KATANA_BOOTSTRAP_ERROR_LOG", str(error_log))

    def broken_initialize():
        raise RuntimeError("dispatcher did not initialize")

    monkeypatch.setattr(plugin, "initialize", broken_initialize)
    entry = cli.resource_path() / "Plugins" / "dcc_mcp_katana.py"

    with pytest.raises(RuntimeError, match="dispatcher did not initialize"):
        runpy.run_path(str(entry), run_name="__katana_plugin_test__")

    record = json.loads(error_log.read_text(encoding="utf-8").splitlines()[-1])
    report = cli.doctor_report()
    assert record["stage"] == "initialize"
    assert record["exception_type"] == "RuntimeError"
    assert record["reason"] == "dispatcher did not initialize"
    assert report["checks"]["bootstrap_error_free"] is False
    assert report["bootstrap_errors"]["last"]["reason"] == "dispatcher did not initialize"


def test_lifecycle_json_uses_core_install_sop_v1_required_surface(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert (
        cli.main(
            [
                "install",
                "--dry-run",
                "--json",
                "--dcc-path",
                str(host),
                "--python",
                sys.executable,
            ]
        )
        == 0
    )
    reports = [json.loads(capsys.readouterr().out)]
    assert cli.main(["status", "--json"]) == 0
    reports.append(json.loads(capsys.readouterr().out))
    assert cli.main(["uninstall", "--dry-run", "--json"]) == 0
    reports.append(json.loads(capsys.readouterr().out))

    required = {
        "schema_version",
        "status",
        "dcc_type",
        "adapter_version",
        "core_version",
        "steps",
        "next_steps",
        "receipt_path",
        "verify",
    }
    for report in reports:
        assert required <= report.keys()
        assert report["schema_version"] == 1
        assert isinstance(report["schema_version"], int)
        assert report["status"] in {
            "planned",
            "running",
            "ok",
            "failed",
            "partial",
            "requires_restart",
        }
        assert {
            "directly_usable",
            "failure_stage",
            "failure_reason",
        } <= report["verify"].keys()


def test_locked_launcher_returns_requires_restart_contract(tmp_path, monkeypatch, capsys):
    host = tmp_path / "katanaBin.exe"
    host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) == host
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        install_environment,
        "_atomic_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PermissionError("launcher is held by Katana")
        ),
    )

    code = cli.main(
        [
            "install",
            "--yes",
            "--json",
            "--dcc-path",
            str(host),
            "--python",
            sys.executable,
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert code == 50
    assert report["status"] == "requires_restart"
    assert report["failure"]["stage"] == "launcher_locked"
    assert report["next_steps"][0]["command"][0:3] == [
        "dcc-mcp-katana",
        "install",
        "--yes",
    ]


def test_failed_upgrade_restores_previous_launcher_and_receipt(tmp_path, monkeypatch, capsys):
    first_host = tmp_path / "Katana8" / "katanaBin.exe"
    second_host = tmp_path / "Katana9" / "katanaBin.exe"
    first_host.parent.mkdir()
    second_host.parent.mkdir()
    first_host.write_bytes(b"")
    second_host.write_bytes(b"")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def fake_run(command, **_kwargs):
        payload = (
            "Katana 8.0v1\n"
            if Path(command[0]) in {first_host, second_host}
            else json.dumps(
                {
                    "python_version": "3.12.10",
                    "dcc-mcp-core": "0.20.8",
                    "dcc-mcp-katana": __version__,
                }
            )
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    common = ["--yes", "--json", "--python", sys.executable]
    assert cli.main(["install", *common, "--dcc-path", str(first_host)]) == 0
    installed = json.loads(capsys.readouterr().out)
    launcher = Path(installed["launcher_path"])
    receipt = Path(installed["receipt_path"])
    previous_launcher = launcher.read_bytes()
    previous_receipt = receipt.read_bytes()
    atomic_write = install_environment._atomic_write

    def fail_receipt(path, payload, mode=0o600):
        if Path(path) == receipt:
            raise OSError("simulated receipt failure")
        return atomic_write(path, payload, mode)

    monkeypatch.setattr(install_environment, "_atomic_write", fail_receipt)

    assert cli.main(["upgrade", *common, "--dcc-path", str(second_host)]) == 30
    failure = json.loads(capsys.readouterr().out)
    assert failure["failure"]["stage"] == "install"
    assert launcher.read_bytes() == previous_launcher
    assert receipt.read_bytes() == previous_receipt
    assert cli.main(["status", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["installation_state"] == "current"
