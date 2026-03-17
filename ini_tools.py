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
from .modules.operations import execute_generate_mode, execute_update_mode


class GenerateINIWithTogglesOperator(bpy.types.Operator):
    """Main operator for INI Tools addon."""
    bl_idname = "wm.ini_tools"
    bl_label = "Generate INI with Toggles"
    bl_description = "Generate or update INI files with toggle functionality"

    filepath: bpy.props.StringProperty(
        name="INI File",
        description="Path to the exported INI file",
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
            self.report({'ERROR'}, f"The file '{ini_filepath}' does not exist or is not set.")
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
                self.report({'WARNING'}, f"Could not create backup: {e}")
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
            self.report({'ERROR'}, f"Unknown operation mode: {operation_mode}")
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
                self.report({'INFO'}, f"INI file processed successfully. Backup created at '{os.path.basename(backup_filepath)}'")
            else:
                self.report({'INFO'}, "INI file processed successfully.")
        
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


def register():
    """Register all addon components."""
    register_ui()
    bpy.utils.register_class(GenerateINIWithTogglesOperator)

    # Import property groups for scene property registration
    from .modules.ui import NewMeshItem, DeletedMeshItem

    # Register scene properties
    bpy.types.Scene.operation_mode = bpy.props.EnumProperty(
        name="Mode",
        description="Choose operation mode",
        items=[
            ('GENERATE', "Generate Toggles", "Generate new INI with toggles from XXMI export"),
            ('UPDATE', "Update Existing INI", "Update drawindexed values from new XXMI export"),
        ],
        default='GENERATE',
    )
    
    bpy.types.Scene.copy_files = bpy.props.BoolProperty(
        name="Copy Files",
        description="Copy additional buffer and index files",
        default=False,
    )
    
    bpy.types.Scene.ini_file_path = bpy.props.StringProperty(
        name="INI File Path",
        description="Path to the INI file",
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

    bpy.utils.unregister_class(GenerateINIWithTogglesOperator)
    unregister_ui()


if __name__ == "__main__":
    register()