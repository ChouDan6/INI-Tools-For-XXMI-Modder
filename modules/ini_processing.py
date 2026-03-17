"""INI file processing utilities for INI Tools addon.

This module handles pure INI file manipulation and processing.
No Blender dependencies - pure Python file operations.
"""

from typing import List, Dict, Optional
import re

# Support both relative imports (when used as part of package) and direct imports (for testing)
try:
    from .utils import (
        is_section_header,
        extract_section_name,
        is_conditional_start,
        is_draw_line,
    )
except ImportError:
    from utils import (
        is_section_header,
        extract_section_name,
        is_conditional_start,
        is_draw_line,
    )


def parse_draw_lines(ini_lines: List[str]) -> Dict[tuple, List[str]]:
    """
    Parse lines from an INI file, returning a dictionary of
    (section_name, condition_line) -> [list_of_draw_lines].

    `condition_line` is the *exact* text of the most recent
    'if' or 'else if' line (or None if outside such blocks).
    """
    data: Dict[tuple, List[str]] = {}
    current_section = None
    current_condition = None

    for line in ini_lines:
        stripped = line.strip()

        if is_section_header(stripped):
            current_section = extract_section_name(stripped)
            current_condition = None
            continue

        if is_conditional_start(stripped):
            current_condition = stripped
            continue

        if stripped == 'endif':
            current_condition = None
            continue

        if is_draw_line(stripped):
            key = (current_section, current_condition)
            data.setdefault(key, []).append(line)

    return data


def merge_draw_lines_into_content(exported_data: Dict[tuple, List[str]], existing_lines: List[str]) -> List[str]:
    """
    For each line in existing_lines, if it's a 'draw = ...' line,
    try to replace it with the corresponding line(s) from exported_data.
    We'll match by (section_name, condition_line).

    Returns a new list of lines with updated draw statements.
    """
    new_lines = []
    current_section = None
    current_condition = None

    for line in existing_lines:
        stripped = line.strip()

        if is_section_header(stripped):
            current_section = extract_section_name(stripped)
            current_condition = None
            new_lines.append(line)
            continue

        if is_conditional_start(stripped):
            current_condition = stripped
            new_lines.append(line)
            continue

        if stripped == 'endif':
            current_condition = None
            new_lines.append(line)
            continue

        if is_draw_line(stripped):
            key = (current_section, current_condition)
            if key in exported_data and exported_data[key]:
                new_lines.extend(exported_data[key])
            else:
                new_lines.append(line)
            continue

        new_lines.append(line)

    return new_lines


def extract_vertex_count_from_draw(draw_line: str) -> Optional[int]:
    """
    Extract the first number (vertex count) from a draw line.

    Examples:
        'draw = 14157, 0' -> 14157
        '    draw = 9215, 0' -> 9215
        'drawindexed = 123, 0, 0' -> None (not a draw line)
    """
    stripped = draw_line.strip()
    if not is_draw_line(stripped):
        return None

    # Match 'draw = <number>, ...'
    match = re.match(r'draw\s*=\s*(\d+)', stripped, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_base_name_from_blend_section(section_name: str) -> Optional[str]:
    """
    Extract the base name from a Blend section name.

    Examples:
        'TextureOverrideYuzuhaOutfitBlend' -> 'YuzuhaOutfit'
        'TextureOverrideHuTaoCherryBlend' -> 'HuTaoCherry'
        'TextureOverrideAliceBodyBlend' -> 'AliceBody'
        'SomeOtherSection' -> None
    """
    if not section_name:
        return None
    match = re.match(r'TextureOverride(.+)Blend$', section_name)
    if match:
        return match.group(1)
    return None


def collect_blend_draw_values(ini_lines: List[str]) -> Dict[str, int]:
    """
    Parse INI content and return mapping of base names to vertex counts
    from Blend sections.

    Scans for sections named 'TextureOverride{BaseName}Blend' and extracts
    the first draw value found in each section.

    Returns:
        Dict mapping base names to vertex counts.
        e.g., {'YuzuhaOutfit': 14157, 'YuzuhaBody': 9215}
    """
    draw_values: Dict[str, int] = {}
    current_section = None
    current_base_name = None

    for line in ini_lines:
        stripped = line.strip()

        if is_section_header(stripped):
            section_name = extract_section_name(stripped)
            current_section = section_name
            current_base_name = extract_base_name_from_blend_section(section_name)
            continue

        # Only look for draw lines in Blend sections where we haven't found a value yet
        if current_base_name and current_base_name not in draw_values:
            if is_draw_line(stripped):
                vertex_count = extract_vertex_count_from_draw(stripped)
                if vertex_count is not None:
                    draw_values[current_base_name] = vertex_count

    return draw_values


def extract_base_name_from_vertex_limit_section(section_name: str) -> Optional[str]:
    """
    Extract the base name from a VertexLimitRaise section name.

    Examples:
        'TextureOverrideYuzuhaOutfitVertexLimitRaise' -> 'YuzuhaOutfit'
        'TextureOverrideHuTaoCherryVertexLimitRaise' -> 'HuTaoCherry'
        'SomeOtherSection' -> None
    """
    if not section_name:
        return None
    match = re.match(r'TextureOverride(.+)VertexLimitRaise$', section_name)
    if match:
        return match.group(1)
    return None


def update_override_vertex_counts(ini_lines: List[str], draw_values: Dict[str, int]) -> List[str]:
    """
    Update override_vertex_count lines to match corresponding draw values.

    For each 'TextureOverride{BaseName}VertexLimitRaise' section, updates the
    'override_vertex_count' line to match the draw value for {BaseName}.

    Args:
        ini_lines: List of INI file lines.
        draw_values: Dict mapping base names to vertex counts (from collect_blend_draw_values).

    Returns:
        Updated list of lines with synchronized override_vertex_count values.
    """
    new_lines = []
    current_base_name = None

    for line in ini_lines:
        stripped = line.strip()

        if is_section_header(stripped):
            section_name = extract_section_name(stripped)
            current_base_name = extract_base_name_from_vertex_limit_section(section_name)
            new_lines.append(line)
            continue

        # Update override_vertex_count if we're in a VertexLimitRaise section with a matching draw value
        if current_base_name and current_base_name in draw_values:
            if stripped.lower().startswith('override_vertex_count'):
                new_value = draw_values[current_base_name]
                # Preserve indentation
                indent = line[:len(line) - len(line.lstrip())]
                # Preserve line ending
                line_ending = '\n' if line.endswith('\n') else ''
                new_lines.append(f"{indent}override_vertex_count = {new_value}{line_ending}")
                continue

        new_lines.append(line)

    return new_lines


