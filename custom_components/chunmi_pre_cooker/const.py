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


RECIPES_ZH_TO_SLUG = {
    '大米饭': 'white_rice',
    '标准煮饭': 'standard_rice',
    '极速煮饭': 'quick_rice',
    '杂粮饭': 'multigrain_rice',
    '热米饭': 'reheat_rice',
    '开盖收汁': 'open_lid_saute',
    '保温': 'keep_warm',
    '再加热': 'reheat',
    '红烧肉': 'braised_pork_belly',
    '红烧排骨': 'braised_ribs',
    '糖醋排骨': 'sweet_sour_ribs',
    '豆豉蒸排骨': 'steamed_ribs_black_bean',
    '糯米蒸排骨': 'steamed_ribs_sticky_rice',
    '土豆炖排骨': 'stewed_ribs_potatoes',
    '精炖猪肉': 'braised_pork',
    '无水焗排骨': 'waterless_baked_ribs',
    '无水焗鸡': 'waterless_baked_chicken',
    '无水焗牛羊': 'waterless_baked_beef_lamb',
    '黄焖鸡': 'braised_chicken_huangmen',
    '小鸡炖蘑菇': 'chicken_stew_mushrooms',
    '香菇蒸鸡': 'steamed_chicken_mushrooms',
    '鲜炖鸡鸭': 'braised_poultry',
    '红烧鸡爪': 'braised_chicken_feet',
    '板栗焖鸡': 'braised_chicken_chestnuts',
    '啤酒鸭': 'beer_duck',
    '盐水鸭': 'salted_duck',
    '酱鸭腿': 'soy_sauce_duck_legs',
    '香辣卤鸭脖': 'spicy_duck_necks',
    '卤鸭掌鸭翅': 'braised_duck_feet_wings',
    '眉豆煲鸡爪': 'chicken_feet_soup_beans',
    '土豆炖牛肉': 'beef_stew_potatoes',
    '番茄牛腩': 'beef_brisket_tomatoes',
    '红烩牛肉': 'braised_beef_stew',
    '卤牛腱': 'spiced_beef_shank',
    '炖牛筋': 'stewed_beef_tendon',
    '酱牛骨头': 'braised_beef_bones',
    '焖炖牛羊': 'braised_beef_mutton',
    '手抓羊肉': 'boiled_lamb_chops',
    '枝竹羊腩煲': 'lamb_brisket_casserole',
    '萝卜焖羊肉': 'lamb_stew_radish',
    '酱羊蝎子': 'braised_lamb_spine',
    '冰糖肘子': 'rock_sugar_pork_shank',
    '梅干菜烧肉': 'braised_pork_preserved_mustard',
    '酸菜炖棒骨': 'pork_bones_sauerkraut',
    '酱棒骨': 'soy_braised_pork_bones',
    '粉蒸肉': 'steamed_pork_rice_flour',
    '红烧猪蹄': 'braised_pork_trotters',
    '黄豆炖猪蹄': 'trotters_stew_soybeans',
    '南乳焖猪手': 'trotters_fermented_tofu',
    '水晶肉皮冻': 'crystal_pork_skin_jelly',
    '豆类蹄筋': 'beans_and_tendons',
    '浓香煲汤': 'rich_soup',
    '花胶鸡汤': 'fish_maw_chicken_soup',
    '老母鸡汤': 'hen_soup',
    '乌鸡虫草花': 'silkie_chicken_cordyceps',
    '人参鸡汤': 'ginseng_chicken_soup',
    '猪肚鸡汤': 'pork_stomach_chicken_soup',
    '乳鸽汤': 'pigeon_soup',
    '笋干老鸭汤': 'duck_soup_dried_bamboo',
    '酸萝卜鸭汤': 'duck_soup_pickled_radish',
    '玉竹老鸭汤': 'duck_soup_solomonseal',
    '当归羊肉汤': 'mutton_soup_angelica',
    '牛尾清汤': 'clear_oxtail_soup',
    '萝卜牛腩汤': 'beef_brisket_radish_soup',
    '玉米排骨汤': 'ribs_soup_sweet_corn',
    '海带排骨汤': 'ribs_soup_kelp',
    '薏米排骨汤': 'ribs_soup_barley',
    '干贝排骨汤': 'ribs_soup_scallop',
    '海底椰骨汤': 'pork_bone_soup_sea_coconut',
    '腌笃鲜': 'yan_du_xian_soup',
    '肉骨茶': 'bak_kut_teh',
    '罗宋汤': 'borscht',
    '韩式土豆汤': 'korean_gamjatang',
    '凤梨苦瓜汤': 'pineapple_bitter_melon_soup',
    '煲仔饭': 'claypot_rice',
    '上海菜饭': 'shanghai_vegetable_rice',
    '羊肉手抓饭': 'lamb_pilaf',
    '牛肉焖饭': 'beef_braised_rice',
    '腊味糯米饭': 'cured_meat_sticky_rice',
    '红豆饭': 'red_bean_rice',
    '皮蛋瘦肉粥': 'congee_preserved_egg_pork',
    '杂粮米粥': 'multigrain_congee',
    '美龄粥': 'meiling_congee',
    '瑶柱排骨粥': 'ribs_congee_scallop',
    '四红粥': 'four_red_congee',
    '花生黑米粥': 'peanut_black_rice_congee',
    '南瓜小米粥': 'pumpkin_millet_congee',
    '小米粥': 'millet_congee',
    '八宝粥': 'eight_treasure_congee',
    '咸蛋黄肉粽': 'salted_egg_pork_zongzi',
    '紫米蜜枣粽子': 'purple_rice_date_zongzi',
    '银耳雪梨': 'snow_pear_white_fungus',
    '木瓜银耳羹': 'papaya_white_fungus_soup',
    '银耳莲子羹': 'white_fungus_lotus_seed_soup',
    '桃胶皂角米': 'peach_gum_snow_lotus_seeds',
    '桂花糖藕': 'sweet_osmanthus_lotus_root',
    '绿豆酿藕节': 'mung_bean_stuffed_lotus_root',
    '冰糖绿豆汤': 'sweet_mung_bean_soup',
    '绿豆汤': 'mung_bean_soup',
    '绿豆莲子汤': 'mung_bean_lotus_seed_soup',
    '陈皮红豆汤': 'tangerine_peel_red_bean_soup',
    '红豆薏米水': 'red_bean_barley_drink',
    '柠檬薏米水': 'lemon_barley_water',
    '燕麦牛奶': 'oatmeal_milk',
    '芒果捞黑米': 'mango_black_rice_dessert',
    '话梅芸豆': 'preserved_plum_kidney_beans',
    '蒸红薯': 'steamed_sweet_potatoes',
    '土豆泥': 'mashed_potatoes'
}

