"""DataUpdateCoordinator for Chunmi Electric Pressure Cooker."""

from datetime import timedelta
import json
import logging
from typing import Any, Dict

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PRESET_COOK_MODES
from .device import ChunmiDevice

_LOGGER = logging.getLogger(__name__)


class ChunmiCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to manage polling data from the cooker."""

    def __init__(self, hass: HomeAssistant, device: ChunmiDevice):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device.did}",
            update_interval=timedelta(seconds=15),
        )
        self.device = device
        self.selected_mode = "大米饭"

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from cooker."""
        try:
            data = await self.device.async_get_props()
            if not data or "status" not in data:
                raise UpdateFailed("Failed to fetch properties from Chunmi cooker")

            # Adjust polling interval dynamically: 5s when cooking, 20s when idle
            status = data.get("status", 10)
            if status == 2:  # Cooking
                self.update_interval = timedelta(seconds=5)
            else:
                self.update_interval = timedelta(seconds=20)

            return data
        except Exception as err:
            raise UpdateFailed(f"Communication error: {err}") from err

    async def async_start_cooking(self, mode_name: str = None) -> bool:
        """Trigger start cooking with selected or specified mode."""
        mode = mode_name or self.selected_mode
        if mode not in PRESET_COOK_MODES:
            _LOGGER.error("Unknown cooking mode: %s", mode)
            return False

        preset = PRESET_COOK_MODES[mode]
        res = await self.device.async_start_cooking(preset["name"], preset["cook_code"], hass=self.hass)
        
        is_success = res.get("success", False)
        if not is_success:
            raw = res.get("raw_result")
            c_lock = res.get("c_lock")
            c_status = res.get("c_status")
            
            msg = f"纯米电压力锅未能启动【{preset['name']}】（设备响应码: {raw}）。\n"
            if preset["name"] != "开盖收汁" and (c_status == 1 or c_lock == 2):
                msg += f"原因提示：锅盖未完全锁紧或处于开盖状态（当前 c_lock={c_lock}, c_status={c_status}）。\n电压力锅具备机械安全联锁保护，正常烹饪请先盖好锅盖并顺时针旋转把手锁死后再点击启动！"
            else:
                msg += f"当前状态: c_lock={c_lock}, c_status={c_status}。"

            persistent_notification.async_create(
                self.hass,
                message=msg,
                title="纯米电压力锅提示",
                notification_id=f"chunmi_cooker_{self.device.did}_start_msg",
            )
            _LOGGER.warning(msg)
            raise HomeAssistantError(msg)

        await self.async_request_refresh()
        return True

    async def async_cancel_cooking(self) -> bool:
        """Trigger stop cooking."""
        success = await self.device.async_cancel_cooking(hass=self.hass)
        if success:
            await self.async_request_refresh()
        return success
