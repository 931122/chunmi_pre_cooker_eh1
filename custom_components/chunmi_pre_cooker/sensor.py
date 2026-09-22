"""Sensors for Chunmi Electric Pressure Cooker."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    PHASE_MAP_SLUG,
    PHASE_MAP_ZH,
    STATUS_MAP_SLUG,
    STATUS_MAP_ZH,
)
from .coordinator import ChunmiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Chunmi cooker sensor platform."""
    coordinator: ChunmiCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([
        ChunmiStatusSensor(coordinator, config_entry),
        ChunmiPhaseSensor(coordinator, config_entry),
        ChunmiLeftTimeSensor(coordinator, config_entry),
        ChunmiTemperatureSensor(coordinator, config_entry),
        ChunmiPressureSensor(coordinator, config_entry),
        ChunmiCurrentMenuSensor(coordinator, config_entry),
        ChunmiLidStatusSensor(coordinator, config_entry),
        ChunmiLockStatusSensor(coordinator, config_entry),
    ])


class ChunmiBaseSensor(CoordinatorEntity[ChunmiCoordinator], SensorEntity):
    """Base sensor for Chunmi cooker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, str(self._config_entry.data["did"]))},
            "name": self._config_entry.title or "纯米智能电压力锅",
            "manufacturer": "纯米 (Chunmi)",
            "model": self._config_entry.data.get("model", "chunmi.pre_cooker.eh1"),
        }


class ChunmiStatusSensor(ChunmiBaseSensor):
    """Sensor for cooking state."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:chef-hat"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["standby", "cooking", "keep_warm", "delayed", "paused", "completed"]

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_status"

    @property
    def native_value(self) -> str:
        """Return standardized status slug."""
        status = self.coordinator.data.get("status")
        s_cook1 = self.coordinator.data.get("s_cook1", 0)

        if s_cook1 == 6 or status == 3:
            return "keep_warm"
        if s_cook1 == 7:
            return "completed"
        if status == 4:
            return "delayed"
        if status == 2:
            return "cooking"
        if status == 5:
            return "paused"
        return STATUS_MAP_SLUG.get(status, "standby")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        status = self.coordinator.data.get("status")
        s_cook1 = self.coordinator.data.get("s_cook1", 0)
        return {
            "status_code": status,
            "phase_code": s_cook1,
            "status_zh": STATUS_MAP_ZH.get(status, "待机"),
            "phase_zh": PHASE_MAP_ZH.get(s_cook1, "空闲"),
            "status_slug": STATUS_MAP_SLUG.get(status, "standby"),
            "phase_slug": PHASE_MAP_SLUG.get(s_cook1, "idle"),
            "is_cooking": status == 2,
            "is_keep_warm": status == 3 or s_cook1 == 6,
            "is_order": status == 4,
        }


class ChunmiPhaseSensor(ChunmiBaseSensor):
    """Sensor for detailed cooking phase."""

    _attr_translation_key = "phase"
    _attr_icon = "mdi:progress-clock"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "idle", "preheating", "waiting_lock", "pressurizing",
        "holding_pressure", "depressurizing", "keep_warm", "completed",
        "pressure_relief_open", "waiting_open", "adding_ingredients", "waiting_continue",
    ]

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_phase"

    @property
    def native_value(self) -> str:
        """Return standardized cooking phase slug."""
        s_cook1 = self.coordinator.data.get("s_cook1", 0)
        status = self.coordinator.data.get("status", 10)
        if status in (1, 10) and s_cook1 == 0:
            return "idle"
        return PHASE_MAP_SLUG.get(s_cook1, "idle")

    @property
    def extra_state_attributes(self) -> dict:
        """Return phase attributes."""
        s_cook1 = self.coordinator.data.get("s_cook1", 0)
        return {
            "phase_code": s_cook1,
            "status_code": self.coordinator.data.get("status"),
            "phase_zh": PHASE_MAP_ZH.get(s_cook1, "空闲"),
            "phase_slug": PHASE_MAP_SLUG.get(s_cook1, "idle"),
        }


