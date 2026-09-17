"""Config flow for Chunmi Electric Pressure Cooker integration."""

import asyncio
import json
import logging
import os
import socket
import struct
import time
from typing import Any, Dict, List, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DID, CONF_HOST, CONF_MODEL, CONF_TOKEN, DEFAULT_MODEL, DEFAULT_NAME, DOMAIN
from .device import HELLO_PACKET, ChunmiDevice

_LOGGER = logging.getLogger(__name__)


def _scan_xiaomi_home_storage(hass: HomeAssistant) -> List[Dict[str, Any]]:
    """Scan existing xiaomi_home storage for Chunmi cooker credentials."""
    storage_dir = hass.config.path(".storage/xiaomi_home/miot_devices")
    discovered = []
    if not os.path.exists(storage_dir):
        return discovered

    try:
        for fname in os.listdir(storage_dir):
            if fname.endswith(".dict"):
                fpath = os.path.join(storage_dir, fname)
                try:
                    with open(fpath, "rb") as f:
                        raw = f.read()
                    data = {}
                    if len(raw) > 32:
                        try:
                            data = json.loads(raw[:-32].decode("utf-8", errors="ignore"))
                        except Exception:
                            pass
                    if not data:
                        try:
                            data = json.loads(raw.decode("utf-8", errors="ignore"))
                        except Exception:
                            pass
                    for did, dev in data.items():
                        model = dev.get("model", "")
                        if "pre_cooker" in model or model == "chunmi.pre_cooker.eh1":
                            discovered.append({
                                CONF_DID: str(dev.get("did", did)),
                                CONF_TOKEN: dev.get("token", ""),
                                CONF_MODEL: model,
                                "name": dev.get("name", "压力锅"),
                                CONF_HOST: dev.get("local_ip") or "",
                            })
                except Exception as err:
                    _LOGGER.debug("Error reading storage file %s: %s", fname, err)
    except Exception as err:
        _LOGGER.debug("Error scanning storage dir: %s", err)

    return discovered


def _discover_device_ip(target_did: str) -> Optional[str]:
    """Discover cooker IP via UDP broadcast hello packet."""
    try:
        did_int = int(target_did)
    except ValueError:
        return None

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.settimeout(1.5)

            # Broadcast on standard miIO port
            for bcast in ["255.255.255.255", "192.168.1.255", "192.168.0.255", "192.168.31.255"]:
                try:
                    s.sendto(HELLO_PACKET, (bcast, 54321))
                except Exception:
                    pass

            start = time.time()
            while time.time() - start < 2.0:
                try:
                    data, addr = s.recvfrom(1024)
                    if len(data) >= 32 and data[:2] == b"\x21\x31":
                        did = struct.unpack(">I", data[8:12])[0]
                        if did == did_int:
                            return addr[0]
                except socket.timeout:
                    break
    except Exception as err:
        _LOGGER.debug("Error during UDP discovery: %s", err)

    return None


class ChunmiCookerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chunmi Electric Pressure Cooker."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            token = user_input[CONF_TOKEN].strip()
            did = str(user_input.get(CONF_DID, "")).strip()

            # Test connection
            device = ChunmiDevice(host, token, int(did) if did else 0)
            if not await device.async_handshake():
                errors["base"] = "cannot_connect"
            else:
                if not did:
                    did = str(device.did)
                await self.async_set_unique_id(did)
                self._abort_if_unique_id_configured()

                title = user_input.get("name") or DEFAULT_NAME
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_TOKEN: token,
                        CONF_DID: did,
                        CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL),
                    },
                )

        # Try auto-detecting credentials from xiaomi_home storage
        discovered = await self.hass.async_add_executor_job(_scan_xiaomi_home_storage, self.hass)

        default_host = ""
        default_token = ""
        default_did = ""
        default_name = DEFAULT_NAME
        default_model = DEFAULT_MODEL

        if discovered:
            dev = discovered[0]
            default_did = dev[CONF_DID]
            default_token = dev[CONF_TOKEN]
            default_name = f"纯米电压力锅 ({dev['name']})"
            default_model = dev[CONF_MODEL]
            if dev.get(CONF_HOST):
                default_host = dev[CONF_HOST]
            else:
                ip = await self.hass.async_add_executor_job(_discover_device_ip, default_did)
                if ip:
                    default_host = ip

        data_schema = vol.Schema({
            vol.Required(CONF_HOST, default=default_host): str,
            vol.Required(CONF_TOKEN, default=default_token): str,
            vol.Optional(CONF_DID, default=default_did): str,
            vol.Optional("name", default=default_name): str,
            vol.Optional(CONF_MODEL, default=default_model): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "discovered_hint": "已从现有插件自动读取到凭证" if default_token else "请手动输入设备信息"
            }
        )
