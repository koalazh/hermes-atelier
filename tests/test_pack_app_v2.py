from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from plugin.atelier.app_pack import AppPack, release_pack
from plugin.atelier.pack_app import PackRuntime
from tests.test_app_pack_v2 import create_pack


class FakeHermes:
    def __init__(self, root: Path, *, fail_on: str | None = None) -> None:
        self.root = root
        self.fail_on = fail_on
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> None:
        self.calls.append(args)
        if self.fail_on and self.fail_on in args:
            raise RuntimeError("Hermes failed")
        if "install" in args:
            name = args[args.index("--name") + 1]
            source = Path(args[args.index("install") + 1])

            shutil.copytree(source, self.root / "profiles" / name, dirs_exist_ok=True)
            receipt = self.root / "profiles" / name / "distribution.yaml"
            value = yaml.safe_load(receipt.read_text(encoding="utf-8"))
            value["name"] = name
            value["distribution_owned"] = [
                str(item).rstrip("/") for item in value.get("distribution_owned") or []
            ]
            value["source"] = str(source)
            value["installed_at"] = f"install-{len(self.calls)}"
            receipt.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        if "delete" in args:
            name = args[args.index("delete") + 1]
            profile = self.root / "profiles" / name
            if profile.exists():
                shutil.rmtree(profile)
        if "config" in args and "set" in args:
            profile = self.root / "profiles" / args[1]
            path = profile / "config.yaml"
            value = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
            config = value if isinstance(value, dict) else {}
            index = args.index("set")
            keys = args[index + 1].split(".")
            target = config
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = args[index + 2]
            path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def released_pack(tmp_path: Path) -> Path:
    source = create_pack(tmp_path / "source")
    destination = tmp_path / "release"
    release_pack(AppPack.load(source), destination)
    return destination


def test_pack_install_and_configure_use_hermes_and_local_runtime_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    fake = FakeHermes(home)
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=fake)

    runtime.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    runtime.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )

    install_calls = [call for call in fake.calls if "install" in call]
    assert {call[call.index("--name") + 1] for call in install_calls} == {
        "customer-a--dispatcher",
        "customer-a--product",
    }
    mapping = json.loads(
        (home / "profiles" / "customer-a--dispatcher" / "local" / "app-runtime.json").read_text(
            encoding="utf-8"
        )
    )
    assert mapping["current_agent"] == "dispatcher"
    assert set(mapping["agents"]) == {"dispatcher", "product"}
    assert mapping["agents"]["dispatcher"]["base_url"] == "http://127.0.0.1:9123"
    assert mapping["agents"]["product"]["base_url"] == "http://127.0.0.1:9124"
    assert mapping["agents"]["dispatcher"]["api_key_env"] != mapping["agents"]["product"][
        "api_key_env"
    ]
    assert "gateway-secret-value" not in json.dumps(mapping)
    env = (home / "profiles" / "customer-a--dispatcher" / ".env").read_text()
    assert "MODEL_KEY=model-secret" in env
    assert "GATEWAY_KEY=gateway-secret-value" not in env
    assert "GATEWAY_KEY__DISPATCHER=gateway-secret-value" in env
    product_env = (home / "profiles" / "customer-a--product" / ".env").read_text()
    assert "GATEWAY_KEY__DISPATCHER=" not in product_env
    assert "GATEWAY_KEY__PRODUCT=" in product_env
    assert "API_SERVER_PORT=9123" in env
    assert any("providers.app_pack.api" in call for call in fake.calls)
    assert any("providers.app_pack.key_env" in call for call in fake.calls)
    assert not any("custom_providers" in call for call in fake.calls)
    assert not any("multiplex_profiles" in call for call in fake.calls)
    assert (home / "app-packs" / "customer-a" / "app.lock").is_file()

    runtime.configure(
        instance="customer-a",
        model="second-model",
        model_base_url="https://second.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9223,
    )
    state = json.loads(
        (home / "app-packs" / "customer-a" / "runtime.json").read_text(encoding="utf-8")
    )
    assert state["model"] == "second-model"
    assert state["entry_base_url"] == "http://127.0.0.1:9223"

    runtime.gateway("start", instance="customer-a")
    started = [call for call in fake.calls if "gateway" in call and "start" in call]
    assert {call[1] for call in started} == {
        "customer-a--dispatcher",
        "customer-a--product",
    }


def test_pack_install_failure_is_not_reported_as_success(tmp_path: Path) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    runtime = PackRuntime(
        pack,
        hermes_home=home,
        hermes_runner=FakeHermes(home, fail_on="customer-a--product"),
    )

    with pytest.raises(RuntimeError, match="Hermes failed"):
        runtime.install(instance="customer-a")

    assert not (home / "app-packs" / "customer-a" / "app.lock").exists()


