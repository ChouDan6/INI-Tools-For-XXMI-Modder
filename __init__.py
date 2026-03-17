bl_info = {
    "name": "INI Tools",
    "author": "MaximiliumM",
    "version": (2, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > INI Tools",
    "description": "Generate and manage INI files with XXMI Tools integration for character customization",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

from . import ini_tools

register = ini_tools.register
unregister = ini_tools.unregister

__all__ = ["register", "unregister"]
