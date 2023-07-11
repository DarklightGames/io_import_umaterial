import uuid

import bpy
from bpy.types import Operator, Context, Collection, Event, Object
from bpy.props import EnumProperty

from .properties import ensure_terrain_info_modifiers
from .scatter.builder import ensure_scatter_layer_modifiers, add_scatter_layer_object, add_scatter_layer
from ...helpers import is_active_object_terrain_info, copy_simple_property_group, get_terrain_doodad, \
    is_active_object_terrain_doodad
from .builder import create_terrain_doodad, create_terrain_doodad_bake_node_tree


class BDK_OT_terrain_doodad_add(Operator):
    bl_label = 'Add Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_add'
    bl_description = 'Add a terrain doodad to the scene'

    object_type: EnumProperty(
        name='Type',
        items=(
            ('CURVE', 'Curve', 'A terrain doodad that uses a curve to define the shape', 'CURVE_DATA', 0),
            ('MESH', 'Mesh', 'A terrain doodad that uses a mesh to define the shape', 'MESH_DATA', 1),
            ('EMPTY', 'Empty', 'A terrain doodad that uses an empty to define the shape', 'EMPTY_DATA', 2),
        )
    )

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a terrain info object')
            return False
        return True

    def execute(self, context: Context):
        # TODO: have a way to select the terrain info object definition.
        terrain_info_object = context.active_object
        terrain_doodad = create_terrain_doodad(context, terrain_info_object, self.object_type)

        """
        BUG: If the terrain info object has been added as rigid body, the collection will be the
        RigidBodyWorld collection, which isn't actually a collection that shows up in the outliner or the view layer,
        and makes the function fail.
        
        How can we get the *actual* collection that the terrain info object is in (the one that shows up in the outliner)?
        """

        # Link and parent the terrain doodad to the terrain info.
        collection: Collection = terrain_info_object.users_collection[0]

        collection.objects.link(terrain_doodad)
        terrain_doodad.parent = terrain_info_object

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Select the terrain doodad.
        context.view_layer.objects.active = terrain_doodad
        terrain_doodad.select_set(True)

        # This needs to be called after the terrain doodad's parent is set.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def ensure_terrain_doodad_layer_indices(terrain_doodad):
    """
    Ensures that the layer indices of the given terrain doodad are correct.
    This is necessary because the indices are used in the driver expressions.
    Any change to the indices requires the driver expressions to be updated.
    :param terrain_doodad:
    """
    # Sculpt Layers
    for i, sculpt_layer in enumerate(terrain_doodad.sculpt_layers):
        sculpt_layer.index = i
    # Paint Layers
    for i, paint_layer in enumerate(terrain_doodad.paint_layers):
        paint_layer.index = i
    # Scatter Layers
    for i, scatter_layer in enumerate(terrain_doodad.scatter_layers):
        scatter_layer.index = i


class BDK_OT_terrain_doodad_sculpt_layer_add(Operator):
    bl_label = 'Add Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

        # Add a new sculpting layer.
        sculpt_layer = terrain_doodad.sculpt_layers.add()
        sculpt_layer.id = uuid.uuid4().hex
        sculpt_layer.terrain_doodad_object = terrain_doodad.object

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Set the sculpting component index to the new sculpting component.
        terrain_doodad.sculpt_layers_index = len(terrain_doodad.sculpt_layers) - 1

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_remove(Operator):
    bl_label = 'Remove Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        sculpt_layers_index = terrain_doodad.sculpt_layers_index

        terrain_doodad.sculpt_layers.remove(sculpt_layers_index)
        terrain_doodad.sculpt_layers_index = min(len(terrain_doodad.sculpt_layers) - 1, sculpt_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


# Add an operator that moves the sculpting component up and down in the list.
class BDK_OT_terrain_doodad_sculpt_layer_move(Operator):
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_move'
    bl_label = 'Move Sculpt Component'
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name='Direction',
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        )
    )

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        sculpt_layers_index = terrain_doodad.sculpt_layers_index
        if self.direction == 'UP':
            terrain_doodad.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index - 1)
            terrain_doodad.sculpt_layers_index -= 1
        elif self.direction == 'DOWN':
            terrain_doodad.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index + 1)
            terrain_doodad.sculpt_layers_index += 1

        ensure_terrain_doodad_layer_indices(terrain_doodad)
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


# TODO: Make this a macro operator that duplicates and then moves mode (same behavior as native duplicate).

