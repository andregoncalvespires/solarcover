"""Garante que traduções e ícones cobrem tudo o que o código expõe."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.solar_cover.binary_sensor import BINARY_SENSORS
from custom_components.solar_cover.config_flow import _geometry_schema, _sensors_schema
from custom_components.solar_cover.const import CONF_COVER
from custom_components.solar_cover.coordinator import ControlStatus
from custom_components.solar_cover.core.decision import Reason
from custom_components.solar_cover.number import NUMBERS
from custom_components.solar_cover.sensor import SENSORS

INTEGRATION = Path(__file__).parents[1] / "custom_components" / "solar_cover"
LANGUAGES = ["en", "pt-BR"]


def load(name: str) -> dict[str, Any]:
    return json.loads((INTEGRATION / name).read_text(encoding="utf-8"))


def flatten(data: dict[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= flatten(value, path)
        else:
            keys.add(path)
    return keys


def schema_keys(schema: Any) -> set[str]:
    return {marker.schema for marker in schema.schema}


def test_idiomas_tem_as_mesmas_chaves() -> None:
    en, pt = (flatten(load(f"translations/{lang}.json")) for lang in LANGUAGES)
    assert en == pt


@pytest.mark.parametrize("lang", LANGUAGES)
def test_todas_as_entidades_tem_nome(lang: str) -> None:
    entity = load(f"translations/{lang}.json")["entity"]
    expected = {
        "sensor": {d.key for d in SENSORS},
        "binary_sensor": {d.key for d in BINARY_SENSORS},
        "number": {d.key for d in NUMBERS},
        "switch": {"auto_control"},
        "button": {"resume"},
    }
    for platform, keys in expected.items():
        assert set(entity[platform]) == keys, platform
        assert all("name" in entity[platform][key] for key in keys), platform


@pytest.mark.parametrize("lang", LANGUAGES)
def test_estados_dos_sensores_enum(lang: str) -> None:
    sensors = load(f"translations/{lang}.json")["entity"]["sensor"]
    assert set(sensors["reason"]["state"]) == {reason.value for reason in Reason}
    assert set(sensors["status"]["state"]) == {status.value for status in ControlStatus}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_campos_do_fluxo_tem_rotulo(lang: str) -> None:
    translations = load(f"translations/{lang}.json")
    geometry = schema_keys(_geometry_schema({}, with_name=True))
    sensors = schema_keys(_sensors_schema({}))

    steps = translations["config"]["step"]
    assert set(steps["user"]["data"]) == {CONF_COVER}
    assert set(steps["geometry"]["data"]) == geometry
    assert set(steps["sensors"]["data"]) == sensors

    options = translations["options"]["step"]
    assert set(options["init"]["data"]) == geometry - {"name"}
    assert set(options["sensors"]["data"]) == sensors

    for errors in (translations["config"]["error"], translations["options"]["error"]):
        assert {"invalid_geometry", "invalid_horizon"} <= set(errors)
    assert {"already_configured", "already_in_progress", "no_covers"} <= set(
        translations["config"]["abort"]
    )


def test_icones_so_para_entidades_existentes() -> None:
    icons = load("icons.json")["entity"]
    entity = load("translations/en.json")["entity"]
    for platform, items in icons.items():
        assert set(items) <= set(entity[platform]), platform


def test_manifest() -> None:
    manifest = load("manifest.json")
    assert manifest["domain"] == "solar_cover"
    assert manifest["config_flow"] is True
    assert list(manifest)[:2] == ["domain", "name"]
    assert list(manifest)[2:] == sorted(list(manifest)[2:])  # hassfest exige ordem alfabética
