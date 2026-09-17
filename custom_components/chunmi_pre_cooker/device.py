"""miIO communication driver for Chunmi Electric Pressure Cooker."""

import asyncio
import hashlib
import json
import logging
import socket
import struct
import time
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import decode_menu_gbk, encode_name_gbk

_LOGGER = logging.getLogger(__name__)

HELLO_PACKET = bytes.fromhex("21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff")


class ChunmiDevice:
    """Handles low-level miIO protocol communication with the cooker."""

    def __init__(self, host: str, token: str, did: int = 0, port: int = 54321):
        self.host = host
        self.port = port
        self.did = int(did)
        self.token_bytes = bytes.fromhex(token)
        self.key = hashlib.md5(self.token_bytes).digest()
        self.iv = hashlib.md5(self.key + self.token_bytes).digest()

        self._last_stamp = 0
        self._last_stamp_time = 0.0
        self._cmd_id = 0
        self._lock = asyncio.Lock()

    def _encrypt(self, plaintext: bytes) -> bytes:
        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len]) * pad_len
        encryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.iv)).encryptor()
        return encryptor.update(padded) + encryptor.finalize()

    def _decrypt(self, ciphertext: bytes) -> bytes:
        decryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.iv)).decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        pad_len = decrypted[-1]
        if 1 <= pad_len <= 16:
            return decrypted[:-pad_len]
        return decrypted

    async def async_handshake(self) -> bool:
        """Perform UDP handshake to synchronize timestamp and DID."""
        loop = asyncio.get_running_loop()
        try:
            def _do_handshake():
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(2.5)
                    s.sendto(HELLO_PACKET, (self.host, self.port))
                    data, _ = s.recvfrom(1024)
                    return data

            data = await loop.run_in_executor(None, _do_handshake)
            if len(data) >= 32 and data[:2] == b"\x21\x31":
                _, _, _, did, stamp = struct.unpack(">2sHIII", data[:16])
                if self.did == 0 or self.did != did:
                    self.did = did
                self._last_stamp = stamp
                self._last_stamp_time = time.time()
                return True
        except Exception as err:
            _LOGGER.debug("Handshake failed with %s: %s", self.host, err)
        return False

    async def async_send_command(self, method: str, params: list, retries: int = 2) -> Optional[Any]:
        """Send miIO RPC command and return parsed result."""
        async with self._lock:
            for attempt in range(retries + 1):
                # Ensure valid timestamp handshake
                now = time.time()
                if self._last_stamp == 0 or (now - self._last_stamp_time > 120):
                    if not await self.async_handshake():
                        if attempt == retries:
                            return None
                        await asyncio.sleep(0.3)
                        continue

                current_stamp = int(self._last_stamp + (now - self._last_stamp_time))
                self._cmd_id = (self._cmd_id % 9999) + 1

                payload = json.dumps({
                    "id": self._cmd_id,
                    "method": method,
                    "params": params
                }).encode("utf-8")

                encrypted = self._encrypt(payload)

                header = bytearray(32)
                header[0:2] = b"\x21\x31"
                header[2:4] = struct.pack(">H", 32 + len(encrypted))
                header[4:8] = b"\x00\x00\x00\x00"
                header[8:12] = struct.pack(">I", self.did)
                header[12:16] = struct.pack(">I", current_stamp + 1)
                header[16:32] = hashlib.md5(header[:16] + self.token_bytes + encrypted).digest()

                packet = bytes(header) + encrypted

                loop = asyncio.get_running_loop()
                try:
                    def _send_and_recv():
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                            s.settimeout(2.5)
                            s.sendto(packet, (self.host, self.port))
                            data, _ = s.recvfrom(4096)
                            return data

                    resp_data = await loop.run_in_executor(None, _send_and_recv)
                    if len(resp_data) > 32 and resp_data[:2] == b"\x21\x31":
                        decrypted = self._decrypt(resp_data[32:])
                        resp_json = json.loads(decrypted.decode("utf-8", errors="ignore"))
                        return resp_json.get("result")
                except socket.timeout:
                    _LOGGER.debug("Timeout waiting for response from %s (attempt %s)", self.host, attempt + 1)
                    # Refresh handshake on next attempt
                    self._last_stamp = 0
                except Exception as err:
                    _LOGGER.warning("Error communicating with %s: %s", self.host, err)
                    self._last_stamp = 0

                await asyncio.sleep(0.3)

            return None

    async def async_get_props(self) -> Dict[str, Any]:
        """Fetch all relevant properties from device."""
        props_to_fetch = [
            "status",
            "s_cook1",
            "temp",
            "t_left",
            "t_kw",
            "t_pre",
            "menu",
            "t_cook",
            "kpa",
            "c_lock",
            "c_status",
        ]
        data: Dict[str, Any] = {}

        for prop in props_to_fetch:
            res = await self.async_send_command("get_prop", [prop])
            if res and isinstance(res, list) and len(res) > 0:
                data[prop] = res[0]
            await asyncio.sleep(0.02)

        if "menu" in data and isinstance(data["menu"], str):
            data["menu_name"] = decode_menu_gbk(data["menu"])
        else:
            data["menu_name"] = "空闲"

        return data

    async def async_send_mips_rpc(self, hass: Any, method: str, params: list) -> Optional[Any]:
        """Try sending RPC command via Xiaomi Central Gateway MIPS broker."""
        try:
            xiaomi_home = hass.data.get("xiaomi_home", {})
            clients = xiaomi_home.get("miot_clients", {})
            for entry_id, client in clients.items():
                mips_local = getattr(client, "_mips_local", {})
                for gid, mips in mips_local.items():
                    req_func = getattr(mips, "_MipsLocalClient__request_async", None)
                    if not req_func:
                        continue
                    payload = json.dumps({
                        "did": str(self.did),
                        "rpc": {
                            "id": 8,
                            "method": method,
                            "params": params
                        }
                    })
                    _LOGGER.warning(
                        "纯米电压力锅尝试通过小米中枢网关 (Group: %s) 发送 RPC [%s]: %s",
                        gid, method, payload
                    )
                    res = await req_func("proxy/rpcReq", payload, timeout_ms=8000)
                    _LOGGER.warning("中枢网关 RPC [%s] 响应: %s", method, res)
                    return res
        except Exception as err:
            _LOGGER.warning("通过中枢网关 MIPS 发送 RPC 失败: %s", err)
        return None

    async def async_start_cooking(self, name: str, cook_code: str, hass: Optional[Any] = None) -> Dict[str, Any]:
        """Start cooking using given recipe name and cookCode."""
        name_gbk = encode_name_gbk(name)
        res = None

        # 1. 优先尝试通过小米中枢网关 MIPS 代理下发启动指令（规避固件本地局域网限制）
        if hass:
            mips_res = await self.async_send_mips_rpc(hass, "set_start", [name_gbk, cook_code])
            if mips_res and isinstance(mips_res, dict):
                if "result" in mips_res:
                    res = mips_res["result"]
                elif "error" in mips_res:
                    _LOGGER.warning("MIPS set_start 返回错误: %s", mips_res["error"])
                elif mips_res.get("code") == 0:
                    res = ["ok"]

        # 2. 如果中枢网关未处理或不可用，回退至本地 UDP 直接通讯
        if res is None:
            res = await self.async_send_command("set_start", [name_gbk, cook_code])
        
        # Check current lid switches
        c_lock_res = await self.async_send_command("get_prop", ["c_lock"])
        c_status_res = await self.async_send_command("get_prop", ["c_status"])
        c_lock = c_lock_res[0] if c_lock_res and isinstance(c_lock_res, list) else None
        c_status = c_status_res[0] if c_status_res and isinstance(c_status_res, list) else None

        _LOGGER.warning(
            "纯米电压力锅发送 set_start [%s] 结果: %s (当前锅盖状态: c_lock=%s, c_status=%s)",
            name, res, c_lock, c_status
        )

        # Note: [4] is returned when device rejects unauthenticated local UDP write commands
        is_success = (
            res is not None
            and isinstance(res, list)
            and len(res) > 0
            and res != ["error"]
            and res != [4]
        )
        return {
            "success": is_success,
            "raw_result": res,
            "c_lock": c_lock,
            "c_status": c_status,
        }

    async def async_cancel_cooking(self, hass: Optional[Any] = None) -> bool:
        """Cancel current cooking session."""
        if hass:
            mips_res = await self.async_send_mips_rpc(hass, "cancel_cooking", [])
            if mips_res and isinstance(mips_res, dict) and (mips_res.get("code") == 0 or "result" in mips_res):
                return True
        res = await self.async_send_command("cancel_cooking", [])
        _LOGGER.warning("纯米电压力锅发送 cancel_cooking 结果: %s", res)
        return res is not None
