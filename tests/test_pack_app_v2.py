from __future__ import annotations

import json
from pathlib import Path

import pytest

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
            (self.root / "profiles" / name).mkdir(parents=True, exist_ok=True)
        if "delete" in args:
            name = args[args.index("delete") + 1]
            profile = self.root / "profiles" / name
            if profile.exists():
                import shutil

                shutil.rmtree(profile)


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
    assert mapping["agents"]["dispatcher"]["base_url"] == "http://127.0.0.1:9123"
    assert mapping["agents"]["product"]["base_url"] == "http://127.0.0.1:9124"
    assert "gateway-secret-value" not in json.dumps(mapping)
    env = (home / "profiles" / "customer-a--dispatcher" / ".env").read_text()
    assert "MODEL_KEY=model-secret" in env
    assert "GATEWAY_KEY=gateway-secret-value" in env
    assert "API_SERVER_PORT=9123" in env
    assert any("providers.app_pack.api" in call for call in fake.calls)
    assert any("providers.app_pack.key_env" in call for call in fake.calls)
    assert not any("custom_providers" in call for call in fake.calls)
    assert not any("multiplex_profiles" in call for call in fake.calls)
    assert (home / "app-packs" / "customer-a" / "app.lock").is_file()

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
