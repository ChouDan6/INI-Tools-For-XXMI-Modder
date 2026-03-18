"""Core operation logic for INI Tools addon.

This module orchestrates the main operations (GENERATE, UPDATE, CLEAR).
Bridges scene analysis, INI processing, and XXMI utilities.
"""

import bpy
import os
import shutil
from typing import Dict, List
from .config import CONTAINERS_COLLECTION, ACTIVE_VARIABLE
from .scene_analysis import collect_scene_variables, build_key_sections
from .ini_processing import (
    parse_draw_lines,
    merge_draw_lines_into_content,
    collect_blend_draw_values,
    update_override_vertex_counts,
)
from .xxmi_utils import transform_xxmi_to_conditionals


def extract_filenames_from_ini(ini_filepath: str) -> List[str]:
    """Extract all .buf and .ib filenames referenced in INI Resource sections."""
    filenames = []
    with open(ini_filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            stripped = line.strip().lower()
            if stripped.startswith('filename ='):
                filename = line.split('=', 1)[1].strip()
                if filename.endswith(('.buf', '.ib')):
                    filenames.append(filename)
    return filenames


def copy_extra_files(ini_filepath: str, report_func) -> None:
    scene = bpy.context.scene
    xxmi_path = getattr(scene, "xxmi", None)
    if not xxmi_path or not hasattr(xxmi_path, "destination_path"):
        report_func({'WARNING'}, "未找到XXMI目标路径。跳过文件复制。")
        return

    source_folder = bpy.path.abspath(xxmi_path.destination_path)
    if not os.path.isdir(source_folder):
        report_func({'WARNING'}, f"源文件夹不存在: {source_folder}")
        return

    target_folder = os.path.dirname(ini_filepath)
    if not os.path.isdir(target_folder):
        report_func({'WARNING'}, f"目标文件夹不存在: {target_folder}")
        return

    required_files = extract_filenames_from_ini(ini_filepath)
    if not required_files:
        report_func({'INFO'}, "INI中未找到 .buf/.ib 文件。跳过文件复制。")
        return

    existing_bufib = {f for f in os.listdir(target_folder) if f.endswith(('.buf', '.ib'))}

    if existing_bufib:
        files_to_copy = [f for f in required_files if f in existing_bufib]
        if not files_to_copy:
            report_func({'INFO'}, "目标文件夹中没有匹配的文件需要更新。")
            return
    else:
        files_to_copy = required_files

    copied = 0
    for filename in files_to_copy:
        src = os.path.join(source_folder, filename)
        dst = os.path.join(target_folder, filename)
        if os.path.isfile(src):
            try:
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                report_func({'WARNING'}, f"复制 {filename} 失败: {e}")
        else:
            report_func({'INFO'}, f"在导出中未找到文件: {filename}")

    mode_desc = "选择性更新" if existing_bufib else "复制"
    report_func({'INFO'}, f"完成: {copied} 个文件已{mode_desc}。")


def execute_generate_mode(ini_filepath, ini_content, component_variables, report_func):
    ini_tools_generated = False
    for i, line in enumerate(ini_content):
        stripped = line.strip()
        if stripped.startswith('global persist $'):
            ini_tools_generated = True
            break
        if stripped == "; Variables" and i > 0 and "=======" in ini_content[i-1]:
            ini_tools_generated = True
            break
    
    if ini_tools_generated:
        report_func({'ERROR'}, "此INI已经包含切换工具的变量。请使用'更新现有INI'代替'生成切换'。")
        return {'CANCELLED'}
    
    try:
        toggle_variables, index_mappings, _ = collect_scene_variables()
    except RuntimeError as exc:
        report_func({'ERROR'}, str(exc))
        return {'CANCELLED'}
    
    prefs = bpy.context.preferences.addons[__package__.split('.')[0]].preferences
    keys_list = [k.strip() for k in prefs.toggle_keys.split(",") if k.strip()]
    
    constants_section, present_section, key_swap_sections = build_key_sections(
        toggle_variables, keys_list, report_func
    )
    
    constants_comment_index = None
    constants_section_index = None
    present_section_index = None
    
    for i, line in enumerate(ini_content):
        if line.strip().startswith("; Constants"):
            constants_comment_index = i
        elif line.strip() == "[Constants]":
            constants_section_index = i
        elif line.strip() == "[Present]":
            present_section_index = i
    
    if constants_section_index is not None:
        insert_pos = constants_section_index + 1
        while insert_pos < len(ini_content):
            line = ini_content[insert_pos].strip()
            if line.startswith('[') or (line.startswith(';') and '---' in line):
                break
            insert_pos += 1
        
        our_content = ["\n"] + constants_section
        if present_section_index is None:
            our_content.extend(present_section)
        our_content.extend(key_swap_sections)
        ini_content = ini_content[:insert_pos] + our_content + ini_content[insert_pos:]
        
    elif constants_comment_index is not None:
        insert_pos = constants_comment_index + 1
        while insert_pos < len(ini_content) and ini_content[insert_pos].strip() == "":
            insert_pos += 1
        
        full_content = ["\n[Constants]\n", f"global {ACTIVE_VARIABLE} = 0\n", "\n"] + constants_section
        if present_section_index is None:
            full_content.extend(present_section)
        full_content.extend(key_swap_sections)
        ini_content = ini_content[:insert_pos] + full_content + ini_content[insert_pos:]
        
    else:
        full_constants = ["\n[Constants]\n", f"global {ACTIVE_VARIABLE} = 0\n", "\n"] + constants_section
        if present_section_index is None:
            full_constants.extend(present_section)
        ini_content = full_constants + key_swap_sections + ini_content
    
    ini_content = transform_xxmi_to_conditionals(ini_content, component_variables, report_func)
    
    scene = bpy.context.scene
    if scene.copy_files:
        copy_extra_files(ini_filepath, report_func)
    
    with open(ini_filepath, 'w', encoding='utf-8') as f:
        f.writelines(ini_content)
    
    report_func({'INFO'}, "INI文件处理成功。")
    return {'FINISHED'}


def execute_update_mode(ini_filepath, ini_content, component_variables, report_func):
    has_ini_tools_variables = False
    for line in ini_content:
        stripped = line.strip()
        if stripped.startswith('global persist $'):
            has_ini_tools_variables = True
            break
    
    if not has_ini_tools_variables:
        report_func({'ERROR'}, "此文件还没有切换工具的变量。请先使用'生成切换'创建切换系统，然后再使用'更新现有INI'来更新 drawindexed 值。")
        return {'CANCELLED'}
    
    scene = bpy.context.scene
    
    destination_path = getattr(scene, "xxmi", None)
    if not destination_path or not hasattr(destination_path, "destination_path"):
        report_func({'ERROR'}, "未找到XXMI目标路径。没有XXMI导出无法更新。")
        return {'CANCELLED'}
    
    destination_path = destination_path.destination_path
    if not destination_path or not os.path.isdir(destination_path):
        report_func({'ERROR'}, "无效的XXMI目标路径。没有XXMI导出无法更新。")
        return {'CANCELLED'}
    
    exported_ini_file = None
    for filename in os.listdir(destination_path):
        if filename.lower().endswith(".ini"):
            exported_ini_file = os.path.join(destination_path, filename)
            break
    
    if not exported_ini_file or not os.path.isfile(exported_ini_file):
        report_func({'ERROR'}, "在XXMI目标路径中未找到 .ini 文件。没有XXMI导出无法更新。")
        return {'CANCELLED'}
    
    with open(exported_ini_file, "r", encoding="utf-8", errors="replace") as ef:
        exported_lines = ef.readlines()
    
    from .xxmi_utils import parse_static_drawindexed, extract_mesh_name_from_comment
    static_draws = parse_static_drawindexed(exported_lines, report_func)
    
    xxmi_mesh_map = {}
    for section_name, draws_list in static_draws.items():
        for comment, mesh_name, drawindexed_value in draws_list:
            xxmi_mesh_map[mesh_name] = drawindexed_value
    
    new_ini_content = []
    last_comment_text = None
    last_comment_line_index = None
    found_any_label = False
    updated_count = 0
    labeled_meshes_in_ini = set()

    for i, line in enumerate(ini_content):
        stripped = line.strip()

        if stripped.startswith(';'):
            comment = stripped.lstrip(';').strip()
            if comment:
                last_comment_text = stripped
                last_comment_line_index = i
            new_ini_content.append(line)
            continue

        if stripped.lower().startswith('drawindexed ='):
            if last_comment_line_index == i - 1 and last_comment_text:
                found_any_label = True
                mesh_name = extract_mesh_name_from_comment(last_comment_text)
                labeled_meshes_in_ini.add(mesh_name)

                if mesh_name in xxmi_mesh_map:
                    new_val = xxmi_mesh_map[mesh_name]
                    indent = line[:line.index('drawindexed')]
                    line = f"{indent}drawindexed = {new_val}\n"
                    updated_count += 1

            last_comment_text = None
            last_comment_line_index = None
            new_ini_content.append(line)
            continue

        new_ini_content.append(line)

    if found_any_label and updated_count == 0:
        report_func({'WARNING'}, "没有找到匹配的网格进行更新。文件结构没有改变。")
    elif not found_any_label:
        report_func({'ERROR'}, "未找到带标签的 drawindexed 条目。没有标签无法更新现有INI。")
        return {'CANCELLED'}

    new_meshes = []
    
    container_mesh_names = set()
    containers_collection = bpy.data.collections.get(CONTAINERS_COLLECTION)
    if containers_collection:
        for obj in containers_collection.objects:
            if obj.type == 'MESH':
                container_mesh_names.add(obj.name)
    
    for mesh_name, drawindexed_value in xxmi_mesh_map.items():
        if mesh_name not in labeled_meshes_in_ini:
            if mesh_name in container_mesh_names:
                continue
            new_meshes.append({
                'mesh_name': mesh_name,
                'drawindexed_line': drawindexed_value
            })

    deleted_meshes = []
    for mesh_name in labeled_meshes_in_ini:
        if mesh_name not in xxmi_mesh_map:
            deleted_meshes.append({'mesh_name': mesh_name})

    exported_draws = parse_draw_lines(exported_lines)
    new_ini_content = merge_draw_lines_into_content(exported_draws, new_ini_content)

    draw_values = collect_blend_draw_values(new_ini_content)
    new_ini_content = update_override_vertex_counts(new_ini_content, draw_values)

    if scene.copy_files:
        copy_extra_files(ini_filepath, report_func)
    
    with open(ini_filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_ini_content)
    
    report_func({'INFO'}, f"INI文件更新成功。已更新 {updated_count} 个 drawindexed 值。")
    return {
        'result': {'FINISHED'},
        'new_meshes': new_meshes,
        'deleted_meshes': deleted_meshes
    }


def execute_clear_mode(ini_filepath, report_func):
    """
    Clear all toggle logic generated by INI Tools from the INI file.
    """
    if not os.path.exists(ini_filepath):
        report_func({'ERROR'}, f"文件不存在: {ini_filepath}")
        return {'CANCELLED'}
        
    with open(ini_filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    skip_keyswap = False
    
    for line in lines:
        stripped = line.strip()
        
        # 1. 过滤掉 KeySwap 块
        if stripped.startswith('[KeySwap'):
            skip_keyswap = True
            continue
            
        if skip_keyswap:
            if stripped.startswith('['):
                skip_keyswap = False
            elif stripped == "":
                continue
            else:
                continue
                
        if not skip_keyswap:
            # 2. 彻底过滤掉生成的所有预设常量和变量标题行
            if stripped == "[Constants]":
                continue
            if stripped == "[Present]":
                continue
            if stripped == "; =======================================":
                continue
            if stripped == "; Variables":
                continue
            if stripped.startswith('global persist $'):
                continue
            if stripped.startswith('global $active'):
                continue
            if stripped == f"{ACTIVE_VARIABLE} = 1" or stripped == f"post {ACTIVE_VARIABLE} = 0":
                continue
            
            # 3. 过滤掉 if / else 条件块
            if stripped.startswith('if $') or stripped.startswith('else if $') or stripped == 'endif':
                continue
                
            # 4. 恢复 drawindexed 代码块的原始缩进
            if line.startswith('    ;') or line.startswith('    drawindexed'):
                new_lines.append(line[4:])
                continue
                
            new_lines.append(line)
            
    # 清理多余的空白行
    cleaned_lines = []
    empty_count = 0
    for line in new_lines:
        if line.strip() == "":
            empty_count += 1
            if empty_count <= 2:
                cleaned_lines.append(line)
        else:
            empty_count = 0
            cleaned_lines.append(line)
            
    with open(ini_filepath, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)
        
    report_func({'INFO'}, "已成功清除INI文件中的切换代码。")
    return {'FINISHED'}