class BDK_OT_terrain_doodad_duplicate(Operator):
    bl_idname = 'bdk.terrain_doodad_duplicate'
    bl_label = 'Duplicate Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Duplicate the terrain doodad'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object is not None and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        new_id = uuid.uuid4().hex
        terrain_doodad_object = context.active_object
        object_copy = terrain_doodad_object.copy()
        object_copy.name = new_id
        if terrain_doodad_object.data:
            data_copy = terrain_doodad_object.data.copy()
            data_copy.name = new_id
            object_copy.data = data_copy
        collection = terrain_doodad_object.users_collection[0]  # TODO: issue with RigidBody collection
        collection.objects.link(object_copy)

        copy_simple_property_group(terrain_doodad_object.bdk.terrain_doodad, object_copy.bdk.terrain_doodad)

        terrain_doodad = object_copy.bdk.terrain_doodad
        terrain_doodad.id = new_id
        terrain_doodad.object = object_copy

        # Add a new modifier to the terrain info object.
        terrain_info_object = terrain_doodad.terrain_info_object
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        # Deselect the active object.
        terrain_doodad_object.select_set(False)

        # Set the new object as the active object.
        context.view_layer.objects.active = object_copy

        return {'FINISHED'}


class BDK_OT_terrain_doodad_bake(Operator):
    bl_label = 'Bake Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_bake'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Bake the terrain doodad to the terrain'

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_doodad(context):
            cls.poll_message_set('Active object must be a terrain doodad')
            return False
        return True

    def execute(self, context: Context):
        """
        This whole thing will need to be reworked.

        We need to bake the sculpting layer directly to the terrain geometry.
        The paint and deco layers need to be written out as additive nodes for the affected layers.
        If the paint layers simply just *were* nodes, that may make things considerably easier conceptually, but
        would complicate the UI.

        The order of operations for sculpt layers is irrelevant, but the order of operations for paint and
        deco layers is important, but it's probably not something that we should concern ourselves with.

        How I imagine the baking working is this:

        1. A new modifier is added to the terrain info object that emulates the sculpting and painting.
        2. Instead of writing to the attributes they are associated with, write it to new attributes, then apply the
            modifier.
        3. Add a new terrain paint nodes for each affected layer with the IDs we generated during the bake.

        When the user does the bake, they should be given the option to bake to a new paint node or to an exiting one.

        Alternatively, we could make sure there is always an implicit paint node for each layer, and then just update
        the values of the paint node.

        The user will want a way to combine or "flatten" the layers, so we'll need to add a new operator to do that.
        """

        terrain_doodad_object = context.active_object
        terrain_doodad = get_terrain_doodad(terrain_doodad_object)
        terrain_info_object = terrain_doodad.terrain_info_object

        # Select the terrain info object and make it the active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # Create a new modifier for the terrain doodad bake.
        bake_node_tree = create_terrain_doodad_bake_node_tree(terrain_doodad)
        modifier = terrain_info_object.modifiers.new(terrain_doodad.id, 'NODES')
        modifier.node_group = bake_node_tree

        # Move the modifier to the top of the stack and apply it.
        bpy.ops.object.modifier_move_to_index(modifier=terrain_doodad.id, index=0)
        bpy.ops.object.modifier_apply(modifier=terrain_doodad.id)

        # Delete the bake node tree.
        bpy.data.node_groups.remove(bake_node_tree)

        # Delete the terrain doodad object.
        bpy.data.objects.remove(terrain_doodad_object)

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Rebuild the terrain info modifiers so that the now-deleted doodad is removed.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_add(Operator):
    bl_label = 'Add Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_doodad(context):
            cls.poll_message_set('Active object must be a terrain doodad')
            return False
        return True

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = get_terrain_doodad(terrain_doodad_object)
        paint_layer = terrain_doodad.paint_layers.add()
        paint_layer.id = uuid.uuid4().hex
        paint_layer.terrain_doodad_object = terrain_doodad_object

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        # Set the paint layer index to the new paint layer.
        terrain_doodad.paint_layers_index = len(terrain_doodad.paint_layers) - 1

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_remove(Operator):
    bl_label = 'Remove Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layers_index = terrain_doodad.paint_layers_index

        terrain_doodad.paint_layers.remove(paint_layers_index)
        terrain_doodad.paint_layers_index = min(len(terrain_doodad.paint_layers) - 1, paint_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_duplicate(Operator):
    bl_label = 'Duplicate Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        # TODO: wrap this into a function.
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layer_copy = terrain_doodad.paint_layers.add()

        # Copy the paint layer. Ignore the name because changing it will trigger the name change callback.
        copy_simple_property_group(terrain_doodad.paint_layers[terrain_doodad.paint_layers_index], paint_layer_copy,
                                   ignore={'name'})

        paint_layer_copy.id = uuid.uuid4().hex

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_duplicate(Operator):
    bl_label = 'Duplicate Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_doodad = terrain_info_object.bdk.terrain_doodad
        sculpt_layer_copy = terrain_doodad.sculpt_layers.add()

        copy_simple_property_group(terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index], sculpt_layer_copy)

        # Make sure the copy has a unique id.
        sculpt_layer_copy.id = uuid.uuid4().hex

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def delete_terrain_doodad(context: Context, terrain_doodad_object: Object):
    terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

    # Delete the modifier from the terrain info object.
    terrain_info_object = terrain_doodad.terrain_info_object

    # Delete the terrain doodad.
    bpy.data.objects.remove(terrain_doodad_object)

    # Rebuild the terrain doodad modifiers.
    ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)


