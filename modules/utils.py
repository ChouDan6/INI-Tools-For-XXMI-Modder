"""General utility functions for INI Tools addon."""

import re

def natural_sort_key(s: str) -> list:
    """Sort strings containing numbers naturally (e.g., _01 before _02)."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]


def get_container_name(mesh_name: str) -> str:
    """Extract container name from mesh name (removes .001 extensions)."""
    return mesh_name.split('.')[0]


def extract_name_index(mesh_name: str) -> tuple[str, int | None]:
    """
    Extract base name and index from mesh name.
    Expects format like 'MeshName_01' or 'MeshName_01.001'.
    Returns: (base_name, index)
    """
    base_name = mesh_name.split('.')[0]
    parts = base_name.split('_')

    if len(parts) > 1 and parts[-1].isdigit():
        index_str = parts[-1]
        name = '_'.join(parts[:-1])
        return name, int(index_str)

    return base_name, None


def standardize_var_name(name: str) -> str:
    """Convert name to lowercase for INI variables."""
    return name.lower()


def capitalize_var_name(name: str) -> str:
    """Capitalize first letter for KeySwap sections."""
    if not name:
        return name
    return name[0].upper() + name[1:]


def is_section_header(line: str) -> bool:
    """Check if line is an INI section header (e.g. '[Constants]')."""
    stripped = line.strip()
    return stripped.startswith('[') and stripped.endswith(']')


def extract_section_name(line: str) -> str:
    """Extract section name without brackets."""
    return line.strip()[1:-1]


def is_comment(line: str) -> bool:
    """Check if line is a comment."""
    return line.strip().startswith(';')


def is_drawindexed(line: str) -> bool:
    """Check if line contains drawindexed."""
    return line.strip().lower().startswith('drawindexed')
