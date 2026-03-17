import re
from typing import Optional, Tuple


def natural_sort_key(name):
    """Return a key for natural sorting of strings."""
    parts = re.split(r'(\d+)', name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def get_container_name(mesh_name):
    """Strip any '-vb' suffix from a mesh name."""
    vb_index = mesh_name.find('-vb')
    return mesh_name[:vb_index] if vb_index != -1 else mesh_name


def standardize_var_name(name: str) -> str:
    """Convert a mesh name to a lowercase variable name.
    
    Examples:
        "Leg Band (L)" → "leg_band_l"
        "No Skirt Body" → "no_skirt_body"
        "Metal Rings" → "metal_rings"
    """
    # Convert to lowercase
    result = name.lower()
    # Replace spaces with underscores
    result = result.replace(" ", "_")
    # Remove parentheses and their contents, keeping the inner text
    result = result.replace("(", "_").replace(")", "")
    # Clean up multiple underscores
    while "__" in result:
        result = result.replace("__", "_")
    # Remove leading/trailing underscores
    result = result.strip("_")
    return result


def capitalize_var_name(var_name: str) -> str:
    """Transform a snake_case variable into PascalCase."""
    parts = var_name.split('_')
    return "".join(part.capitalize() for part in parts)


def extract_name_index(name: str) -> Tuple[str, Optional[int]]:
    """Split a name into base name and optional numeric index.
    
    Handles patterns like:
    - "Head_01" → ("Head", 1)
    - "Body_01 (Vanilla)" → ("Body", 1)  
    - "Belt" → ("Belt", None)
    - "Component_02.blend" → ("Component", 2)
    """
    # Remove file extensions first
    name = name.split('.')[0]
    
    # Look for _NN pattern, ignoring anything after it (like comments in parentheses)
    match = re.match(r"(.+?)_(\d+)", name)
    if match:
        return match.group(1), int(match.group(2))
    return name, None


# INI parsing utilities

def is_section_header(line: str) -> bool:
    """Check if line is an INI section header like [SectionName]."""
    stripped = line.strip()
    return stripped.startswith('[') and stripped.endswith(']')


def extract_section_name(line: str) -> str:
    """Extract section name from header line. Assumes is_section_header() is True."""
    return line.strip()[1:-1]


def is_comment(line: str) -> bool:
    """Check if line is a comment (starts with ;)."""
    return line.strip().startswith(';')


def is_conditional_start(line: str) -> bool:
    """Check if line starts an if/else if block."""
    lower = line.strip().lower()
    return lower.startswith('if ') or lower.startswith('else if')


def is_drawindexed(line: str) -> bool:
    """Check if line is a drawindexed statement."""
    return line.strip().lower().startswith('drawindexed =')


def is_draw_line(line: str) -> bool:
    """Check if line is a draw statement."""
    return line.strip().startswith('draw =')