class BDK_OT_terrain_doodad_delete(Operator):
    bl_idname = 'bdk.terrain_doodad_delete'
    bl_label = 'Delete Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        delete_terrain_doodad(context, context.active_object)
        return {'FINISHED'}


class BDK_OT_convert_to_terrain_doodad(Operator):
    bl_idname = 'bdk.convert_to_terrain_doodad'
    bl_label = 'Convert to Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        terrain_doodad_object_types = {'MESH', 'CURVE', 'EMPTY'}
        # Check if object is already a terrain doodad.
        if is_active_object_terrain_doodad(context):
            cls.poll_message_set('Object is already a terrain doodad')
            return False
        # Check if object is a mesh, curve or empty.
        if context.active_object is None or context.active_object.type not in terrain_doodad_object_types:
            cls.poll_message_set('Active object must be a mesh, curve or empty.')
            return False
        return True

    def execute(self, context: Context):
        # TODO: convert to terrain doodad (refactor from terrain doodad add)
        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_add(Operator):
    bl_label = 'Add Scatter Layer'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

        # Add a new sculpting layer.
        scatter_layer = add_scatter_layer(terrain_doodad)
        add_scatter_layer_object(scatter_layer)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        terrain_doodad.scatter_layers_index = len(terrain_doodad.scatter_layers) - 1

        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_remove(Operator):
    bl_label = 'Remove Scatter Layer'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        scatter_layers_index = terrain_doodad.scatter_layers_index

        scatter_layer_id = terrain_doodad.scatter_layers[scatter_layers_index].id

        terrain_doodad.scatter_layers.remove(scatter_layers_index)
        terrain_doodad.scatter_layers_index = min(len(terrain_doodad.scatter_layers) - 1, scatter_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Delete the associated node group.
        if scatter_layer_id in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups[scatter_layer_id])

        # Update the scatter layer modifiers.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_objects_add(Operator):
    bl_label = 'Add Scatter Layer Object'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_objects_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad and terrain_doodad.scatter_layers and terrain_doodad.scatter_layers_index >= 0

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        # Add a new scatter layer object.
        add_scatter_layer_object(scatter_layer)

        # Set the sculpting component index to the new sculpting component.
        scatter_layer.objects_index = len(scatter_layer.objects) - 1

        # TODO: do less here, just ensure the modifier for this scatter layer.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_objects_remove(Operator):
    bl_label = 'Remove Scatter Layer Object'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_objects_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad and terrain_doodad.scatter_layers and terrain_doodad.scatter_layers_index >= 0

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        objects_index = scatter_layer.objects_index
        scatter_layer.objects.remove(scatter_layer.objects_index)
        scatter_layer.objects_index = min(len(scatter_layer.objects) - 1, objects_index)

        # TODO: do less here, just ensure the modifier for this scatter layer.
        # Update the scatter layer modifiers.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


classes = (
    BDK_OT_convert_to_terrain_doodad,
    BDK_OT_terrain_doodad_add,
    BDK_OT_terrain_doodad_bake,
    BDK_OT_terrain_doodad_delete,
    BDK_OT_terrain_doodad_duplicate,
    BDK_OT_terrain_doodad_sculpt_layer_add,
    BDK_OT_terrain_doodad_sculpt_layer_remove,
    BDK_OT_terrain_doodad_sculpt_layer_move,
    BDK_OT_terrain_doodad_sculpt_layer_duplicate,
    BDK_OT_terrain_doodad_paint_layer_add,
    BDK_OT_terrain_doodad_paint_layer_remove,
    BDK_OT_terrain_doodad_paint_layer_duplicate,
    BDK_OT_terrain_doodad_scatter_layer_add,
    BDK_OT_terrain_doodad_scatter_layer_remove,
    BDK_OT_terrain_doodad_scatter_layer_objects_add,
    BDK_OT_terrain_doodad_scatter_layer_objects_remove,
)
