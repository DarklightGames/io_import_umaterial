import math
import uuid

import bpy
from bpy.types import Operator, Context
from bpy.props import StringProperty, FloatProperty
from typing import Union, Set

from .builder import ensure_projector_node_tree


def bake_projector(projector_object: bpy.types.Object):
    projector = projector_object.bdk.projector
    modifier = projector_object.modifiers['Projector']
    session_uid = projector_object.session_uid
    for bake in modifier.bakes:
        bpy.ops.object.geometry_node_bake_single(
            session_uid=session_uid,
            modifier_name=modifier.name,
            bake_id=bake.bake_id
        )
    projector.is_baked = True


def unbake_projector(projector_object: bpy.types.Object):
    projector = projector_object.bdk.projector
    modifier = projector_object.modifiers['Projector']
    session_uid = projector_object.session_uid
    for bake in modifier.bakes:
        bpy.ops.object.geometry_node_bake_delete_single(
            session_uid=session_uid,
            modifier_name=modifier.name,
            bake_id=bake.bake_id
        )
    projector.is_baked = False


class BDK_OT_projector_bake(Operator):
    bl_idname = 'bdk.projector_bake'
    bl_label = 'Bake Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if context.active_object is None or context.active_object.bdk.type != 'PROJECTOR':
            return False
        projector = context.active_object.bdk.projector
        if projector.is_baked:
            cls.poll_message_set(f'Projector is already baked')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        bake_projector(context.active_object)
        self.report({'INFO'}, 'Baked projector')
        return {'FINISHED'}


class BDK_OT_projector_unbake(Operator):
    bl_idname = 'bdk.projector_unbake'
    bl_label = 'Unbake Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if context.active_object is None or context.active_object.bdk.type != 'PROJECTOR':
            return False
        projector = context.active_object.bdk.projector
        if not projector.is_baked:
            cls.poll_message_set(f'Projector is not baked')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        unbake_projector(context.active_object)
        self.report({'INFO'}, 'Unbaked projector')
        return {'FINISHED'}


class BDK_OT_projector_add(Operator):

    bl_idname = 'bdk.projector_add'
    bl_label = 'Add Projector'
    bl_options = {'REGISTER', 'UNDO'}

    target: StringProperty(name='Target')
    material_name: StringProperty(name='Material')
    fov: FloatProperty(name='FOV', default=0.0, min=0.0, max=180.0)
    max_trace_distance: FloatProperty(name='Max Trace Distance', default=1024.0, min=0.0, soft_min=1.0, soft_max=4096.0, subtype='DISTANCE')

    def draw(self, context: Context):
        self.layout.prop_search(self, 'target', bpy.data, 'doodad')
        self.layout.prop_search(self, 'material_name', bpy.data, 'materials')
        self.layout.prop(self, 'fov')
        self.layout.prop(self, 'max_trace_distance')

    def invoke(self, context: 'Context', event: 'Event'):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> Union[Set[int], Set[str]]:

        # Add a new mesh object at the 3D cursor.
        mesh_data = bpy.data.meshes.new(name=uuid.uuid4().hex)

        bpy_object = bpy.data.objects.new("Projector", mesh_data)
        bpy_object.location = context.scene.cursor.location
        bpy_object.lock_scale = (True, True, True)
        bpy_object.bdk.type = 'PROJECTOR'

        # TODO: Set this up.
        material = bpy.data.materials.get(self.material_name, None)
        target = bpy.data.objects.get(self.target, None)

        # Rotate the projector so that it is facing down.
        bpy_object.rotation_euler = (0.0, math.pi / 2, 0.0)

        modifier = bpy_object.modifiers.new(name='Projector', type='NODES')
        modifier.node_group = ensure_projector_node_tree()

        socket_properties = {
            'Socket_2': 'draw_scale',
            'Socket_4': 'fov',
            'Socket_5': 'max_trace_distance',
        }

        for socket_name, property_name in socket_properties.items():
            fcurve = bpy_object.driver_add(f'modifiers["Projector"]["{socket_name}"]')
            fcurve.driver.type = 'SCRIPTED'
            fcurve.driver.use_self = True
            fcurve.driver.expression = f'self.id_data.bdk.projector.{property_name}'

        # Deselect all doodad.
        for obj in context.selected_objects:
            obj.select_set(False)

        # Add the object into the scene and select it.
        context.collection.objects.link(bpy_object)
        context.view_layer.objects.active = bpy_object
        bpy_object.select_set(True)

        return {'FINISHED'}


class BDK_OT_projectors_bake(Operator):
    bl_idname = 'bdk.projectors_bake'
    bl_label = 'Bake Projectors'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        count = 0
        for obj in context.selected_objects:
            if obj.bdk.type == 'PROJECTOR' and not obj.bdk.projector.is_baked:
                bake_projector(obj)
                count += 1
        self.report({'INFO'}, f'Baked {count} projectors')
        return {'FINISHED'}


class BDK_OT_projectors_unbake(Operator):
    bl_idname = 'bdk.projectors_unbake'
    bl_label = 'Unbake Projectors'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> Set[str]:
        count = 0
        for obj in context.selected_objects:
            if obj.bdk.type == 'PROJECTOR' and obj.bdk.projector.is_baked:
                unbake_projector(obj)
                count += 1
        self.report({'INFO'}, f'Unbaked {count} projectors')
        return {'FINISHED'}


classes = (
    BDK_OT_projector_add,
    BDK_OT_projector_bake,
    BDK_OT_projector_unbake,
    BDK_OT_projectors_bake,
    BDK_OT_projectors_unbake,
)
