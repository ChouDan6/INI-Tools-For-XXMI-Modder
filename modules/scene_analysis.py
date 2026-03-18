"""Scene analysis utilities for INI Tools addon."""

import bpy
import hashlib
from typing import Dict, List, Tuple
from .config import CONTAINERS_COLLECTION, ACTIVE_VARIABLE
from .utils import natural_sort_key, get_container_name, standardize_var_name, extract_name_index, capitalize_var_name


def sanitize_to_ascii(text: str) -> str:
    """
    智能中英文变量转换。
    优先尝试 pypinyin，失败则使用内置高频词典，最后回退安全 Hash。
    """
    style = 'PINYIN'
    try:
        for addon_name, addon in bpy.context.preferences.addons.items():
            if hasattr(addon.preferences, "naming_style"):
                style = addon.preferences.naming_style
                break
    except Exception:
        pass

    ascii_prefix = "".join([c for c in text if c.isascii() and (c.isalnum() or c == '_')])
    if len(ascii_prefix) == len(text) and ascii_prefix != "":
        if ascii_prefix[0].isdigit():
            ascii_prefix = "v_" + ascii_prefix
        return ascii_prefix

    if style == 'PINYIN':
        try:
            from pypinyin import lazy_pinyin
            pinyin_list = lazy_pinyin(text)
            res = "".join([word for word in pinyin_list if word.isalnum() or word == '_'])
            if not res: res = "var"
            elif res[0].isdigit(): res = "v_" + res
            return res
        except ImportError:
            # 内置高频词典（无需额外库）
            pinyin_map = {
                '内': 'nei', '衣': 'yi', '手': 'shou', '头': 'tou', '体': 'ti',
                '脚': 'jiao', '腿': 'tui', '鞋': 'xie', '脸': 'lian', '发': 'fa',
                '身': 'shen', '臂': 'bi', '裙': 'qun', '裤': 'ku', '饰': 'shi',
                '左': 'l', '右': 'r', '胸': 'xiong', '背': 'bei', '腰': 'yao',
                '眼': 'yan', '嘴': 'zui', '角': 'jiao', '外': 'wai', '上': 'shang',
                '下': 'xia', '前': 'qian', '后': 'hou', '环': 'huan', '套': 'tao'
            }
            res = ""
            for char in text:
                if '\u4e00' <= char <= '\u9fff':
                    if char in pinyin_map:
                        res += pinyin_map[char]
                    else:
                        res += f"u{ord(char):04x}"
                elif char.isascii() and (char.isalnum() or char == '_'):
                    res += char
            if not res: res = "var"
            elif res[0].isdigit(): res = "v_" + res
            return res

    hash_str = hashlib.md5(text.encode('utf-8')).hexdigest()[:6]
    return f"v_{hash_str}" if not ascii_prefix else f"{ascii_prefix}_{hash_str}"


def collect_scene_variables() -> tuple[dict, dict, dict]:
    toggle_variables: dict[str, set[int]] = {}
    index_mappings: dict[str, dict[int, int]] = {}
    component_variables: dict[str, dict[str, dict[int, list[bpy.types.Object]]]] = {}

    containers_collection = bpy.data.collections.get(CONTAINERS_COLLECTION)
    if not containers_collection:
        raise RuntimeError(f"错误: 场景中未找到 '{CONTAINERS_COLLECTION}' 集合。")

    component_collections = [
        coll for coll in bpy.data.collections
        if coll.name != "Containers" and coll.objects
    ]

    for component_coll in component_collections:
        component_name = component_coll.name
        component_variables[component_name] = {}

        for mesh_obj in component_coll.objects:
            if mesh_obj.type != 'MESH' or mesh_obj.hide_get():
                continue

            base_name, index = extract_name_index(mesh_obj.name)
            raw_var_name = standardize_var_name(base_name)
            var_name = sanitize_to_ascii(raw_var_name)

            if var_name not in toggle_variables:
                toggle_variables[var_name] = set()
                index_mappings[var_name] = {}

            option = index if index is not None else 0
            toggle_variables[var_name].add(option)

            if option not in index_mappings[var_name]:
                new_index = len(index_mappings[var_name])
                index_mappings[var_name][option] = new_index

            if var_name not in component_variables[component_name]:
                component_variables[component_name][var_name] = {}
                
            mapped_option = index_mappings[var_name][option]
            component_variables[component_name][var_name].setdefault(mapped_option, []).append(mesh_obj)

    for var_name in toggle_variables:
        mapped_indices = sorted(index_mappings[var_name].values())
        if len(mapped_indices) == 1:
            mapped_indices = [0, 1]
        toggle_variables[var_name] = mapped_indices

    return toggle_variables, index_mappings, component_variables


def format_key_string(key_str: str) -> str:
    key_str = key_str.strip()
    parts = key_str.split()
    
    has_ctrl = any("ctrl" in part.lower() for part in parts)
    has_alt = any("alt" in part.lower() for part in parts)
    has_shift = any("shift" in part.lower() for part in parts)
    
    prefix = ""
    if not has_ctrl: prefix += "no_ctrl "
    if not has_alt: prefix += "no_alt "
    if not has_shift: prefix += "no_shift "
        
    return prefix + key_str


def build_key_sections(
    toggle_variables: dict,
    keys_list: list,
    report_func,
) -> tuple[list[str], list[str], list[str]]:
    constants_section = ["; =======================================\n", "; Variables\n"]
    
    for var_name, options in toggle_variables.items():
        default_value = options[0]
        variable_line = f"global persist ${var_name} = {default_value}\n"
        constants_section.append(variable_line)
    
    constants_section.append("\n")
    present_section = ["\n[Present]\n", f"post {ACTIVE_VARIABLE} = 0\n\n"]

    key_swap_sections: list[str] = []
    keys_assigned = 0
    for var_name in toggle_variables.keys():
        capitalized_name = capitalize_var_name(var_name)
        key_swap_sections.append(f"[KeySwap{capitalized_name}]\n")
        
        if keys_assigned < len(keys_list):
            raw_key = keys_list[keys_assigned]
            keys_assigned += 1
            formatted_key = format_key_string(raw_key)
            key_swap_sections.append(f"key = {formatted_key}\n")
        else:
            report_func({'WARNING'}, f"变量 '{var_name}' 的按键不足。请手动��配一个按键。")
            key_swap_sections.append("; 请替换为实际的按键\n")
            formatted_key = format_key_string("REPLACE")
            key_swap_sections.append(f"key = {formatted_key}\n")
            
        key_swap_sections.append(f"condition = {ACTIVE_VARIABLE} == 1\n")
        key_swap_sections.append("type = cycle\n")
        opts = ",".join(map(str, toggle_variables[var_name]))
        key_swap_sections.append(f"${var_name} = {opts}\n\n")

    return constants_section, present_section, key_swap_sections