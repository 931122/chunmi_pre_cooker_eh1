"""Button entities for Chunmi Electric Pressure Cooker."""

from homeassistant.components.button import ButtonEntity
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
    """Set up the Chunmi cooker button platform."""
    coordinator: ChunmiCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([
        ChunmiStartCookButton(coordinator, config_entry),
        ChunmiCancelCookButton(coordinator, config_entry),
        ChunmiOpenLidJuiceButton(coordinator, config_entry),
        ChunmiKeepWarmButton(coordinator, config_entry),
    ])


class ChunmiCookerBaseButton(CoordinatorEntity[ChunmiCoordinator], ButtonEntity):
    """Base button for Chunmi cooker."""

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


class ChunmiStartCookButton(ChunmiCookerBaseButton):
    """Button to start cooking with currently selected mode."""

    _attr_name = "开始烹饪"
    _attr_icon = "mdi:pot-steam"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_start_cooking"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_start_cooking()


class ChunmiCancelCookButton(ChunmiCookerBaseButton):
    """Button to stop/cancel cooking."""

    _attr_name = "停止烹饪"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_cancel_cooking"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_cancel_cooking()


class ChunmiOpenLidJuiceButton(ChunmiCookerBaseButton):
    """Button to start 开盖收汁 directly."""

    _attr_name = "开盖收汁"
    _attr_icon = "mdi:pot-steam-outline"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_open_lid_juice"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_start_cooking("开盖收汁")


class ChunmiKeepWarmButton(ChunmiCookerBaseButton):
    """Button to start 保温 directly."""

    _attr_name = "开始保温"
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator: ChunmiCoordinator, config_entry: ConfigEntry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.data['did']}_keep_warm"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_start_cooking("保温")

