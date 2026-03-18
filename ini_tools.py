"""Main operator for INI Tools addon.

This module contains the core Blender operator that orchestrates
all INI processing operations through the modular system.
"""

import bpy
import os
import shutil
from datetime import datetime

from .modules.ui import register_ui, unregister_ui
from .modules.scene_analysis import collect_scene_variables
from .modules.operations import execute_generate_mode, execute_update_mode, execute_clear_mode


class GenerateINIWithTogglesOperator(bpy.types.Operator):
    """Main operator for INI Tools addon."""
    bl_idname = "wm.ini_tools"
    bl_label = "生成带切换功能的INI"
    bl_description = "生成或更新具有切换功能的INI文件"

    filepath: bpy.props.StringProperty(
        name="INI文件",
        description="导出INI文件的路径",
        subtype='FILE_PATH',
    )

    def execute(self, context):
        """Main execution method that orchestrates all operations."""
        scene = context.scene
        
        # Clear old mesh data each time we run
        scene.new_meshes.clear()
        scene.deleted_meshes.clear()

        operation_mode = scene.operation_mode
        ini_filepath = bpy.path.abspath(scene.ini_file_path)

        if not ini_filepath or not os.path.exists(ini_filepath):
            self.report({'ERROR'}, f"文件 '{ini_filepath}' 不存在或未设置。")
            return {'CANCELLED'}

        # Handle backup functionality
        prefs = bpy.context.preferences.addons[__package__].preferences
        do_backup = prefs.backup_ini
        backup_filepath = None
        
        if do_backup:
            ini_filename = os.path.basename(ini_filepath)
            base_name, ext = os.path.splitext(ini_filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(ini_filepath), "Backup")
            os.makedirs(backup_dir, exist_ok=True)

            backup_filename = f"{base_name}_{timestamp}{ext}.bkp"
            backup_filepath = os.path.join(backup_dir, backup_filename)
            
            try:
                shutil.copy2(ini_filepath, backup_filepath)
            except Exception as e:
                self.report({'WARNING'}, f"无法创建备份: {e}")
                backup_filepath = None

        # Read INI content and collect scene variables
        with open(ini_filepath, "r", encoding="utf-8") as file:
            ini_content = file.readlines()

        try:
            toggle_variables, index_mappings, component_variables = collect_scene_variables()
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        # Route to appropriate operation mode
        if operation_mode == 'GENERATE':
            result = execute_generate_mode(ini_filepath, ini_content, component_variables, self.report)
        elif operation_mode == 'UPDATE':
            result = execute_update_mode(ini_filepath, ini_content, component_variables, self.report)
        else:
            self.report({'ERROR'}, f"未知的操作模式: {operation_mode}")
            return {'CANCELLED'}

        # Handle results from operations
        if isinstance(result, dict):
            if 'new_meshes' in result:
                # Add new meshes to scene for UI display
                for mesh_info in result['new_meshes']:
                    item = scene.new_meshes.add()
                    item.mesh_name = mesh_info['mesh_name']
                    item.drawindexed_line = mesh_info['drawindexed_line']
            if 'deleted_meshes' in result:
                # Add deleted meshes to scene for UI display
                for mesh_info in result['deleted_meshes']:
                    item = scene.deleted_meshes.add()
                    item.mesh_name = mesh_info['mesh_name']
            operation_result = result.get('result', {'FINISHED'})
        else:
            operation_result = result

        # Final reporting
        if operation_result == {'FINISHED'}:
            if do_backup and backup_filepath:
                self.report({'INFO'}, f"INI文件处理成功。已在 '{os.path.basename(backup_filepath)}' 创建备份")
            else:
                self.report({'INFO'}, "INI文件处理成功。")
        
        return operation_result

    def invoke(self, context, event):
        """Invoke the file browser if no file is set."""
        scene = context.scene
        self.filepath = scene.ini_file_path
        if not self.filepath:
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        else:
            return self.execute(context)


class ClearINITogglesOperator(bpy.types.Operator):
    """清除INI文件中的所有切换代码"""
    bl_idname = "wm.clear_ini_toggles"
    bl_label = "清除切换功能"
    bl_description = "一键从选定的INI文件中清除所有由本插件生成的切换代码，恢复原生结构"

    @classmethod
    def poll(cls, context):
        return bool(context.scene.ini_file_path)

    def execute(self, context):
        scene = context.scene
        ini_filepath = bpy.path.abspath(scene.ini_file_path)

        if not ini_filepath or not os.path.exists(ini_filepath):
            self.report({'ERROR'}, "INI文件不存在或未设置。")
            return {'CANCELLED'}

        return execute_clear_mode(ini_filepath, self.report)


def register():
    """Register all addon components."""
    register_ui()
    bpy.utils.register_class(GenerateINIWithTogglesOperator)
    bpy.utils.register_class(ClearINITogglesOperator)

    # Import property groups for scene property registration
    from .modules.ui import NewMeshItem, DeletedMeshItem

    # Register scene properties
    bpy.types.Scene.operation_mode = bpy.props.EnumProperty(
        name="模式",
        description="选择操作模式",
        items=[
            ('GENERATE', "生成切换", "从XXMI导出生成带有切换功能的新INI"),
            ('UPDATE', "更新现有INI", "从新的XXMI导出中更新drawindexed值"),
        ],
        default='GENERATE',
    )
    
    bpy.types.Scene.copy_files = bpy.props.BoolProperty(
        name="复制文件",
        description="复制附加的buffer和index文件",
        default=False,
    )
    
    bpy.types.Scene.ini_file_path = bpy.props.StringProperty(
        name="INI文件路径",
        description="INI文件的路径",
        subtype='FILE_PATH',
    )
    
    bpy.types.Scene.new_meshes = bpy.props.CollectionProperty(type=NewMeshItem)
    bpy.types.Scene.deleted_meshes = bpy.props.CollectionProperty(type=DeletedMeshItem)


def unregister():
    """Unregister all addon components."""
    # Delete scene properties
    del bpy.types.Scene.deleted_meshes
    del bpy.types.Scene.new_meshes
    del bpy.types.Scene.ini_file_path
    del bpy.types.Scene.operation_mode
    del bpy.types.Scene.copy_files

    bpy.utils.unregister_class(ClearINITogglesOperator)
    bpy.utils.unregister_class(GenerateINIWithTogglesOperator)
    unregister_ui()


if __name__ == "__main__":
    register()
