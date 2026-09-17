"""Sensors for Chunmi Electric Pressure Cooker."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_MAP
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

    _attr_name = "工作状态"
    _attr_icon = "mdi:chef-hat"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_status"

    @property
    def native_value(self) -> str:
        """Return human-readable status."""
        val = self.coordinator.data.get("status")
        return STATUS_MAP.get(val, f"未知状态({val})")


class ChunmiLeftTimeSensor(ChunmiBaseSensor):
    """Sensor for remaining cooking time."""

    _attr_name = "剩余时间"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_left_time"

    @property
    def native_value(self) -> int:
        """Return left time in minutes."""
        val = self.coordinator.data.get("t_left", 0)
        # When idle, device may report huge dummy values like 3526
        status = self.coordinator.data.get("status", 10)
        if status in (1, 10, 5) or val > 1440:
            return 0
        return int(val)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        est_total = self.coordinator.current_mode_estimated_total_time
        return {
            "mode": self.coordinator.selected_mode,
            "taste": self.coordinator.current_taste_name,
            "preset_estimated_total_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
            "preset_estimated_total_minutes": est_total,
            "selected_holding_duration": f"{self.coordinator.selected_duration} 分钟",
        }


class ChunmiTemperatureSensor(ChunmiBaseSensor):
    """Sensor for temperature."""

    _attr_name = "锅内温度"
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

    _attr_name = "当前压力"
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

    _attr_name = "当前烹饪模式"
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
            "practice": detail.get("practice", "家常烹饪"),
            "recipe_description": detail.get("description", ""),
            "recipe_ingredients": detail.get("ingredients", []),
            "recipe_steps": steps,
            "recipe_practice_text": steps_text,
            "recipe_tips": detail.get("tips", ""),
            "taste": self.coordinator.current_taste_name,
            "holding_duration": f"{self.coordinator.selected_duration} 分钟",
            "estimated_total_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
        }


class ChunmiLidStatusSensor(ChunmiBaseSensor):
    """Sensor for cooker lid seated/closed state."""

    _attr_name = "锅盖合盖状态"
    _attr_icon = "mdi:pot"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_c_status"

    @property
    def native_value(self) -> str:
        """Return lid state."""
        val = self.coordinator.data.get("c_status")
        if val == 2:
            return "已合盖到位"
        elif val == 1:
            return "未合好/开盖"
        return "未知"


class ChunmiLockStatusSensor(ChunmiBaseSensor):
    """Sensor for cooker handle lock state."""

    _attr_name = "手柄锁止状态"
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_c_lock"

    @property
    def native_value(self) -> str:
        """Return lock state."""
        val = self.coordinator.data.get("c_lock")
        if val == 1:
            return "已旋转锁死"
        elif val == 2:
            return "未锁紧"
        return "未知"

