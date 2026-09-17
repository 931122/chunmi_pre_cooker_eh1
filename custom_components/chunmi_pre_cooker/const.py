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
    """Encode recipe name to 28-char GBK hex format used by Chunmi."""
    name = name[:5]
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


def get_mode_duration_limits(cook_code_hex: str) -> tuple:
    """Return (min_dur, max_dur, default_dur) in minutes."""
    try:
        b = bytes.fromhex(cook_code_hex)
        d_min = b[12] * 60 + b[13]
        d_max = b[10] * 60 + b[11]
        d_def = b[8] * 60 + b[9]
        if d_min <= 0:
            d_min = 1
        if d_max < d_min:
            d_max = max(d_min, d_def)
        if d_def < d_min or d_def > d_max:
            d_def = d_min
        return (d_min, d_max, d_def)
    except Exception:
        return (5, 60, 20)


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


# Presets extracted directly from Chunmi / Joyami Cloud for chunmi.pre_cooker.eh1
PRESET_COOK_MODES = {
    "杂粮饭": {
        "name": "杂粮饭",
        "recipe_id": 2208,
        "duration": 15,
        "slot": 1,
        "description": "米家电压力锅预设：杂粮饭",
        "name_gbk": encode_name_gbk("杂粮饭"),
        "cook_code": "020101000008a0e4000f0019000a00800102050a140000000004009182321800000001230091507320000000010100915a7d003205c8010d00966673ff3205ff000a00ffff91ff3205ff00ffffff8273ff3205ff00030091827d0000000000000091827d00000000021e0091827d00ffff0000000091827d000000000700180c7d0c910c0a001a0a800c910c32001c0a860c910c732001ff1e1e2d3c0c00000c00000c0000000000000000000000b748",
    },
    "大米饭": {
        "name": "大米饭",
        "recipe_id": 7694,
        "duration": 15,
        "slot": 2,
        "description": "米家电压力锅预设：大米饭",
        "name_gbk": encode_name_gbk("大米饭"),
        "cook_code": "02010200001e0ee4001e0019000600800102050a1400000000040091823218000000012300af507d20000000010100915a7d003205c8010d00af667dff3205ff000a00ffff91ff3205ff00ffffff8273ff3205ff00000091827d0000000000000091827d00000000020a0091827d00ffff0000000091827d000000000700180c7d0691060a001a0a8009910932001c0a86099109732002ff1e1e2d3c0f00000f00000f0000000000000000000000baaa",
    },
    "焖炖牛羊": {
        "name": "焖炖牛羊",
        "recipe_id": 2,
        "duration": 60,
        "slot": 3,
        "description": "米家电压力锅预设：焖炖牛羊",
        "name_gbk": encode_name_gbk("焖炖牛羊"),
        "cook_code": "02010300000002e100190100000f0080010105060a00000000000591827d00000000012000914b7d20000000010100915a7d003205c8011e00916678ff3205ff00050091ff73ff3205ff000a00918273ff3205ff80ffff9182730a050fc88000009182730a3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f002012910c910c732001ff1e28323c001900001900001900000000000000000000de0e",
    },
    "土豆炖排骨": {
        "name": "土豆炖排骨",
        "recipe_id": 2309,
        "duration": 20,
        "slot": 4,
        "description": "米家电压力锅预设：土豆炖排骨",
        "name_gbk": encode_name_gbk("土豆炖排骨"),
        "cook_code": "02010400000905e20014001e000a0080010105061400000000000591827d00000000012100914b7d20000000010100915a7d003205c8011e00916678ff3205ff000a0091ff73ff3205ff000500918273ff3205ff00ffff9182730a0a0fc8000000918273ff3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f001812910c910c732001ff1e28323c000f00000f00000f00000000000000000005dfd9",
    },
    "杂粮米粥": {
        "name": "杂粮米粥",
        "recipe_id": 6,
        "duration": 60,
        "slot": 5,
        "description": "米家电压力锅预设：杂粮米粥",
        "name_gbk": encode_name_gbk("杂粮米粥"),
        "cook_code": "02010500000006e500210100000a0080010205061400000000000591827d00000000012400914b7d20000000010100915a7d003205c8011e00916578ff030fc8000a0091ff73ff0332c800ffff918273ff32050000000091827300050f000005009182730032050002230091826e00ffff0000000091826e0000000005000e0c910c91080a00100e910a910a0f001210910c910c732001ff1e28323c0c00000c00000c0000000000000000000000f0d8",
    },
    "番茄牛腩": {
        "name": "番茄牛腩",
        "recipe_id": 2009,
        "duration": 45,
        "slot": 6,
        "description": "米家电压力锅预设：番茄牛腩",
        "name_gbk": encode_name_gbk("番茄牛腩"),
        "cook_code": "020106000007d9e1002d010000230080010105061400000000000591827d00000000012000914b7d20000000010100915a7d003205c8011e00916678ff3205ff00050091ff73ff3205ff000a00918273ff3205ff00ffff9182730a050fc80000009182730a3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f002012910c910c732001ff1e28323c00230000230000230000000000000000000588d1",
    },
    "保温": {
        "name": "保温",
        "recipe_id": 8,
        "duration": 0,
        "slot": 7,
        "description": "米家电压力锅预设：保温",
        "name_gbk": encode_name_gbk("保温"),
        "cook_code": "02010700000008071800000000000080010000000000000000000591827d00000000002500913c7d20000000000100915a7d003205c8000a0091647dff0a05c8000a0091ff7dff3205ff00000091827dff3205ff00000091827d00050fc800000091827d003205ff00001e91826e000505c800000091826e000000000073120e780c780c00af18107d0e7d0e011918127d127d12732001ff1e141e280a0c0a0a0c0a0a0c0a0000000000000000001f48",
    },
    "开盖收汁": {
        "name": "开盖收汁",
        "recipe_id": 9,
        "duration": 10,
        "slot": 9,
        "description": "米家电压力锅预设：开盖收汁",
        "name_gbk": encode_name_gbk("开盖收汁"),
        "cook_code": "030109000000090802000100000500800103050c0000000000000091827d00000000000000913c7d20000000000000915a7d003205c8000000916578ff3205ff00000091ff73ff3205ff00ffff91827d203205a000000091827d103205a000000091827d0a3205a000000091826e0000000000000091826e000503c80073120e910c910c00af1810910e910e0119181291109110732001ff1e1e1e280f00000f00000f0000000000000000000000922c",
    },
    "浓香煲汤": {
        "name": "浓香煲汤",
        "recipe_id": 7,
        "duration": 60,
        "slot": 9,
        "description": "米家电压力锅预设：浓香煲汤",
        "name_gbk": encode_name_gbk("浓香煲汤"),
        "cook_code": "02010900000007e600190100000a00800103050c0f00000000000591827d00000000012500914b7d20000000010100915a7d003205c8011e00916578ff3205ff000a0091ff73ff3205ff000500918273ff3205ff80ffff9182730a050fc8800000918273ff3205ff021e0091826e00ffff0000000091826e000000000300120e910c910c08001810910e910e0f00181291109110732001ff1e1e2328001900001900001900000000000000000000186c",
    },
    "精炖猪肉": {
        "name": "精炖猪肉",
        "recipe_id": 3,
        "duration": 60,
        "slot": 9,
        "description": "米家电压力锅预设：精炖猪肉",
        "name_gbk": encode_name_gbk("精炖猪肉"),
        "cook_code": "02010900000003e200140100000f0080010105060f00000000000591827d00000000012100914b7d20000000010100915a7d003205c8011e00916678ff3205ff000a0091ff73ff3205ff000a00918273ff3205ff80ffff9182730a050fc8800000918273ff3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f001812910c910c732001ff1e232832000f00000f00000f00000000000000000000a22b",
    },
    "热米饭": {
        "name": "热米饭",
        "recipe_id": 10,
        "duration": 27,
        "slot": 9,
        "description": "米家电压力锅预设：热米饭",
        "name_gbk": encode_name_gbk("热米饭"),
        "cook_code": "0201090000000a24001b0003000300800102050a0055000000000091823200000000000f00af467318000000000a009150730c3205c8000000af6669063205ff000000ffff91ff3205ff000000916669063205ff00000091826906000000000300916673063205ff02000091827d00ffff0000000091827d000000000700180c7d0691060a001a0a8009910932001c0a86099109732001001e0000000f00000f00000f000000000000000000000043c5",
    },
    "标准煮饭": {
        "name": "标准煮饭",
        "recipe_id": 5,
        "duration": 15,
        "slot": 9,
        "description": "米家电压力锅预设：标准煮饭",
        "name_gbk": encode_name_gbk("标准煮饭"),
        "cook_code": "02010900000005e400140019000d00800102050a0f00000000040091823218000000012300af507d20000000010100915a7d003205c8010d00af667dff3205ff000a00ffff91ff3205ff00ffffff8273ff3205ff00000091827d0000000000000091827d00000000020a0091827d00ffff0000000091827d000000000700180c7d0691060a001a0a8009910932001c0a86099109732001ff1e1e2d3c0f00000f00000f0000000000000000000000c514",
    },
    "再加热": {
        "name": "再加热",
        "recipe_id": 11,
        "duration": 12,
        "slot": 9,
        "description": "米家电压力锅预设：再加热",
        "name_gbk": encode_name_gbk("再加热"),
        "cook_code": "0201090000000b21000c000800080080010105060055000000000591827d00000000012000914b7d14000000010100915a7d003205c8010000916678ff3205ff00000091ff73ff3205ff000000918273ff3205ff000800918269080a05c80000009182730a3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f002012910c910c622001ff1e28323c0000000000000000000000000000000000002e6c",
    },
    "豆类蹄筋": {
        "name": "豆类蹄筋",
        "recipe_id": 4,
        "duration": 60,
        "slot": 9,
        "description": "米家电压力锅预设：豆类蹄筋",
        "name_gbk": encode_name_gbk("豆类蹄筋"),
        "cook_code": "02010900000004e3001e0100000f0080010005060500000000000591827d00000000012200914b7d20000000010100915a7d003205c8011e00916678ff3205ff000a0091ff73ff3205ff00ffff918273ff32050800000091827300050f00000000918273003205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f001812910c910c732001ff1e2d3c4b28000028000028000000000000000000000a76da",
    },
    "鲜炖鸡鸭": {
        "name": "鲜炖鸡鸭",
        "recipe_id": 1,
        "duration": 30,
        "slot": 9,
        "description": "米家电压力锅预设：鲜炖鸡鸭",
        "name_gbk": encode_name_gbk("鲜炖鸡鸭"),
        "cook_code": "02010900000001e000190100000a0080010105081400000000000591827d00000000011f00914b7d20000000010100915a7d003205c8011e00916678ff3205ff00050091ff73ff3205ff000500918273ff3205ff80ffff9182730a050fc88000009182730a3205ff021e0091827d00ffff0000000091827d000000000300120e910c910c08001810910c910c0f002012910c910c732001ff1e1e2832000a00000a00000a0000000000000000000006f6",
    },
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
