"""Fluxo de configuração: escolher a cortina, informar a geometria e as entradas."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_ALARM_ENTITY,
    CONF_COVER,
    CONF_FACADE_AZIMUTH,
    CONF_HORIZON,
    CONF_LUX_ENTITY,
    CONF_MAX_INCIDENCE,
    CONF_TEMPERATURE_ENTITY,
    DEFAULT_FACADE_AZIMUTH,
    DEFAULT_GEOMETRY,
    DEFAULT_MAX_INCIDENCE,
    DOMAIN,
    GEOMETRY_KEYS,
)
from .core.geometry import CurtainGeometry
from .core.horizon import HorizonProfile

_SENSOR_KEYS = (CONF_TEMPERATURE_ENTITY, CONF_LUX_ENTITY, CONF_ALARM_ENTITY)


def _number(minimum: float, maximum: float, step: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _geometry_schema(defaults: Mapping[str, Any], *, with_name: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, ""))] = (
            selector.TextSelector()
        )
    fields[
        vol.Required(
            CONF_FACADE_AZIMUTH, default=defaults.get(CONF_FACADE_AZIMUTH, DEFAULT_FACADE_AZIMUTH)
        )
    ] = _number(0, 360, 1, "°")
    fields[
        vol.Required(
            CONF_MAX_INCIDENCE, default=defaults.get(CONF_MAX_INCIDENCE, DEFAULT_MAX_INCIDENCE)
        )
    ] = _number(30, 90, 1, "°")
    for key in GEOMETRY_KEYS:
        fields[vol.Required(key, default=defaults.get(key, DEFAULT_GEOMETRY[key]))] = _number(
            0, 600, 0.5, "cm"
        )
    return vol.Schema(fields)


def _sensors_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    def suggested(key: str) -> dict[str, Any]:
        return {"suggested_value": defaults.get(key)}

    return vol.Schema(
        {
            vol.Optional(CONF_TEMPERATURE_ENTITY, description=suggested(CONF_TEMPERATURE_ENTITY)): (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            ),
            vol.Optional(CONF_LUX_ENTITY, description=suggested(CONF_LUX_ENTITY)): (
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
            ),
            vol.Optional(CONF_ALARM_ENTITY, description=suggested(CONF_ALARM_ENTITY)): (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "alarm_control_panel"])
                )
            ),
            vol.Optional(CONF_HORIZON, description=suggested(CONF_HORIZON)): (
                selector.TextSelector(selector.TextSelectorConfig(multiline=True))
            ),
        }
    )


def _validate_geometry(user_input: Mapping[str, Any]) -> dict[str, str]:
    geometry = CurtainGeometry(**{key: float(user_input[key]) for key in GEOMETRY_KEYS})
    try:
        geometry.validate()
    except ValueError:
        return {"base": "invalid_geometry"}
    return {}


def _validate_sensors(user_input: Mapping[str, Any]) -> dict[str, str]:
    try:
        HorizonProfile.parse(user_input.get(CONF_HORIZON))
    except ValueError:
        return {CONF_HORIZON: "invalid_horizon"}
    return {}


def _clean_sensors(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Remove campos vazios para que "sem sensor" signifique ausência da chave."""
    cleaned = {key: user_input[key] for key in _SENSOR_KEYS if user_input.get(key)}
    horizon = (user_input.get(CONF_HORIZON) or "").strip()
    if horizon:
        cleaned[CONF_HORIZON] = horizon
    return cleaned


def _free_covers(hass: HomeAssistant) -> list[str]:
    configured = {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)}
    return [
        state.entity_id
        for state in hass.states.async_all("cover")
        if state.entity_id not in configured
    ]


class SolarCoverConfigFlow(ConfigFlow, domain=DOMAIN):
    """Uma entrada de configuração por cortina."""

    VERSION = 1

    def __init__(self) -> None:
        self._cover: str = ""
        self._name: str = ""
        self._options: dict[str, Any] = {}

    # --- escolha da cortina (manual ou descoberta) -------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Escolhe a cortina entre as que ainda não têm controle solar."""
        free = _free_covers(self.hass)
        if not free:
            return self.async_abort(reason="no_covers")

        if user_input is not None:
            await self._select_cover(user_input[CONF_COVER])
            return await self.async_step_geometry()

        schema = vol.Schema(
            {
                vol.Required(CONF_COVER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="cover", include_entities=free)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Cortina sugerida pela autodescoberta."""
        await self._select_cover(discovery_info[CONF_COVER])
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirma a configuração de uma cortina descoberta."""
        if user_input is not None:
            return await self.async_step_geometry()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._name, "entity_id": self._cover},
        )

    async def _select_cover(self, entity_id: str) -> None:
        await self.async_set_unique_id(entity_id)
        self._abort_if_unique_id_configured()
        self._cover = entity_id
        state = self.hass.states.get(entity_id)
        self._name = state.name if state else entity_id

    # --- geometria e entradas ------------------------------------------------

    async def async_step_geometry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nome, orientação da fachada e cotas da instalação."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_geometry(user_input)
            if not errors:
                self._name = user_input[CONF_NAME]
                self._options = {k: v for k, v in user_input.items() if k != CONF_NAME}
                return await self.async_step_sensors()
        defaults = user_input or {CONF_NAME: self._name}
        return self.async_show_form(
            step_id="geometry",
            data_schema=_geometry_schema(defaults, with_name=True),
            errors=errors,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sensores opcionais e perfil de horizonte do prédio vizinho."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sensors(user_input)
            if not errors:
                return self.async_create_entry(
                    title=self._name,
                    data={CONF_COVER: self._cover},
                    options={**self._options, **_clean_sensors(user_input)},
                )
        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensors_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SolarCoverOptionsFlow:
        """Opções da cortina."""
        return SolarCoverOptionsFlow()


class SolarCoverOptionsFlow(OptionsFlow):
    """Reajusta geometria, entradas e horizonte de uma cortina."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Orientação da fachada e cotas."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_geometry(user_input)
            if not errors:
                self._options = dict(user_input)
                return await self.async_step_sensors()
        defaults = user_input or self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=_geometry_schema(defaults, with_name=False),
            errors=errors,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sensores opcionais e horizonte."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sensors(user_input)
            if not errors:
                return self.async_create_entry(data={**self._options, **_clean_sensors(user_input)})
        defaults = user_input or self.config_entry.options
        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensors_schema(defaults),
            errors=errors,
        )
