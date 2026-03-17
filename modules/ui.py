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
    bl_label = "Copy Mesh Line"

    index: IntProperty()

    def execute(self, context):
        scene = context.scene
        item = scene.new_meshes[self.index]
        # Keep indentation consistent (4 spaces as default)
        line_to_copy = f"; {item.mesh_name}\n" \
                       f"    drawindexed = {item.drawindexed_line}\n"
        bpy.context.window_manager.clipboard = line_to_copy
        self.report({'INFO'}, f"Copied lines for {item.mesh_name} to clipboard.")
        return {'FINISHED'}


class INIToolsPreferences(AddonPreferences):
    """Addon preferences for INI Tools."""
    bl_idname = __package__.split('.')[0]  # Get main package name

    custom_keys: StringProperty(
        name="Key List",
        description="Custom keys for toggling, separated by commas (e.g. '1,2,3,0,VK_OEM_PLUS')",
        default=DEFAULT_KEYS
    )

    backup_ini: BoolProperty(
        name="Backup INI",
        description="Enable or disable creating backup files for the selected INI.",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Set your custom keys (comma-separated):")
        layout.prop(self, "custom_keys", text="")
        layout.prop(self, "backup_ini", text="Backup INI")


class GenerateINIPanel(Panel):
    """Main UI panel for INI Tools."""
    bl_label = "INI Tools"
    bl_idname = "VIEW3D_PT_generate_ini"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "INI Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Select Mode:")
        col = layout.column()
        col.prop(scene, "operation_mode", expand=True)

        layout.prop(scene, "copy_files", text="Copy Files")

        layout.prop(scene, "ini_file_path", text="INI File")

        layout.operator("wm.ini_tools", text="Run")

        if hasattr(scene, "new_meshes") and scene.new_meshes:
            layout.separator()
            layout.label(text="Newly Added Meshes:", icon='INFO')
            for i, item in enumerate(scene.new_meshes):
                row = layout.row(align=True)
                row.label(text=item.mesh_name)
                copy_op = row.operator("wm.copy_mesh_line", text="Copy", icon='COPYDOWN')
                copy_op.index = i
            layout.label(text="Copy drawindexed values.")

        if hasattr(scene, "deleted_meshes") and scene.deleted_meshes:
            layout.separator()
            layout.label(text="Meshes Not in Export:", icon='ERROR')
            for item in scene.deleted_meshes:
                row = layout.row()
                row.label(text=item.mesh_name, icon='MESH_DATA')


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
