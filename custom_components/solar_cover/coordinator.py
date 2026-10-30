"""Coordenador: lê as entradas, decide a posição e aciona o motor com cautela."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_SET_COVER_POSITION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    COMMAND_GRACE,
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
    MOVING_STATES,
    STORAGE_SAVE_DELAY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .core.decision import AlarmState, Decision, DecisionInput, decide
from .core.geometry import CurtainGeometry, lit_door_height
from .core.horizon import HorizonProfile
from .core.lux import LuxFilter
from .core.motion import MoveStatus, plan_move
from .core.sun import solar_position
from .runtime import Settings

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

_ARMED_STATES = frozenset(
    {
        "on",
        "arming",
        "pending",
        "triggered",
        "armed_home",
        "armed_away",
        "armed_night",
        "armed_vacation",
        "armed_custom_bypass",
    }
)
_DISARMED_STATES = frozenset({"off", "disarmed"})


class ControlStatus(StrEnum):
    """O que a integração está fazendo com a cortina."""

    IDLE = "idle"
    MOVING = "moving"
    WAITING = "waiting"
    PAUSED = "paused"
    DISABLED = "disabled"
    HOLD = "hold"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SolarCoverData:
    """Resultado de um ciclo de cálculo."""

    now: datetime
    sun_azimuth: float
    sun_elevation: float
    decision: Decision
    current_position: float | None
    door_lit_cm: float
    status: ControlStatus
    lux_ok: bool | None
    manual_until: datetime | None


def alarm_state_from(state: str | None) -> AlarmState:
    """Reduz o estado de um binary_sensor/alarm_control_panel a armado/desarmado."""
    if state in _DISARMED_STATES:
        return AlarmState.DISARMED
    if state in _ARMED_STATES:
        return AlarmState.ARMED
    return AlarmState.UNKNOWN


class SolarCoverCoordinator(DataUpdateCoordinator[SolarCoverData]):
    """Uma cortina = um coordenador."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        options = entry.options
        self.cover_entity_id: str = entry.data[CONF_COVER]
        self.temperature_entity: str | None = options.get(CONF_TEMPERATURE_ENTITY)
        self.lux_entity: str | None = options.get(CONF_LUX_ENTITY)
        self.alarm_entity: str | None = options.get(CONF_ALARM_ENTITY)
        self.facade_azimuth = float(options.get(CONF_FACADE_AZIMUTH, DEFAULT_FACADE_AZIMUTH))
        self.max_incidence = float(options.get(CONF_MAX_INCIDENCE, DEFAULT_MAX_INCIDENCE))
        self.geometry = CurtainGeometry(
            **{key: float(options.get(key, DEFAULT_GEOMETRY[key])) for key in GEOMETRY_KEYS}
        )
        try:
            self.horizon = HorizonProfile.parse(options.get(CONF_HORIZON))
        except ValueError:
            _LOGGER.warning("Perfil de horizonte inválido em %s; ignorando", entry.title)
            self.horizon = HorizonProfile()

        self.settings = Settings()
        self.lux_filter = LuxFilter()
        self.manual_until: datetime | None = None
        self._last_command: datetime | None = None
        self._last_target: int | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.device_info = self._build_device_info()

    # ------------------------------------------------------------------ setup

    def _build_device_info(self) -> DeviceInfo:
        info = DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.title,
            manufacturer="Solar Cover",
            model="Controle solar de cortina",
        )
        entity = er.async_get(self.hass).async_get(self.cover_entity_id)
        if entity is not None and entity.device_id is not None:
            device = dr.async_get(self.hass).async_get(entity.device_id)
            if device is not None and device.identifiers:
                info["via_device"] = next(iter(device.identifiers))
        return info

    async def async_setup(self) -> None:
        """Carrega o estado salvo e passa a escutar as entidades de entrada."""
        stored = await self._store.async_load() or {}
        self.settings = Settings.from_dict(stored.get("settings"))
        self.lux_filter.state = bool(stored.get("lux_state", False))
        self.manual_until = dt_util.parse_datetime(stored.get("manual_until") or "")

        tracked = [
            entity_id
            for entity_id in (
                self.cover_entity_id,
                self.temperature_entity,
                self.lux_entity,
                self.alarm_entity,
            )
            if entity_id
        ]
        self.config_entry.async_on_unload(
            async_track_state_change_event(self.hass, tracked, self._handle_state_event)
        )

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "lux_state": self.lux_filter.state,
            "manual_until": self.manual_until.isoformat() if self.manual_until else None,
        }

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data_to_save, STORAGE_SAVE_DELAY)

    async def async_save(self) -> None:
        """Grava o estado imediatamente (usado ao descarregar a entrada)."""
        await self._store.async_save(self._data_to_save())

    # --------------------------------------------------------------- user API

    async def async_update_setting(self, key: str, value: float | bool) -> None:
        """Altera um ajuste e recalcula."""
        setattr(self.settings, key, value)
        if key == "enabled" and value:
            self.manual_until = None
        self._schedule_save()
        await self.async_refresh()

    async def async_resume(self) -> None:
        """Encerra a pausa por ajuste manual."""
        self.manual_until = None
        self._schedule_save()
        await self.async_refresh()

    # ---------------------------------------------------------------- events

    @callback
    def _handle_state_event(self, event: Event[EventStateChangedData]) -> None:
        if event.data["entity_id"] == self.cover_entity_id:
            self._detect_manual_change(event)
        self.hass.async_create_task(self.async_request_refresh(), eager_start=True)

    @callback
    def _detect_manual_change(self, event: Event[EventStateChangedData]) -> None:
        """Pausa o controle quando a cortina se mexe sem comando nosso."""
        old, new = event.data["old_state"], event.data["new_state"]
        if old is None or new is None:
            return
        if {old.state, new.state} & {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return
        now = dt_util.utcnow()
        if self._last_command is not None and now - self._last_command < COMMAND_GRACE:
            return
        started_moving = new.state in MOVING_STATES and old.state not in MOVING_STATES
        position_changed = old.attributes.get(ATTR_CURRENT_POSITION) != new.attributes.get(
            ATTR_CURRENT_POSITION
        )
        pause = self.settings.manual_pause
        if not (started_moving or position_changed) or pause <= 0 or not self.settings.enabled:
            return
        self.manual_until = now + timedelta(minutes=pause)
        self._schedule_save()
        _LOGGER.info(
            "%s: ajuste manual detectado; controle automático pausado por %.0f min",
            self.config_entry.title,
            pause,
        )

    # ------------------------------------------------------------- readings

    def _state_value(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state

    def _float_value(self, entity_id: str | None) -> float | None:
        value = self._state_value(entity_id)
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    # ---------------------------------------------------------------- update

    async def _async_update_data(self) -> SolarCoverData:
        now = dt_util.utcnow()
        settings = self.settings

        azimuth, elevation = solar_position(
            now, self.hass.config.latitude, self.hass.config.longitude
        )

        lux_ok: bool | None = None
        if self.lux_entity:
            before = self.lux_filter.state
            lux_ok = self.lux_filter.update(
                now,
                self._float_value(self.lux_entity),
                settings.lux_on,
                settings.lux_off,
                timedelta(minutes=settings.lux_delay),
            )
            if lux_ok != before:
                self._schedule_save()

        alarm = (
            alarm_state_from(self._state_value(self.alarm_entity)) if self.alarm_entity else None
        )
        decision = decide(
            DecisionInput(
                azimuth=azimuth,
                elevation=elevation,
                facade_azimuth=self.facade_azimuth,
                max_incidence=self.max_incidence,
                geometry=self.geometry,
                horizon=self.horizon,
                margin_cm=settings.margin,
                alarm=alarm,
                temperature=self._float_value(self.temperature_entity),
                temperature_min=settings.temperature_min if self.temperature_entity else None,
                lux_ok=lux_ok,
            )
        )

        if self.manual_until is not None and now >= self.manual_until:
            self.manual_until = None
            self._schedule_save()

        current, moving = self._cover_reading()
        lit = 0.0
        if current is not None and decision.sun.drop is not None and not decision.building_blocked:
            lit = lit_door_height(self.geometry, decision.sun.drop, current)

        status = await self._async_apply(decision, current, moving, now)

        return SolarCoverData(
            now=now,
            sun_azimuth=azimuth,
            sun_elevation=elevation,
            decision=decision,
            current_position=current,
            door_lit_cm=lit,
            status=status,
            lux_ok=lux_ok,
            manual_until=self.manual_until,
        )

    def _cover_reading(self) -> tuple[float | None, bool]:
        state = self.hass.states.get(self.cover_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None, False
        position = state.attributes.get(ATTR_CURRENT_POSITION)
        try:
            current = float(position) if position is not None else None
        except (TypeError, ValueError):
            current = None
        return current, state.state in MOVING_STATES

    async def _async_apply(
        self, decision: Decision, current: float | None, moving: bool, now: datetime
    ) -> ControlStatus:
        settings = self.settings
        if not settings.enabled:
            return ControlStatus.DISABLED
        if self.manual_until is not None:
            return ControlStatus.PAUSED
        if decision.hold:
            return ControlStatus.HOLD

        plan = plan_move(
            current=current,
            desired=decision.position,
            now=now,
            last_move=self._last_command,
            tolerance=settings.tolerance,
            min_interval=timedelta(minutes=settings.min_interval),
            moving=moving,
        )
        if plan.status is MoveStatus.MOVE and plan.target is not None:
            # o mesmo comando já enviado há pouco ainda está a caminho: não repetir
            in_flight = (
                plan.target == self._last_target
                and self._last_command is not None
                and now - self._last_command < COMMAND_GRACE
            )
            if not in_flight:
                await self._async_send_position(plan.target, now)
            return ControlStatus.MOVING
        return {
            MoveStatus.IDLE: ControlStatus.IDLE,
            MoveStatus.WAITING: ControlStatus.WAITING,
            MoveStatus.MOVING: ControlStatus.MOVING,
            MoveStatus.UNAVAILABLE: ControlStatus.UNAVAILABLE,
        }[plan.status]

    async def _async_send_position(self, position: int, now: datetime) -> None:
        _LOGGER.debug("%s: movendo para %s%%", self.cover_entity_id, position)
        self._last_command = now
        self._last_target = position
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: self.cover_entity_id, ATTR_POSITION: position},
            blocking=False,
            context=Context(),
        )