RECIPES_SLUG_TO_ZH = {v: k for k, v in RECIPES_ZH_TO_SLUG.items()}

ALL_RECIPE_SLUGS = list(RECIPES_ZH_TO_SLUG.values())

TASTES_ZH_TO_SLUG = {
    '绵软': 'soft_fluffy',
    '酥软': 'tender',
    '软糯': 'soft_glutinous',
    '香浓': 'rich_fragrant',
    '浓稠': 'thick',
    '适中': 'standard',
    '嚼劲': 'chewy',
    '劲道': 'firm',
    '紧实': 'compact',
    '清亮': 'clear',
    '弹润': 'springy',
    '弹嫩': 'tender_springy',
    '清鲜': 'fresh',
}

TASTES_SLUG_TO_ZH = {v: k for k, v in TASTES_ZH_TO_SLUG.items()}


def resolve_mode_name(mode_or_slug: str) -> str:
    """Return Chinese mode name given Chinese name or English slug."""
    if not mode_or_slug:
        return '大米饭'
    if mode_or_slug in RECIPES_SLUG_TO_ZH:
        return RECIPES_SLUG_TO_ZH[mode_or_slug]
    if mode_or_slug in PRESET_COOK_MODES:
        return mode_or_slug
    return mode_or_slug


def resolve_mode_slug(mode_or_slug: str) -> str:
    """Return English slug given Chinese name or English slug."""
    if not mode_or_slug:
        return 'white_rice'
    if mode_or_slug in RECIPES_ZH_TO_SLUG:
        return RECIPES_ZH_TO_SLUG[mode_or_slug]
    if mode_or_slug in RECIPES_SLUG_TO_ZH:
        return mode_or_slug
    return 'white_rice'


def resolve_taste_zh(taste_or_slug: str) -> str:
    """Return Chinese taste name given slug or Chinese name."""
    if taste_or_slug in TASTES_SLUG_TO_ZH:
        return TASTES_SLUG_TO_ZH[taste_or_slug]
    return taste_or_slug


def resolve_taste_slug(taste_or_slug: str) -> str:
    """Return taste slug given slug or Chinese name."""
    if taste_or_slug in TASTES_ZH_TO_SLUG:
        return TASTES_ZH_TO_SLUG[taste_or_slug]
    return taste_or_slug


STATUS_MAP_SLUG = {
    1: 'standby',
    2: 'cooking',
    3: 'keep_warm',
    4: 'delayed',
    5: 'paused',
    10: 'standby',
}

STATUS_MAP_ZH = {
    1: '待机',
    2: '烹饪中',
    3: '保温中',
    4: '预约中',
    5: '暂停中',
    10: '待机',
}

PHASE_MAP_SLUG = {
    0: 'idle',
    1: 'preheating',
    2: 'waiting_lock',
    3: 'pressurizing',
    4: 'holding_pressure',
    5: 'depressurizing',
    6: 'keep_warm',
    7: 'completed',
    8: 'pressure_relief_open',
    9: 'waiting_open',
    10: 'adding_ingredients',
    11: 'waiting_continue',
}

PHASE_MAP_ZH = {
    0: '空闲',
    1: '升温预热',
    2: '等待锁盖',
    3: '加压升压',
    4: '高压保压',
    5: '降压排气',
    6: '保温中',
    7: '已完成',
    8: '泄压开盖',
    9: '待开盖',
    10: '中途添料',
    11: '待继续',
}

STATUS_MAP = STATUS_MAP_ZH
PHASE_MAP = PHASE_MAP_ZH