class ChunmiLeftTimeSensor(ChunmiBaseSensor):
    """Sensor for remaining cooking time."""

    _attr_translation_key = "left_time"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_left_time"

    @property
    def native_value(self) -> int:
        """Return left time in seconds."""
        val = self.coordinator.data.get("t_left", 0)
        status = self.coordinator.data.get("status", 10)
        s_cook1 = self.coordinator.data.get("s_cook1", 0)

        # When in reservation/delay mode (status 4), return reservation countdown in seconds
        if status == 4:
            t_pre = self.coordinator.data.get("t_pre", 0)
            return int(t_pre * 60) if t_pre > 0 else int(val)

        # When idle/standby (1, 10), paused (5), keep-warm (3 or s_cook1==6), or finished (s_cook1==7),
        # remaining cooking time is 0
        if status in (1, 10, 5, 3) or s_cook1 in (6, 7) or val > 86400:
            return 0
        return int(val)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        est_total = self.coordinator.current_mode_estimated_total_time
        val = self.native_value  # total remaining seconds
        hours = val // 3600
        minutes = (val % 3600) // 60
        seconds = val % 60

        if val <= 0:
            formatted = "0秒"
        elif hours > 0:
            formatted = f"{hours}小时{minutes}分{seconds}秒"
        elif minutes > 0:
            formatted = f"{minutes}分{seconds}秒"
        else:
            formatted = f"{seconds}秒"

        hms = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        if est_total >= 1440:
            est_total_str = "持续恒温"
        elif est_total >= 60:
            eh = est_total // 60
            em = est_total % 60
            est_total_str = f"约 {eh}小时{em}分钟" if em > 0 else f"约 {eh}小时"
        else:
            est_total_str = f"约 {est_total} 分钟"

        # Keep warm duration calculation
        t_kw = int(self.coordinator.data.get("t_kw", 0))
        kw_h = t_kw // 3600
        kw_m = (t_kw % 3600) // 60
        kw_s = t_kw % 60
        if kw_h > 0:
            kw_formatted = f"{kw_h}小时{kw_m}分{kw_s}秒"
        elif kw_m > 0:
            kw_formatted = f"{kw_m}分{kw_s}秒"
        else:
            kw_formatted = f"{kw_s}秒"

        s_cook1 = self.coordinator.data.get("s_cook1", 0)
        status = self.coordinator.data.get("status", 10)

        return {
            "mode": self.coordinator.selected_mode,
            "mode_slug": self.coordinator.selected_mode_slug,
            "taste": self.coordinator.current_taste_name,
            "taste_slug": self.coordinator.current_taste_slug,
            "phase": PHASE_MAP_ZH.get(s_cook1, "空闲"),
            "phase_slug": PHASE_MAP_SLUG.get(s_cook1, "idle"),
            "remaining_time_formatted": formatted,
            "remaining_time_hms": hms,
            "remaining_hours": hours,
            "remaining_minutes": minutes,
            "remaining_seconds": seconds,
            "total_remaining_minutes": val // 60,
            "total_remaining_seconds": val,
            "keep_warm_seconds": t_kw,
            "keep_warm_formatted": kw_formatted if (t_kw > 0 or s_cook1 == 6 or status == 3) else "未保温",
            "preset_estimated_total_time": est_total_str,
            "preset_estimated_total_minutes": est_total,
            "selected_holding_duration": f"{self.coordinator.selected_duration} 分钟",
        }


class ChunmiTemperatureSensor(ChunmiBaseSensor):
    """Sensor for temperature."""

    _attr_translation_key = "temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_temperature"

    @property
    def native_value(self) -> float:
        """Return temperature in Celsius."""
        return self.coordinator.data.get("temp", 0)


class ChunmiPressureSensor(ChunmiBaseSensor):
    """Sensor for pressure."""

    _attr_translation_key = "pressure"
    _attr_icon = "mdi:gauge"
    _attr_native_unit_of_measurement = "kPa"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_pressure"

    @property
    def native_value(self) -> int:
        """Return pressure in kPa."""
        return self.coordinator.data.get("kpa", 0)


class ChunmiCurrentMenuSensor(ChunmiBaseSensor):
    """Sensor for current running recipe/menu."""

    _attr_translation_key = "current_menu"
    _attr_icon = "mdi:book-open-variant"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_current_menu"

    @property
    def native_value(self) -> str:
        """Return current decoded menu name."""
        return self.coordinator.data.get("menu_name", "空闲")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        est_total = self.coordinator.current_mode_estimated_total_time
        detail = self.coordinator.current_mode_detail
        steps = detail.get("steps", [])
        steps_text = "\n".join(f"{idx+1}. {s}" for idx, s in enumerate(steps))
        return {
            "selected_preset_mode": self.coordinator.selected_mode,
            "selected_mode_slug": self.coordinator.selected_mode_slug,
            "practice": detail.get("practice", "家常烹饪"),
            "recipe_description": detail.get("description", ""),
            "recipe_ingredients": detail.get("ingredients", []),
            "recipe_steps": steps,
            "recipe_practice_text": steps_text,
            "recipe_tips": detail.get("tips", ""),
            "taste": self.coordinator.current_taste_name,
            "taste_slug": self.coordinator.current_taste_slug,
            "holding_duration": f"{self.coordinator.selected_duration} 分钟",
            "estimated_total_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
        }


class ChunmiLidStatusSensor(ChunmiBaseSensor):
    """Sensor for cooker lid seated/closed state."""

    _attr_translation_key = "lid_status"
    _attr_icon = "mdi:pot"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["closed", "opened"]

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_c_status"

    @property
    def native_value(self) -> str:
        """Return lid state slug."""
        val = self.coordinator.data.get("c_status")
        if val == 2:
            return "closed"
        return "opened"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        val = self.coordinator.data.get("c_status")
        return {
            "raw_code": val,
            "status_zh": "已合盖到位" if val == 2 else "未合好/开盖",
        }


class ChunmiLockStatusSensor(ChunmiBaseSensor):
    """Sensor for cooker handle lock state."""

    _attr_translation_key = "lock_status"
    _attr_icon = "mdi:lock"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["locked", "unlocked"]

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_c_lock"

    @property
    def native_value(self) -> str:
        """Return lock state slug."""
        val = self.coordinator.data.get("c_lock")
        if val == 1:
            return "locked"
        return "unlocked"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        val = self.coordinator.data.get("c_lock")
        return {
            "raw_code": val,
            "status_zh": "已旋转锁死" if val == 1 else "未锁紧",
        }
