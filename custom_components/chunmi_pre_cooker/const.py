"""Constants and Presets for Chunmi Electric Pressure Cooker."""

DOMAIN = "chunmi_pre_cooker"
DEFAULT_NAME = "纯米智能电压力锅"
DEFAULT_PORT = 54321

CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_DID = "did"
CONF_MODEL = "model"

DEFAULT_MODEL = "chunmi.pre_cooker.eh1"

def encode_name_gbk(name: str) -> str:
    """Encode recipe name to 28-char GBK hex format used by Chunmi (up to 7 chars)."""
    name = name[:7]
    all_codes = ""
    for ch in name:
        h = ch.encode("gbk", errors="ignore").hex()
        if len(h) < 4:
            h = (h + "0000")[:4]
        all_codes += h
    return (all_codes + "0" * 28)[:28]

def decode_menu_gbk(hex_str: str) -> str:
    """Decode recipe name from menu property returned by device."""
    if not hex_str or len(hex_str) < 16:
        return "未知"
    try:
        # Menu payload usually starts with 4-char prefix e.g. 01ff, followed by GBK hex name
        # padded with 00
        raw = hex_str[4:] if len(hex_str) > 28 else hex_str
        # Strip trailing 00s and non-text bytes
        cleaned = ""
        for i in range(0, len(raw), 2):
            byte_hex = raw[i:i+2]
            if byte_hex == "00":
                break
            cleaned += byte_hex
        if cleaned:
            return bytes.fromhex(cleaned).decode("gbk", errors="ignore").strip()
    except Exception:
        pass
    return "自定义模式"


ALL_TASTE_NAMES = [
    "绵软", "酥软", "软糯", "香浓", "浓稠", "适中", "嚼劲", "劲道", "紧实", "清亮", "弹润", "弹嫩", "清鲜"
]


def calc_crc16_chunmi(data: bytearray, count: int) -> int:
    """Calculate CRC-16-CCITT checksum for Chunmi CookProfile."""
    crc = 0
    for j in range(count):
        crc = crc ^ (data[j] << 8)
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def get_mode_taste_names(cook_code_hex: str) -> list:
    """Return the 3 taste names for given cook code."""
    try:
        b = bytes.fromhex(cook_code_hex)
        t0 = ALL_TASTE_NAMES[b[17]] if b[17] < len(ALL_TASTE_NAMES) else "偏软"
        t1 = ALL_TASTE_NAMES[b[18]] if b[18] < len(ALL_TASTE_NAMES) else "适中"
        t2 = ALL_TASTE_NAMES[b[19]] if b[19] < len(ALL_TASTE_NAMES) else "偏硬"
        if t0 == t1 == t2:
            return [t0]
        return [t0, t1, t2]
    except Exception:
        return ["软糯", "适中", "嚼劲"]


def _parse_pressure_time(b1: int, b2: int) -> int:
    if (b1 & 0xFF) == 0xFF or (b2 & 0xFF) == 0xFF:
        return 0xFF
    elif (b1 & 0x80) == 0x80:
        return b1 * 60 + b2
    else:
        return b1


def get_holding_duration_from_code(cook_code_hex: str, taste_idx: int = 1) -> int:
    """Calculate default holding pressure duration from code taste bytes."""
    try:
        b = bytes.fromhex(cook_code_hex)
        p1 = _parse_pressure_time(b[75], b[76])
        p2 = _parse_pressure_time(b[85], b[86])
        p3 = _parse_pressure_time(b[95], b[96])
        base_off = 156 + (taste_idx % 3) * 3
        t_times = [b[base_off], b[base_off + 1], b[base_off + 2]]
        dur = 0
        dur += t_times[0] if p1 == 0xFF else p1
        dur += t_times[1] if p2 == 0xFF else p2
        dur += t_times[2] if p3 == 0xFF else p3
        return dur
    except Exception:
        return 15


def get_mode_base_overhead(cook_code_hex: str) -> int:
    """Return fixed heating/exhausting overhead in minutes."""
    try:
        b = bytes.fromhex(cook_code_hex)
        recipe_id = (b[3] << 24) | (b[4] << 16) | (b[5] << 8) | b[6]
        if recipe_id == 9:  # 开盖收汁
            return 0
        if recipe_id == 8:  # 保温
            return 1440
        return b[8] * 60 + b[9]
    except Exception:
        return 20


