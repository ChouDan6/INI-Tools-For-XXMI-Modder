"""XXMI utility functions for parsing and transforming XXMI exports."""

import bpy
import hashlib
from typing import List, Dict, Tuple

from .config import ACTIVE_VARIABLE
from .utils import (
    extract_name_index,
    standardize_var_name,
    is_section_header,
    extract_section_name,
    is_comment,
    is_drawindexed
)


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


def transform_xxmi_to_conditionals(ini_content: List[str], component_variables: dict, report_func=None) -> List[str]:
    static_draws = parse_static_drawindexed(ini_content, report_func)
    variable_groups = group_by_variables(static_draws, component_variables, report_func)
    result = replace_with_conditionals(ini_content, variable_groups, report_func)
    return result


def parse_static_drawindexed(ini_content: List[str], report_func=None) -> Dict[str, List[Tuple[str, str, str]]]:
    static_draws: Dict[str, List[Tuple[str, str, str]]] = {}
    current_section = None
    i = 0
    while i < len(ini_content):
        line = ini_content[i].strip()
        if is_section_header(line):
            current_section = extract_section_name(line)
            i += 1
            continue

        if is_comment(line) and current_section:
            comment = line
            mesh_name = extract_mesh_name_from_comment(comment)

            if i + 1 < len(ini_content):
                next_line = ini_content[i + 1].strip()
                if is_drawindexed(next_line):
                    drawindexed_value = next_line.split('=', 1)[1].strip()
                    static_draws.setdefault(current_section, []).append(
                        (comment, mesh_name, drawindexed_value)
                    )
                    i += 2
                    continue
        i += 1
    return static_draws


def extract_mesh_name_from_comment(comment: str) -> str:
    comment_text = comment[1:].strip()
    parts = comment_text.split('(')
    if len(parts) >= 2:
        last_part = parts[-1]
        if last_part.replace(')', '').strip().isdigit():
            mesh_name = '('.join(parts[:-1]).strip()
            return mesh_name
    mesh_name = comment_text.split('(')[0].strip()
    return mesh_name


def group_by_variables(static_draws: Dict[str, List[Tuple[str, str, str]]], 
                      component_variables: dict, report_func=None) -> Dict[str, Dict]:
    variable_groups = {}
    
    for section_name, draws_list in static_draws.items():
        section_vars = {}
        for comment, mesh_name, drawindexed_value in draws_list:
            base_name, index = extract_name_index(mesh_name)
            if not base_name:
                continue
                
            raw_var_name = standardize_var_name(base_name)
            var_name = sanitize_to_ascii(raw_var_name)
            
            variable_exists_in_scene = False
            for component_name, component_vars in component_variables.items():
                if var_name in component_vars:
                    variable_exists_in_scene = True
                    break
            
            if not variable_exists_in_scene:
                continue
            
            option = max(0, (index - 1)) if index is not None else 0
            
            if var_name not in section_vars:
                section_vars[var_name] = {}
            if option not in section_vars[var_name]:
                section_vars[var_name][option] = []
            
            section_vars[var_name][option].append({
                'comment': comment,
                'mesh_name': mesh_name,
                'drawindexed': drawindexed_value
            })
        
        if section_vars:
            variable_groups[section_name] = section_vars
    
    return variable_groups


def replace_with_conditionals(ini_content: List[str], variable_groups: Dict[str, Dict], report_func=None) -> List[str]:
    result = []
    i = 0
    while i < len(ini_content):
        line = ini_content[i]
        if is_section_header(line.strip()):
            section_name = extract_section_name(line.strip())
            result.append(line)
            if section_name in variable_groups:
                i = process_section_with_conditionals(
                    ini_content, i, section_name,
                    variable_groups[section_name], result, report_func
                )
            else:
                i += 1
        else:
            result.append(line)
            i += 1
    return result


def process_section_with_conditionals(ini_content: List[str], start_idx: int, section_name: str,
                                      section_vars: Dict, result: List[str], report_func=None) -> int:
    i = start_idx + 1
    active_inserted = False

    while i < len(ini_content):
        line = ini_content[i]
        stripped = line.strip()

        if is_section_header(stripped): break
        if is_comment(stripped) and ('---' in stripped or 'CommandList' in stripped or 'Resources' in stripped): break

        if is_comment(stripped):
            mesh_name = extract_mesh_name_from_comment(stripped)
            should_skip = any(
                mesh_data['mesh_name'] == mesh_name
                for options in section_vars.values()
                for meshes in options.values()
                for mesh_data in meshes
            )
            if should_skip:
                if i + 1 < len(ini_content) and is_drawindexed(ini_content[i + 1].strip()):
                    i += 2
                else:
                    i += 1
                continue

        if not active_inserted and stripped and not is_comment(stripped) and not is_section_header(stripped):
            if section_vars:
                result.append(f"{ACTIVE_VARIABLE} = 1\n")
                active_inserted = True

        result.append(line)
        i += 1

    add_conditional_blocks(section_vars, result, report_func)
    return i


def add_conditional_blocks(section_vars: Dict, result: List[str], report_func=None):
    for var_name, options in section_vars.items():
        sorted_options = sorted(options.items())
        for idx, (option, meshes) in enumerate(sorted_options):
            prefix = "if" if idx == 0 else "else if"
            result.append(f"{prefix} ${var_name} == {option}\n")
            for mesh_data in meshes:
                result.append(f"    {mesh_data['comment']}\n")
                result.append(f"    drawindexed = {mesh_data['drawindexed']}\n")
        result.append("endif\n\n")
    
    if section_vars and result and result[-1] == "\n":
        result.pop()
