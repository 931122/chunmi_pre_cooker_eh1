"""DataUpdateCoordinator for Chunmi Electric Pressure Cooker."""

from datetime import timedelta
import json
import logging
from typing import Any, Dict

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    PRESET_COOK_MODES,
    ALL_MODES_ESTIMATED_TIME_CACHE,
    customize_cook_code,
    get_holding_duration_from_code,
    get_mode_base_overhead,
    get_mode_duration_limits,
    get_mode_taste_names,
    get_mode_total_estimated_time,
)
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
        self.selected_taste_idx = 1  # 0: 偏软/软糯, 1: 适中, 2: 偏硬/嚼劲
        self.selected_duration = 15  # minutes

    @property
    def current_mode_preset(self) -> Dict[str, Any]:
        """Return preset config of currently selected mode."""
        return PRESET_COOK_MODES.get(self.selected_mode, PRESET_COOK_MODES["大米饭"])

    @property
    def current_mode_taste_options(self) -> list:
        """Return available taste option names for current mode."""
        code = self.current_mode_preset["cook_code"]
        return get_mode_taste_names(code)

    @property
    def current_taste_name(self) -> str:
        """Return currently selected taste name."""
        options = self.current_mode_taste_options
        if len(options) == 1:
            return options[0]
        if 0 <= self.selected_taste_idx < len(options):
            return options[self.selected_taste_idx]
        return options[1] if len(options) > 1 else options[0]

    @property
    def current_mode_duration_limits(self) -> tuple:
        """Return (min, max, default) duration in minutes for current mode."""
        code = self.current_mode_preset["cook_code"]
        min_v, max_v, _ = get_mode_duration_limits(code)
        def_v = get_holding_duration_from_code(code, taste_idx=self.selected_taste_idx)
        return (min_v, max_v, def_v)

    @property
    def current_mode_base_overhead(self) -> int:
        """Return fixed heating/exhausting overhead in minutes for current mode."""
        code = self.current_mode_preset["cook_code"]
        return get_mode_base_overhead(code)

    @property
    def current_mode_estimated_total_time(self) -> int:
        """Return total estimated cooking time in minutes for current mode & duration."""
        code = self.current_mode_preset["cook_code"]
        if self.selected_mode == "保温":
            return 1440
        return get_mode_total_estimated_time(code, duration=self.selected_duration)

    @property
    def all_modes_estimated_time_dict(self) -> Dict[str, str]:
        """Return dictionary of estimated total cooking time for all preset modes."""
        return ALL_MODES_ESTIMATED_TIME_CACHE

    async def async_set_selected_mode(self, mode: str) -> None:
        """Set selected cooking mode and reset taste and duration to defaults."""
        if mode in PRESET_COOK_MODES:
            self.selected_mode = mode
            self.selected_taste_idx = 1  # Reset to 适中
            min_dur, max_dur, def_dur = self.current_mode_duration_limits
            self.selected_duration = def_dur
            self.async_update_listeners()

    async def async_set_selected_taste(self, taste_name: str) -> None:
        """Set selected taste option and adjust default holding duration."""
        options = self.current_mode_taste_options
        if taste_name in options:
            self.selected_taste_idx = options.index(taste_name)
            code = self.current_mode_preset["cook_code"]
            self.selected_duration = get_holding_duration_from_code(code, self.selected_taste_idx)
            self.async_update_listeners()

    async def async_set_selected_duration(self, duration: int) -> None:
        """Set selected holding pressure duration."""
        min_dur, max_dur, _ = self.current_mode_duration_limits
        self.selected_duration = max(min_dur, min(max_dur, duration))
        self.async_update_listeners()

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

    async def async_start_cooking(
        self,
        mode_name: str = None,
        taste: Any = None,
        duration: int = None,
    ) -> bool:
        """Trigger start cooking with customized taste and duration."""
        mode = mode_name or self.selected_mode
        if mode not in PRESET_COOK_MODES:
            _LOGGER.error("Unknown cooking mode: %s", mode)
            return False

        preset = PRESET_COOK_MODES[mode]

        # Resolve taste index
        t_idx = self.selected_taste_idx
        if taste is not None:
            if isinstance(taste, int) and 0 <= taste <= 2:
                t_idx = taste
            elif isinstance(taste, str):
                options = get_mode_taste_names(preset["cook_code"])
                if taste in options:
                    t_idx = options.index(taste)
                elif "软" in taste or "烂" in taste:
                    t_idx = 0
                elif "硬" in taste or "嚼" in taste or "弹" in taste:
                    t_idx = 2
                else:
                    t_idx = 1

        # Resolve duration
        dur = duration if duration is not None else self.selected_duration

        # Generate dynamically customized cook code
        custom_code = customize_cook_code(
            preset["cook_code"],
            taste_index=t_idx,
            duration=dur,
        )

        _LOGGER.warning(
            "纯米电压力锅下发烹饪【%s】(口感索引: %d, 保压时间: %d 分钟)",
            preset["name"], t_idx, dur
        )

        res = await self.device.async_start_cooking(preset["name"], custom_code, hass=self.hass)
        
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
