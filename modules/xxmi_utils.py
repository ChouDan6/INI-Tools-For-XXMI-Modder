"""XXMI utility functions for parsing and transforming XXMI exports."""

from typing import List, Dict, Tuple

from .config import ACTIVE_VARIABLE
from .utils import (
    extract_name_index,
    standardize_var_name,
    is_section_header,
    extract_section_name,
    is_comment,
    is_drawindexed,
)


def transform_xxmi_to_conditionals(ini_content: List[str], component_variables: dict, report_func=None) -> List[str]:
    """
    Transform XXMI static drawindexed values into conditional blocks.
    
    This is the core function that converts XXMI exports into toggle-enabled INIs.
    
    Args:
        ini_content: Original XXMI-exported INI content
        component_variables: Component structure from collect_scene_variables()
        report_func: Blender report function for logging
        
    Returns:
        Modified INI content with conditional blocks
    """
    # Parse static drawindexed values from XXMI
    static_draws = parse_static_drawindexed(ini_content, report_func)
    
    # Group by variables following the existing conditional logic
    variable_groups = group_by_variables(static_draws, component_variables, report_func)
    
    # Replace static values with conditional blocks
    result = replace_with_conditionals(ini_content, variable_groups, report_func)
    
    return result


def parse_static_drawindexed(ini_content: List[str], report_func=None) -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Parse static drawindexed values from XXMI export.

    Returns:
        Dict mapping section names to list of (comment, mesh_name, drawindexed_value) tuples
    """
    static_draws: Dict[str, List[Tuple[str, str, str]]] = {}
    current_section = None

    i = 0
    while i < len(ini_content):
        line = ini_content[i].strip()

        if is_section_header(line):
            current_section = extract_section_name(line)
            i += 1
            continue

        # Look for comment + drawindexed pattern
        if is_comment(line) and current_section:
            comment = line
            mesh_name = extract_mesh_name_from_comment(comment)

            # Check if next line is drawindexed
            if i + 1 < len(ini_content):
                next_line = ini_content[i + 1].strip()
                if is_drawindexed(next_line):
                    drawindexed_value = next_line.split('=', 1)[1].strip()
                    static_draws.setdefault(current_section, []).append(
                        (comment, mesh_name, drawindexed_value)
                    )
                    i += 2  # Skip both comment and drawindexed lines
                    continue

        i += 1

    return static_draws


def extract_mesh_name_from_comment(comment: str) -> str:
    """Extract mesh name from comment line like '; MeshName_01 (123)' or '; InnerSkirt (L) (947)'"""
    comment_text = comment[1:].strip()
    
    # Handle different comment patterns:
    # Pattern 1: "; MeshName_01 (123)" -> "MeshName_01"
    # Pattern 2: "; InnerSkirt (L) (947)" -> "InnerSkirt (L)"
    # Pattern 3: "; InnerShirt (14)" -> "InnerShirt"
    
    # Find the last parentheses with numbers (drawindexed count)
    # Split by parentheses and check each part
    parts = comment_text.split('(')
    if len(parts) >= 2:
        # Check if the last part contains only numbers and closing paren
        last_part = parts[-1]
        if last_part.replace(')', '').strip().isdigit():
            # Remove the last parentheses part (the number)
            mesh_name = '('.join(parts[:-1]).strip()
            return mesh_name
    
    # Fallback to original behavior if no numeric parentheses found
    mesh_name = comment_text.split('(')[0].strip()
    return mesh_name


def group_by_variables(static_draws: Dict[str, List[Tuple[str, str, str]]], 
                      component_variables: dict, report_func=None) -> Dict[str, Dict]:
    """
    Group static drawindexed values by toggle variables.
    
    This follows the same logic as the original conditional generation:
    - Legs_01 and Legs_01.001 share the same conditional
    - InnerShirt_01, InnerShirt_02 become options 0, 1 for variable 'innershirt'
    """
    variable_groups = {}
    
    for section_name, draws_list in static_draws.items():
        # Group by variable names
        section_vars = {}
        
        for comment, mesh_name, drawindexed_value in draws_list:
            # Extract base name and index using existing logic
            base_name, index = extract_name_index(mesh_name)
            
            if not base_name:
                continue
                
            var_name = standardize_var_name(base_name)
            
            # Check if this variable exists in component_variables (from scene analysis)
            # This handles both indexed meshes (_01, _02) and single meshes that are in collections
            variable_exists_in_scene = False
            for component_name, component_vars in component_variables.items():
                if var_name in component_vars:
                    variable_exists_in_scene = True
                    break
            
            # Skip if this mesh doesn't have a corresponding variable in the scene
            if not variable_exists_in_scene:
                continue
            
            # Map index to option number
            if index is not None:
                # Indexed mesh: index 1 -> option 0, index 2 -> option 1, etc.
                option = max(0, (index - 1))
            else:
                # Single mesh in collection: treat as option 0
                option = 0
            
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


def replace_with_conditionals(ini_content: List[str], variable_groups: Dict[str, Dict],
                              report_func=None) -> List[str]:
    """
    Replace static drawindexed values with conditional blocks.
    """
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
    """
    Process a section by replacing static drawindexed with conditionals.
    """
    i = start_idx + 1  # Skip section header
    active_inserted = False

    while i < len(ini_content):
        line = ini_content[i]
        stripped = line.strip()

        # Stop if we hit next section
        if is_section_header(stripped):
            break

        # Stop if we hit comment separators
        if is_comment(stripped) and ('---' in stripped or 'CommandList' in stripped or 'Resources' in stripped):
            break

        # Check for comment + drawindexed pattern to replace
        if is_comment(stripped):
            mesh_name = extract_mesh_name_from_comment(stripped)

            # Check if this mesh should be part of a conditional
            should_skip = any(
                mesh_data['mesh_name'] == mesh_name
                for options in section_vars.values()
                for meshes in options.values()
                for mesh_data in meshes
            )

            if should_skip:
                # Skip this comment and its drawindexed line
                if i + 1 < len(ini_content) and is_drawindexed(ini_content[i + 1].strip()):
                    i += 2
                else:
                    i += 1
                continue

        # Insert $active = 1 after headers but before content
        if not active_inserted and stripped and not is_comment(stripped) and not is_section_header(stripped):
            if section_vars:
                result.append(f"{ACTIVE_VARIABLE} = 1\n")
                active_inserted = True

        result.append(line)
        i += 1

    add_conditional_blocks(section_vars, result, report_func)
    return i


def add_conditional_blocks(section_vars: Dict, result: List[str], report_func=None):
    """Add conditional if/else blocks for each variable."""
    
    for var_name, options in section_vars.items():
        # Sort options by key to ensure consistent ordering
        sorted_options = sorted(options.items())
        
        for idx, (option, meshes) in enumerate(sorted_options):
            # Generate if/else if prefix
            if idx == 0:
                prefix = "if"
            else:
                prefix = "else if"
            
            result.append(f"{prefix} ${var_name} == {option}\n")
            
            # Add all meshes for this option
            for mesh_data in meshes:
                result.append(f"    {mesh_data['comment']}\n")
                result.append(f"    drawindexed = {mesh_data['drawindexed']}\n")
        
        result.append("endif\n")
        result.append("\n")  # Add spacing after each variable block
    
    # Remove the extra newline at the very end if there were any conditionals
    if section_vars and result and result[-1] == "\n":
        result.pop()  # Remove the last extra newline


