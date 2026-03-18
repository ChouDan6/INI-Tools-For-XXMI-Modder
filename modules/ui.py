"""UI components for INI Tools addon.

This module contains all Blender UI-related classes and components.
Handles panels, preferences, property groups, and UI operators.
"""

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, IntProperty
from bpy.types import PropertyGroup, Operator, AddonPreferences, Panel

from .config import DEFAULT_KEYS


class NewMeshItem(PropertyGroup):
    """Property group for new mesh items."""
    mesh_name: StringProperty()
    drawindexed_line: StringProperty()


class DeletedMeshItem(PropertyGroup):
    """Property group for deleted mesh items (in INI but not in XXMI export)."""
    mesh_name: StringProperty()


class CopyMeshLineOperator(Operator):
    """Operator for copying mesh lines to clipboard."""
    bl_idname = "wm.copy_mesh_line"
    bl_label = "复制网格行"

    index: IntProperty()

    def execute(self, context):
        scene = context.scene
        item = scene.new_meshes[self.index]
        # Keep indentation consistent (4 spaces as default)
        line_to_copy = f"; {item.mesh_name}\n" \
                       f"    drawindexed = {item.drawindexed_line}\n"
        bpy.context.window_manager.clipboard = line_to_copy
        self.report({'INFO'}, f"已将 {item.mesh_name} 的行复制到剪贴板。")
        return {'FINISHED'}


class INIToolsPreferences(AddonPreferences):
    """Addon preferences for INI Tools."""
    bl_idname = __package__.split('.')[0]  # Get main package name

    # 变量名修改为 toggle_keys 强制避开 Blender 的旧缓存
    toggle_keys: StringProperty(
        name="按键列表",
        description="用于切换的自定义按键，用逗号分隔 (例如 'VK_UP,1,2,3,0,VK_OEM_PLUS')",
        default=DEFAULT_KEYS
    )

    backup_ini: BoolProperty(
        name="备份INI",
        description="启用或禁用为选定的INI创建备份文件。",
        default=True,
    )

    naming_style: EnumProperty(
        name="变量命名风格",
        description="选择如何将中文网格名转换为INI变量名。拼音风格需要安装pypinyin库，否则自动退退至Hash",
        items=[
            ('PINYIN', "拼音 (需pypinyin库)", "智能将汉字转为拼音，如: neiyi"),
            ('HASH', "安全哈希 (Hash)", "将非英文字符转换为安全的哈希后缀，如: v_a7d3f9"),
        ],
        default='PINYIN',
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="设置自定义按键 (逗号分隔):")
        layout.prop(self, "toggle_keys", text="")
        layout.prop(self, "naming_style")
        layout.prop(self, "backup_ini", text="备份INI")


class GenerateINIPanel(Panel):
    """Main UI panel for INI Tools."""
    bl_label = "切换工具"
    bl_idname = "VIEW3D_PT_generate_ini"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "切换工具"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="选择模式:")
        col = layout.column()
        col.prop(scene, "operation_mode", expand=True)

        layout.prop(scene, "copy_files", text="复制文件")

        layout.prop(scene, "ini_file_path", text="INI文件")
        
        # 在面板上直接显示按键设置
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        if prefs:
            layout.prop(prefs, "toggle_keys", text="切换按键")
            layout.prop(prefs, "naming_style", text="变量风格")

        # 运行按钮与清除按钮
        row = layout.row()
        row.operator("wm.ini_tools", text="运行")
        row.operator("wm.clear_ini_toggles", text="清除切换功能", icon='TRASH')

        if hasattr(scene, "new_meshes") and scene.new_meshes:
            layout.separator()
            layout.label(text="新增的网格:", icon='INFO')
            for i, item in enumerate(scene.new_meshes):
                row = layout.row(align=True)
                row.label(text=item.mesh_name)
                copy_op = row.operator("wm.copy_mesh_line", text="复制", icon='COPYDOWN')
                copy_op.index = i
            layout.label(text="复制 drawindexed 值。")

        if hasattr(scene, "deleted_meshes") and scene.deleted_meshes:
            layout.separator()
            layout.label(text="未在导出中找到的网格:", icon='ERROR')
            for item in scene.deleted_meshes:
                row = layout.row()
                row.label(text=item.mesh_name, icon='MESH_DATA')

        # 教程文本
        layout.separator()
        box = layout.box()
        box.label(text="使用说明:", icon='HELP')
        col = box.column(align=True)
        col.label(text="• 原始导入文件置于Containers集合中")
        col.label(text="• Containers集合放置无切换的网格文件，通常与原始导入文件同名")
        col.label(text="• 手_01 、 手_02 会创建一个名为 $shou 的切换变量，可在选项间循环切换")
        col.label(text="• 不带数字后缀的对象（如内衣）拥有独立的开关切换功能 $neiyi")
        col.label(text="• Blender 副本： A_01 与 A_01.001 视为同一选项，当 $A == 0 时一同渲染")
        col.label(text="• 数字后缀决定切换选项编号。 _01 对应选项 0， _02 对应选项 1，依此类推")


# UI registration functions
def register_ui():
    """Register UI classes."""
    bpy.utils.register_class(NewMeshItem)
    bpy.utils.register_class(DeletedMeshItem)
    bpy.utils.register_class(CopyMeshLineOperator)
    bpy.utils.register_class(INIToolsPreferences)
    bpy.utils.register_class(GenerateINIPanel)


def unregister_ui():
    """Unregister UI classes."""
    bpy.utils.unregister_class(GenerateINIPanel)
    bpy.utils.unregister_class(INIToolsPreferences)
    bpy.utils.unregister_class(CopyMeshLineOperator)
    bpy.utils.unregister_class(DeletedMeshItem)
    bpy.utils.unregister_class(NewMeshItem)