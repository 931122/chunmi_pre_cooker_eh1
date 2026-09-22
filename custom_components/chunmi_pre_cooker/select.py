"""Select entities for Chunmi Electric Pressure Cooker."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALL_RECIPE_SLUGS, DOMAIN, PRESET_COOK_MODES
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
    _attr_translation_key = "cook_mode"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_cook_mode_select"
        self._attr_options = ALL_RECIPE_SLUGS

    @property
    def current_option(self) -> str:
        """Return the currently selected cooking mode slug."""
        return self.coordinator.selected_mode_slug

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes with practice, recipe steps, and estimated time."""
        est_total = self.coordinator.current_mode_estimated_total_time
        limits = self.coordinator.current_mode_duration_limits
        detail = self.coordinator.current_mode_detail
        steps = detail.get("steps", [])
        steps_text = "\n".join(f"{idx+1}. {s}" for idx, s in enumerate(steps))
        return {
            "mode_name": self.coordinator.selected_mode,
            "mode_slug": self.coordinator.selected_mode_slug,
            "practice": detail.get("practice", "家常烹饪"),
            "recipe_description": detail.get("description", ""),
            "recipe_ingredients": detail.get("ingredients", []),
            "recipe_steps": steps,
            "recipe_practice_text": steps_text,
            "recipe_tips": detail.get("tips", ""),
            "estimated_cooking_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
            "estimated_cooking_minutes": est_total,
            "holding_duration": f"{self.coordinator.selected_duration} 分钟",
            "holding_duration_range": f"{limits[0]}~{limits[1]} 分钟",
            "taste": self.coordinator.current_taste_name,
            "all_modes_estimated_time": self.coordinator.all_modes_estimated_time_dict,
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected cooking mode."""
        await self.coordinator.async_set_selected_mode(option)
        self.async_write_ha_state()


class ChunmiTasteSelect(ChunmiCookerBaseSelect):
    """Select entity to choose cooking taste preference."""

    _attr_icon = "mdi:food-variant"
    _attr_translation_key = "taste"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_taste_select"

    @property
    def options(self) -> list[str]:
        """Return taste option slugs for current mode."""
        return self.coordinator.current_mode_taste_slugs

    @property
    def current_option(self) -> str:
        """Return the currently selected taste slug."""
        return self.coordinator.current_taste_slug

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        est_total = self.coordinator.current_mode_estimated_total_time
        return {
            "mode": self.coordinator.selected_mode,
            "mode_slug": self.coordinator.selected_mode_slug,
            "taste_name": self.coordinator.current_taste_name,
            "taste_slug": self.coordinator.current_taste_slug,
            "holding_duration": f"{self.coordinator.selected_duration} 分钟",
            "estimated_cooking_time": f"约 {est_total} 分钟" if est_total < 1440 else "持续恒温",
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected taste option."""
        await self.coordinator.async_set_selected_taste(option)
        self.async_write_ha_state()