def test_configure_assigns_base_port_to_entry_even_when_lock_is_sorted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml

    source = create_pack(tmp_path / "source")
    manifest_path = source / "app.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["entry"] = "product"
    manifest["agents"]["dispatcher"]["exposure"] = "internal"
    manifest["agents"]["product"]["exposure"] = "public"
    manifest["allowed_calls"] = {"product": ["dispatcher"]}
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    pack = tmp_path / "release"
    release_pack(AppPack.load(source), pack)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")

    runtime.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )

    state = json.loads(
        (home / "app-packs" / "customer-a" / "runtime.json").read_text(encoding="utf-8")
    )
    assert state["entry_base_url"] == "http://127.0.0.1:9123"
    assert state["agent_ports"] == {"product": 9123, "dispatcher": 9124}


def test_pack_update_removes_deleted_profile_and_preserves_consumer_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_pack = released_pack(tmp_path / "old")
    home = tmp_path / "hermes"
    fake = FakeHermes(home)
    old = PackRuntime(old_pack, hermes_home=home, hermes_runner=fake)
    old.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    old.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )
    dispatcher = home / "profiles" / "customer-a--dispatcher"
    with (dispatcher / ".env").open("a", encoding="utf-8") as output:
        output.write("CONSUMER_MARKER=keep\n")
    (dispatcher / "local" / "consumer.json").write_text("{}", encoding="utf-8")

    source = create_pack(tmp_path / "new-source")
    import yaml

    manifest_path = source / "app.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["agents"].pop("product")
    manifest["allowed_calls"] = {}
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    new_pack = tmp_path / "new-release"
    release_pack(AppPack.load(source), new_pack)

    PackRuntime(new_pack, hermes_home=home, hermes_runner=fake).update(
        instance="customer-a", restart=False
    )

    assert not (home / "profiles" / "customer-a--product").exists()
    assert "CONSUMER_MARKER=keep" in (dispatcher / ".env").read_text()
    assert (dispatcher / "local" / "consumer.json").is_file()
    assert any("delete" in call and "customer-a--product" in call for call in fake.calls)


