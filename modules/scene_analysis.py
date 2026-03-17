"""Scene analysis utilities for INI Tools addon.

This module handles Blender scene inspection and variable collection.
Responsible for analyzing mesh collections and generating toggle variables.
"""

import bpy
from typing import Dict, List, Tuple
from .config import CONTAINERS_COLLECTION, ACTIVE_VARIABLE
from .utils import natural_sort_key, get_container_name, standardize_var_name, extract_name_index, capitalize_var_name


def collect_scene_variables() -> tuple[dict, dict, dict]:
    """Gather toggle and component information from the Blender scene."""

    toggle_variables: dict[str, set[int]] = {}
    index_mappings: dict[str, dict[int, int]] = {}
    component_variables: dict[str, dict[str, dict[int, list[bpy.types.Object]]]] = {}

    containers_collection = bpy.data.collections.get(CONTAINERS_COLLECTION)
    if not containers_collection:
        raise RuntimeError(f"Error: '{CONTAINERS_COLLECTION}' collection not found in the scene.")

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
            var_name = standardize_var_name(base_name)

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


def build_key_sections(
    toggle_variables: dict,
    keys_list: list,
    report_func,
) -> tuple[list[str], list[str], list[str]]:
    """Generate constants, present and key swap sections for an INI file."""

    # Build clean constants section with just the toggle variables
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
            key = keys_list[keys_assigned]
            keys_assigned += 1
            key_swap_sections.append(f"key =  {key}\n")
        else:
            report_func({'WARNING'}, f"Not enough keys for variable '{var_name}'. Assign a key manually.")
            key_swap_sections.append("; PLEASE REPLACE WITH ACTUAL KEY\n")
            key_swap_sections.append("key =  REPLACE\n")
        key_swap_sections.append(f"condition = {ACTIVE_VARIABLE} == 1\n")
        key_swap_sections.append("type = cycle\n")
        opts = ",".join(map(str, toggle_variables[var_name]))
        key_swap_sections.append(f"${var_name} = {opts}\n\n")

    return constants_section, present_section, key_swap_sections