def get_mode_duration_limits(cook_code_hex: str) -> tuple:
    """Return (min_dur, max_dur, default_dur) in minutes for holding pressure."""
    try:
        b = bytes.fromhex(cook_code_hex)
        d_min = b[12] * 60 + b[13]
        d_max = b[10] * 60 + b[11]
        d_def = get_holding_duration_from_code(cook_code_hex, taste_idx=1)
        if d_min <= 0:
            d_min = 1
        if d_max < d_min:
            d_max = max(d_min, d_def)
        if d_def < d_min:
            d_def = d_min
        elif d_def > d_max:
            d_def = d_max
        return (d_min, d_max, d_def)
    except Exception:
        return (5, 60, 20)


def get_mode_total_estimated_time(cook_code_hex: str, duration: int = None) -> int:
    """Return total estimated cooking duration in minutes (overhead + holding)."""
    try:
        b = bytes.fromhex(cook_code_hex)
        recipe_id = (b[3] << 24) | (b[4] << 16) | (b[5] << 8) | b[6]
        if recipe_id == 8:  # 保温
            return 1440
        overhead = get_mode_base_overhead(cook_code_hex)
        if duration is not None:
            holding = duration
        else:
            _, _, holding = get_mode_duration_limits(cook_code_hex)
        return overhead + holding
    except Exception:
        return 40


def customize_cook_code(
    base_hex: str,
    taste_index: int = None,
    duration: int = None,
) -> str:
    """Modify taste and/or holding pressure duration of a base cook code."""
    data = bytearray(bytes.fromhex(base_hex))

    if taste_index is not None and 0 <= taste_index <= 2:
        data[150] = taste_index

    if duration is not None and duration > 0:
        def _get_pressure_time(b1: int, b2: int) -> int:
            if (b1 & 0xFF) == 0xFF or (b2 & 0xFF) == 0xFF:
                return 0xFF
            elif (b1 & 0x80) == 0x80:
                return b1 * 60 + b2
            else:
                return b1

        t1 = _get_pressure_time(data[75], data[76])
        t2 = _get_pressure_time(data[85], data[86])
        t3 = _get_pressure_time(data[95], data[96])

        # Stage 0
        if (data[75] & 0xFF) == 0xFF or (data[76] & 0xFF) == 0xFF:
            val = duration
            if t2 != 0xFF:
                val -= t2
            if t3 != 0xFF:
                val -= t3
            val = max(0, min(255, val))
            data[156] = val
            data[159] = val
            data[162] = val

        # Stage 1
        if (data[85] & 0xFF) == 0xFF or (data[86] & 0xFF) == 0xFF:
            val = duration
            if t1 != 0xFF:
                val -= t1
            if t3 != 0xFF:
                val -= t3
            val = max(0, min(255, val))
            data[157] = val
            data[160] = val
            data[163] = val

        # Stage 2
        if (data[95] & 0xFF) == 0xFF or (data[96] & 0xFF) == 0xFF:
            val = duration
            if t1 != 0xFF:
                val -= t1
            if t2 != 0xFF:
                val -= t2
            val = max(0, min(255, val))
            data[158] = val
            data[161] = val
            data[164] = val

    # Recalculate CRC16 across data[0..len-3]
    crc = calc_crc16_chunmi(data, len(data) - 2)
    data[-2] = (crc >> 8) & 0xFF
    data[-1] = crc & 0xFF
    return data.hex()


from .recipes import ALL_RECIPES

# Presets & Cloud recipes extracted directly from Chunmi / Joyami Cloud for chunmi.pre_cooker.eh1
PRESET_COOK_MODES = ALL_RECIPES

ALL_MODES_ESTIMATED_TIME_CACHE = {
    name: "持续恒温" if name == "保温" else f"约 {get_mode_total_estimated_time(p['cook_code'])} 分钟"
    for name, p in PRESET_COOK_MODES.items()
}


STATUS_MAP = {
    1: "待机",
    2: "烹饪中",
    3: "预约中",
    4: "保温中",
    5: "暂停中",
    10: "待机",
}

PHASE_MAP = {
    0: "就绪",
    1: "预热升压",
    2: "高压保压",
    3: "降压排气",
    4: "收汁熟化",
    5: "保温",
}
