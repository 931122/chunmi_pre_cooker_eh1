"""Select entities for Chunmi Electric Pressure Cooker."""

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
    async_add_entities([
        ChunmiCookModeSelect(coordinator, config_entry),
        ChunmiTasteSelect(coordinator, config_entry),
    ])


class ChunmiCookerBaseSelect(CoordinatorEntity[ChunmiCoordinator], SelectEntity):
    """Base select entity for Chunmi cooker."""

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


class ChunmiCookModeSelect(ChunmiCookerBaseSelect):
    """Select entity to choose cooking mode."""

    _attr_icon = "mdi:rice"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "烹饪模式选择"
        self._attr_unique_id = f"{config_entry.data['did']}_cook_mode_select"
        self._attr_options = list(PRESET_COOK_MODES.keys())

    @property
    def current_option(self) -> str:
        """Return the currently selected cooking mode."""
        return self.coordinator.selected_mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected cooking mode."""
        if option in self._attr_options:
            await self.coordinator.async_set_selected_mode(option)
            self.async_write_ha_state()


class ChunmiTasteSelect(ChunmiCookerBaseSelect):
    """Select entity to choose cooking taste preference."""

    _attr_icon = "mdi:food-variant"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_name = "口感偏好"
        self._attr_unique_id = f"{config_entry.data['did']}_taste_select"

    @property
    def options(self) -> list[str]:
        """Return taste options for current mode."""
        return self.coordinator.current_mode_taste_options

    @property
    def current_option(self) -> str:
        """Return the currently selected taste name."""
        return self.coordinator.current_taste_name

    async def async_select_option(self, option: str) -> None:
        """Change the selected taste option."""
        await self.coordinator.async_set_selected_taste(option)
        self.async_write_ha_state()
