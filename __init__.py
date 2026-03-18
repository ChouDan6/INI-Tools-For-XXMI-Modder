bl_info = {
    "name": "切换工具",
    "author": "MaximiliumM",
    "version": (2, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > 切换工具",
    "description": "生成并管理带有XXMI工具集成的角色自定义INI文件",
    "warning": "",
    "wiki_url": "",
    "category": "Object",
}

from . import ini_tools

register = ini_tools.register
unregister = ini_tools.unregister

__all__ = ["register", "unregister"]