"""Select entity for Chunmi Electric Pressure Cooker cooking modes."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRESET_COOK_MODES
from .coordinator import ChunmiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Chunmi cooker select platform."""
    coordinator: ChunmiCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([ChunmiCookModeSelect(coordinator, config_entry)])


class ChunmiCookModeSelect(CoordinatorEntity[ChunmiCoordinator], SelectEntity):
    """Select entity to choose cooking mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "cook_mode"
    _attr_icon = "mdi:rice"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = "烹饪模式选择"
        self._attr_unique_id = f"{config_entry.data['did']}_cook_mode_select"
        self._attr_options = list(PRESET_COOK_MODES.keys())

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
    def current_option(self) -> str:
        """Return the currently selected cooking mode."""
        return self.coordinator.selected_mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected cooking mode."""
        if option in self._attr_options:
            self.coordinator.selected_mode = option
            self.async_write_ha_state()