def test_pack_update_smoke_failure_restores_old_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_pack = released_pack(tmp_path / "old")
    home = tmp_path / "hermes"
    fake = FakeHermes(home)
    old = PackRuntime(old_pack, hermes_home=home, hermes_runner=fake)
    old.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    old.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )

    source = create_pack(tmp_path / "new-source")
    import yaml

    manifest_path = source / "app.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["agents"].pop("product")
    manifest["allowed_calls"] = {}
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    new_pack = tmp_path / "new-release"
    release_pack(AppPack.load(source), new_pack)
    runtime = PackRuntime(new_pack, hermes_home=home, hermes_runner=fake)
    smokes = 0

    def smoke_once(*_: object, **__: object) -> None:
        nonlocal smokes
        smokes += 1
        if smokes == 1:
            raise RuntimeError("new smoke failed")

    monkeypatch.setattr(runtime, "_smoke", smoke_once)

    with pytest.raises(RuntimeError, match="previous distributions restored"):
        runtime.update(instance="customer-a")

    mapping = json.loads(
        (home / "profiles" / "customer-a--dispatcher" / "local" / "app-runtime.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(mapping["agents"]) == {"dispatcher", "product"}
    assert (home / "profiles" / "customer-a--product").is_dir()


def test_pack_case_runner_uses_unique_session_trace_assertions_and_restores_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml

    source = create_pack(tmp_path / "source")
    contracts = source / "contracts"
    contracts.mkdir()
    (contracts / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "known": {"type": "array", "items": {"type": "string"}},
                    "uncertain": {"type": "array", "items": {"type": "string"}},
                    "next_action": {"type": "string"},
                },
                "required": ["known", "uncertain", "next_action"],
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )
    manifest_path = source / "app.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["public_api"]["output_contract"] = "contracts/output.schema.json"
    manifest["contracts"] = ["contracts/output.schema.json"]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    case_path = source / "cases" / "smoke.yaml"
    case_path.write_text(
        yaml.safe_dump(
            {
                "id": "smoke",
                "input": "hello",
                "memory_policy": "clean",
                "assertions": {
                    "calls": {"required": ["product"]},
                    "output": {"must_contain": ["evidence"]},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pack = tmp_path / "release"
    release_pack(AppPack.load(source), pack)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    runtime.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )
    mapping_path = (
        home / "profiles" / "customer-a--dispatcher" / "local" / "app-runtime.json"
    )
    original_mapping = mapping_path.read_bytes()
    sessions: list[str] = []

    def entry_run(**kwargs: object) -> tuple[str, str, str]:
        session_id = str(kwargs["session_id"])
        sessions.append(session_id)
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        trace_path = (
            Path(mapping["trace"]["directory"])
            / f"{hashlib.sha256(session_id.encode()).hexdigest()}.jsonl"
        )
        trace_path.write_text(
            json.dumps(
                {
                    "event": "profile_call.completed",
                    "source_session_id": session_id,
                    "target": "product",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return (
            "run-entry",
            "completed",
            json.dumps(
                {
                    "known": ["product evidence"],
                    "uncertain": [],
                    "next_action": "continue",
                }
            ),
        )

    monkeypatch.setattr(runtime, "_entry_run", entry_run)

    first = runtime.run_cases(instance="customer-a", case_id="smoke")
    second = runtime.run_cases(instance="customer-a", case_id="smoke")

    assert first["passed"] is True
    assert second["passed"] is True
    assert sessions[0] != sessions[1]
    assert first["cases"][0]["traces"][0]["target"] == "product"
    assert first["cases"][0]["assertions"][-1]["kind"] == "contract.output"
    assert mapping_path.read_bytes() == original_mapping


def test_pack_attestation_binds_release_runtime_definition_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    runtime.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )

    attestation = runtime.attest(instance="customer-a")

    assert attestation["verified"] is True
    assert attestation["model_fingerprint"] == {
        "provider": "custom:app_pack",
        "model": "test-model",
        "base_url": "https://model.invalid/v1",
    }
    assert attestation["pack_revision"] == attestation["definition_snapshot"]["revision"]

    soul = home / "profiles" / "customer-a--dispatcher" / "SOUL.md"
    soul.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="installed Profile asset changed"):
        runtime.attest(instance="customer-a")


def test_configure_rejects_profile_tampered_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="customer-a")
    (home / "profiles" / "customer-a--dispatcher" / "SOUL.md").write_text(
        "tampered before configure\n", encoding="utf-8"
    )
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")

    with pytest.raises(RuntimeError, match="does not match app.lock"):
        runtime.configure(
            instance="customer-a",
            model="test-model",
            model_base_url="https://model.invalid/v1",
            model_key_env="MODEL_KEY",
            gateway_key_env="GATEWAY_KEY",
            gateway_port=9123,
        )


def test_attestation_cannot_rebaseline_tampered_release_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    runtime.install(instance="customer-a")
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")
    runtime.configure(
        instance="customer-a",
        model="test-model",
        model_base_url="https://model.invalid/v1",
        model_key_env="MODEL_KEY",
        gateway_key_env="GATEWAY_KEY",
        gateway_port=9123,
    )
    soul = home / "profiles" / "customer-a--dispatcher" / "SOUL.md"
    soul.write_text("tampered and rebaselined\n", encoding="utf-8")
    import hashlib

    state_path = home / "app-packs" / "customer-a" / "runtime.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["runtime_definition"]["dispatcher"]["SOUL.md"] = hashlib.sha256(
        soul.read_bytes()
    ).hexdigest()
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not match app.lock"):
        runtime.attest(instance="customer-a")


@pytest.mark.parametrize(
    "operation",
    [
        lambda runtime: runtime.configure(
            instance="../../escape",
            model="test-model",
            model_base_url="https://model.invalid/v1",
            model_key_env="MODEL_KEY",
            gateway_key_env="GATEWAY_KEY",
            gateway_port=9123,
        ),
        lambda runtime: runtime.run_cases(instance="../../escape"),
        lambda runtime: runtime.attest(instance="../../escape"),
        lambda runtime: runtime.update(instance="../../escape", restart=False),
        lambda runtime: runtime.gateway("start", instance="../../escape"),
    ],
)
def test_all_pack_operations_reject_escaping_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: object,
) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=FakeHermes(home))
    monkeypatch.setenv("MODEL_KEY", "model-secret")
    monkeypatch.setenv("GATEWAY_KEY", "gateway-secret-value")

    with pytest.raises(ValueError, match="instance"):
        operation(runtime)  # type: ignore[operator]

    assert not (tmp_path / "escape").exists()


def test_pack_install_rejects_symlinked_instance_state(tmp_path: Path) -> None:
    pack = released_pack(tmp_path)
    home = tmp_path / "hermes"
    outside = tmp_path / "outside"
    outside.mkdir()
    state_root = home / "app-packs"
    state_root.mkdir(parents=True)
    (state_root / "customer-a").symlink_to(outside, target_is_directory=True)
    fake = FakeHermes(home)
    runtime = PackRuntime(pack, hermes_home=home, hermes_runner=fake)

    with pytest.raises(ValueError, match="instance state"):
        runtime.install(instance="customer-a")

    assert fake.calls == []
    assert not (outside / "app.lock").exists()
    assert not (outside / "install.json").exists()


def test_case_instructions_include_declared_initial_state(tmp_path: Path) -> None:
    runtime = PackRuntime(
        released_pack(tmp_path),
        hermes_home=tmp_path / "hermes",
        hermes_runner=FakeHermes(tmp_path / "hermes"),
    )

    instructions = runtime._case_instructions(
        {"manifest": {"public_api": {"output_contract": None}}},
        {
            "memory_policy": "clean",
            "initial_state": {"ticket": "T-100", "attempt": 2},
        },
    )

    assert '"ticket": "T-100"' in instructions
    assert '"attempt": 2' in instructions
