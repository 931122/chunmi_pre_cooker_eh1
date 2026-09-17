"""Number entity for Chunmi Electric Pressure Cooker holding duration."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChunmiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Chunmi cooker number platform."""
    coordinator: ChunmiCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([ChunmiHoldingDurationNumber(coordinator, config_entry)])


class ChunmiHoldingDurationNumber(CoordinatorEntity[ChunmiCoordinator], NumberEntity):
    """Number entity to adjust holding pressure duration (保压时间)."""

    _attr_has_entity_name = True
    _attr_name = "保压时间"
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.data['did']}_holding_duration"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, str(self._config_entry.data["did"]))},
            "name": self._config_entry.title or "纯米智能电压力锅",
            "manufacturer": "纯米 (Chunmi)",
            "model": self._config_entry.data.get("model", "chunmi.pre_cooker.eh1"),
        }

    @property
    def native_min_value(self) -> float:
        """Return min holding duration for current mode."""
        min_v, _, _ = self.coordinator.current_mode_duration_limits
        return float(min_v)

    @property
    def native_max_value(self) -> float:
        """Return max holding duration for current mode."""
        min_v, max_v, _ = self.coordinator.current_mode_duration_limits
        if max_v <= min_v:
            max_v = min_v + 1
        return float(max_v)

    @property
    def native_value(self) -> float:
        """Return currently selected holding duration."""
        return float(self.coordinator.selected_duration)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        est_total = self.coordinator.current_mode_estimated_total_time
        base_overhead = self.coordinator.current_mode_base_overhead
        limits = self.coordinator.current_mode_duration_limits
        return {
            "mode": self.coordinator.selected_mode,
            "taste": self.coordinator.current_taste_name,
            "estimated_total_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
            "estimated_total_minutes": est_total,
            "base_overhead_minutes": base_overhead,
            "holding_duration_range": f"{limits[0]}~{limits[1]} 分钟",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set holding pressure duration."""
        await self.coordinator.async_set_selected_duration(int(value))
        self.async_write_ha_state()
