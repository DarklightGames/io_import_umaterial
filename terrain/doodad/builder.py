import uuid
from typing import List, Iterable, Optional, Dict, Set

import bmesh
import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, bpy_struct, Node

from .sculpt.builder import ensure_sculpt_value_node_group
from ..kernel import ensure_paint_layers, ensure_deco_layers, add_density_from_terrain_layer_nodes
from ...node_helpers import ensure_interpolation_node_tree, add_operation_switch_nodes, \
    add_noise_type_switch_nodes, ensure_geometry_node_tree, ensure_input_and_output_nodes, \
    add_geometry_node_switch_nodes, ensure_curve_modifier_node_tree
from .data import terrain_doodad_operation_items
from ...units import meters_to_unreal


distance_to_mesh_node_group_id = 'BDK Distance to Mesh'
distance_to_empty_node_group_id = 'BDK Distance to Empty'
distance_to_curve_node_group_id = 'BDK Distance to Curve'


def ensure_distance_to_curve_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        curve_to_mesh_node = node_tree.nodes.new(type='GeometryNodeCurveToMesh')

        geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
        geometry_proximity_node.target_element = 'EDGES'

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['Curve'], curve_to_mesh_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])

        # Internal
        node_tree.links.new(curve_to_mesh_node.outputs['Mesh'], geometry_proximity_node.inputs['Target'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
        node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])
        node_tree.links.new(combine_xyz_node_2.outputs['Vector'], geometry_proximity_node.inputs['Source Position'])

        # Output
        node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_curve_node_group_id, items, build_function)


def ensure_distance_noise_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketInt', 'Type'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Noise'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        noise_value_socket = add_noise_type_switch_nodes(
            node_tree,
            position_node.outputs['Position'],
            input_node.outputs['Type'],
            input_node.outputs['Distortion'],
            None
        )

        add_distance_noise_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_distance_noise_node.operation = 'ADD'
        add_distance_noise_node.label = 'Add Noise'

        use_noise_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        use_noise_switch_node.input_type = 'FLOAT'
        use_noise_switch_node.label = 'Use Noise'

        distance_noise_factor_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        distance_noise_factor_multiply_node.operation = 'MULTIPLY'
        distance_noise_factor_multiply_node.label = 'Factor'

        distance_noise_offset_subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        distance_noise_offset_subtract_node.operation = 'SUBTRACT'
        distance_noise_offset_subtract_node.label = 'Offset'

        # Input
        node_tree.links.new(input_node.outputs['Distance'], add_distance_noise_node.inputs[0])
        node_tree.links.new(input_node.outputs['Offset'], distance_noise_offset_subtract_node.inputs[1])
        node_tree.links.new(input_node.outputs['Factor'], distance_noise_factor_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Use Noise'], use_noise_switch_node.inputs[0])
        node_tree.links.new(input_node.outputs['Distance'], use_noise_switch_node.inputs[2])

        # Internal
        node_tree.links.new(noise_value_socket, distance_noise_offset_subtract_node.inputs[0])
        node_tree.links.new(distance_noise_offset_subtract_node.outputs['Value'], distance_noise_factor_multiply_node.inputs[0])
        node_tree.links.new(distance_noise_factor_multiply_node.outputs['Value'], add_distance_noise_node.inputs[1])
        node_tree.links.new(add_distance_noise_node.outputs['Value'], use_noise_switch_node.inputs[3])

        # Output
        node_tree.links.new(use_noise_switch_node.outputs[0], output_node.inputs['Distance'])

    return ensure_geometry_node_tree('BDK Distance Noise', items, build_function)


def ensure_doodad_paint_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Interpolation Type'),
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketString', 'Attribute'),
        ('INPUT', 'NodeSocketFloat', 'Radius'),
        ('INPUT', 'NodeSocketFloat', 'Falloff Radius'),
        ('INPUT', 'NodeSocketFloat', 'Strength'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Distance Noise'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Create a new Store Named Attribute node.
        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'BYTE_COLOR'
        store_named_attribute_node.domain = 'POINT'

        # Create a Named Attribute node.
        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'FLOAT'

        # Link the Attribute output of the input node to the name input of the named attribute node.
        node_tree.links.new(input_node.outputs['Attribute'], named_attribute_node.inputs['Name'])
        node_tree.links.new(input_node.outputs['Attribute'], store_named_attribute_node.inputs['Name'])

        # Pass the geometry from the input to the output.
        node_tree.links.new(input_node.outputs['Geometry'], output_node.inputs['Geometry'])

        # Add a subtract node.
        subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        subtract_node.operation = 'SUBTRACT'

        # Link the distance output of the input node to the first input of the subtraction node.
        node_tree.links.new(input_node.outputs['Radius'], subtract_node.inputs[1])

        # Add a divide node.
        divide_node = node_tree.nodes.new(type='ShaderNodeMath')
        divide_node.operation = 'DIVIDE'

        # Link the output of the subtraction node to the first input of the divide node.
        node_tree.links.new(subtract_node.outputs['Value'], divide_node.inputs[0])
        node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

        # Add an interpolation group node.
        interpolation_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        interpolation_group_node.node_tree = ensure_interpolation_node_tree()

        # Add a multiply node.
        strength_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        strength_multiply_node.operation = 'MULTIPLY'
        strength_multiply_node.label = 'Strength Multiply'

        value_socket = add_operation_switch_nodes(
            node_tree,
            input_node.outputs['Operation'],
            named_attribute_node.outputs[1],
            strength_multiply_node.outputs['Value'],
            [x[0] for x in terrain_doodad_operation_items]
        )

        # Add the distance noise node group.
        distance_noise_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_noise_group_node.node_tree = ensure_distance_noise_node_group()

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Distance'], distance_noise_group_node.inputs['Distance'])
        node_tree.links.new(input_node.outputs['Noise Type'], distance_noise_group_node.inputs['Type'])
        node_tree.links.new(input_node.outputs['Distance Noise Factor'], distance_noise_group_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Distance Noise Distortion'], distance_noise_group_node.inputs['Distortion'])
        node_tree.links.new(input_node.outputs['Distance Noise Offset'], distance_noise_group_node.inputs['Offset'])
        node_tree.links.new(input_node.outputs['Use Distance Noise'], distance_noise_group_node.inputs['Use Noise'])
        node_tree.links.new(input_node.outputs['Interpolation Type'], interpolation_group_node.inputs['Interpolation Type'])
        node_tree.links.new(input_node.outputs['Strength'], strength_multiply_node.inputs[1])

        # Internal
        node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])
        node_tree.links.new(interpolation_group_node.outputs['Value'], strength_multiply_node.inputs[0])
        node_tree.links.new(value_socket, store_named_attribute_node.inputs[5])
        node_tree.links.new(distance_noise_group_node.outputs['Distance'], subtract_node.inputs[0])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Doodad Paint', items, build_function)


def ensure_distance_to_mesh_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
        geometry_proximity_node.target_element = 'FACES'

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')
        transform_geometry_node.inputs['Scale'].default_value = (1.0, 1.0, 0.0)

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'VECTOR'

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], switch_node.inputs[8])
        node_tree.links.new(position_node.outputs['Position'], switch_node.inputs[9])
        node_tree.links.new(switch_node.outputs[3], geometry_proximity_node.inputs['Source Position'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], geometry_proximity_node.inputs['Target'])

        # Output
        node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_mesh_node_group_id, items, build_function)


def ensure_distance_to_empty_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketVector', 'Location'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        vector_subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'

        vector_length_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_length_node.operation = 'LENGTH'

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Location'], vector_subtract_node.inputs[0])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
        node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])
        node_tree.links.new(position_node.outputs['Position'], vector_subtract_node.inputs[1])
        node_tree.links.new(vector_subtract_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(combine_xyz_node_2.outputs['Vector'], vector_length_node.inputs['Vector'])

        # Output
        node_tree.links.new(vector_length_node.outputs['Value'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_empty_node_group_id, items, build_function)


def create_terrain_doodad_object(context: Context, terrain_info_object: Object, object_type: str = 'CURVE') -> Object:
    """
    Creates a terrain doodad of the specified type.
    Note that this function does not add the terrain doodad object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_info_object:
    :param object_type: The type of object to create. Valid values are 'CURVE', 'MESH' and 'EMPTY'
    :return:
    """
    if object_type == 'CURVE':
        object_data = bpy.data.curves.new(name=uuid4().hex, type='CURVE')
        spline = object_data.splines.new(type='BEZIER')

        # Add some points to the spline.
        spline.bezier_points.add(count=1)

        # Add a set of aligned meandering points.
        for i, point in enumerate(spline.bezier_points):
            point.co = (i, 0, 0)
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            point.handle_left = (i - 0.25, -0.25, 0)
            point.handle_right = (i + 0.25, 0.25, 0)

        # Scale the points.
        scale = meters_to_unreal(10.0)
        for point in spline.bezier_points:
            point.co *= scale
            point.handle_left *= scale
            point.handle_right *= scale
    elif object_type == 'EMPTY':
        object_data = None
    elif object_type == 'MESH':
        object_data = bpy.data.meshes.new(name=uuid4().hex)
        # Create a plane using bmesh.
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=meters_to_unreal(1.0))
        bm.to_mesh(object_data)
        del bm

    bpy_object = bpy.data.objects.new(name='Doodad', object_data=object_data)

    if object_type == 'EMPTY':
        bpy_object.empty_display_type = 'SPHERE'
        bpy_object.empty_display_size = meters_to_unreal(1.0)
        # Set the delta transform to the terrain info object's rotation.
        bpy_object.delta_rotation_euler = (0, 0, 0)
    elif object_type == 'MESH':
        bpy_object.display_type = 'WIRE'

    # Set the location of the curve object to the 3D cursor.
    bpy_object.location = context.scene.cursor.location

    # Convert the newly made object to a terrain doodad.
    convert_object_to_terrain_doodad(bpy_object, terrain_info_object)

    return bpy_object

def convert_object_to_terrain_doodad(obj: Object, terrain_info_object: Object):
    # Hide from rendering and Cycles passes.
    obj.hide_render = True

    # Disable all ray visibility settings (this stops it from being visible in Cycles rendering in the viewport).
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.visible_shadow = False

    terrain_doodad_id = uuid4().hex
    obj.bdk.type = 'TERRAIN_DOODAD'
    obj.bdk.terrain_doodad.id = terrain_doodad_id
    obj.bdk.terrain_doodad.terrain_info_object = terrain_info_object
    obj.bdk.terrain_doodad.object = obj
    obj.bdk.terrain_doodad.node_tree = bpy.data.node_groups.new(name=terrain_doodad_id, type='GeometryNodeTree')

    obj.show_in_front = True
    obj.lock_location = (False, False, True)
    obj.lock_rotation = (True, True, False)


def get_terrain_doodads_for_terrain_info_object(context: Context, terrain_info_object: Object) -> List['BDK_PG_terrain_doodad']:
    return [obj.bdk.terrain_doodad for obj in context.scene.objects if obj.bdk.type == 'TERRAIN_DOODAD' and obj.bdk.terrain_doodad.terrain_info_object == terrain_info_object]


def ensure_terrain_info_modifiers(context: Context, terrain_info: 'BDK_PG_terrain_info'):
    terrain_info_object: Object = terrain_info.terrain_info_object

    # Ensure that the modifier IDs have been generated.
    if terrain_info.doodad_sculpt_modifier_name == '':
        terrain_info.doodad_sculpt_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_attribute_modifier_name == '':
        terrain_info.doodad_attribute_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_paint_modifier_name == '':
        terrain_info.doodad_paint_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_deco_modifier_name == '':
        terrain_info.doodad_deco_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_mask_modifier_name == '':
        terrain_info.doodad_mask_modifier_name = uuid.uuid4().hex

    # Gather and sort the terrain doodad by the sort order and ID.
    terrain_doodads = get_terrain_doodads_for_terrain_info_object(context, terrain_info.terrain_info_object)
    terrain_doodads.sort(key=lambda x: (x.sort_order, x.id))

    # Ensure that the terrain info object has the required pass modifiers.
    modifier_names = [
        terrain_info.doodad_sculpt_modifier_name,
        terrain_info.doodad_attribute_modifier_name,
        terrain_info.doodad_paint_modifier_name,
        terrain_info.doodad_deco_modifier_name,
        terrain_info.doodad_mask_modifier_name,
    ]
    for modifier_name in modifier_names:
        if modifier_name not in terrain_info_object.modifiers:
            modifier = terrain_info_object.modifiers.new(name=modifier_name, type='NODES')
            modifier.show_on_cage = True

    # Ensure the node groups for the pass modifiers.
    modifiers = terrain_info_object.modifiers
    modifiers[terrain_info.doodad_sculpt_modifier_name].node_group = _ensure_terrain_doodad_sculpt_modifier_node_group(terrain_info.doodad_sculpt_modifier_name, terrain_info, terrain_doodads)
    modifiers[terrain_info.doodad_attribute_modifier_name].node_group = _ensure_terrain_doodad_attribute_modifier_node_group(terrain_info.doodad_attribute_modifier_name, terrain_info, terrain_doodads)
    modifiers[terrain_info.doodad_paint_modifier_name].node_group = _ensure_terrain_doodad_paint_modifier_node_group(terrain_info.doodad_paint_modifier_name, terrain_info, terrain_doodads)
    modifiers[terrain_info.doodad_deco_modifier_name].node_group = _ensure_terrain_doodad_deco_modifier_node_group(terrain_info.doodad_deco_modifier_name, terrain_info, terrain_doodads)
    modifiers[terrain_info.doodad_mask_modifier_name].node_group = _ensure_terrain_doodad_scatter_layer_mask_modifier_node_group(terrain_info.doodad_mask_modifier_name, terrain_info, terrain_doodads)

    # Rebuild the modifier node trees for the paint and deco layers.
    ensure_paint_layers(terrain_info_object)
    ensure_deco_layers(terrain_info_object)

    """
    Sort the modifiers on the terrain info object in the following order:
    1. Terrain Doodad Sculpt
    2. Terrain Doodad Attribute
    3. Terrain Info Paint Layer Nodes
    4. Terrain Doodad Paint Layers
    5. Terrain Info Deco Layer Nodes
    6. Terrain Doodad Deco Layers
    """

    # The modifier ID list will contain a list of modifier IDs in the order that they should be sorted.
    modifier_ids = list()
    modifier_ids.append(terrain_info.doodad_sculpt_modifier_name)
    modifier_ids.append(terrain_info.doodad_attribute_modifier_name)
    modifier_ids.extend(map(lambda paint_layer: paint_layer.id, terrain_info.paint_layers))
    modifier_ids.append(terrain_info.doodad_paint_modifier_name)
    modifier_ids.extend(map(lambda deco_layer: deco_layer.modifier_name, terrain_info.deco_layers))  # TODO: something weird going down here, we shouldn't be using the deco layer ID
    modifier_ids.append(terrain_info.doodad_deco_modifier_name)
    modifier_ids.append(terrain_info.doodad_mask_modifier_name)

    # Make note of what the current mode is so that we can restore it later.
    current_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    current_active_object = bpy.context.view_layer.objects.active

    # Make the active object the terrain info object.
    bpy.context.view_layer.objects.active = terrain_info_object

    # Set the mode to OBJECT so that we can move the modifiers.
    bpy.ops.object.mode_set(mode='OBJECT')

    # It's theoretically possible that the modifiers don't exist (e.g., having been deleted by the user, debugging etc.)
    # Get a list of missing modifiers.
    missing_modifier_ids = set(modifier_ids).difference(set(terrain_info_object.modifiers.keys()))
    # Add any missing modifiers.
    for modifier_id in missing_modifier_ids:
        if modifier_id not in bpy.data.node_groups:
            print('Missing node group: ' + modifier_id)
            continue
        modifier = terrain_info_object.modifiers.new(name=modifier_id, type='NODES')
        modifier.node_group = bpy.data.node_groups[modifier_id]
        modifier.show_on_cage = True

    # Remove any modifier IDs that do not have a corresponding modifier in the terrain info object.
    superfluous_modifier_ids = set(terrain_info_object.modifiers.keys()).difference(set(modifier_ids))

    # Remove any superfluous modifiers.
    for modifier_id in superfluous_modifier_ids:
        terrain_info_object.modifiers.remove(terrain_info_object.modifiers[modifier_id])

    modifier_ids = [x for x in modifier_ids if x in terrain_info_object.modifiers]

    # TODO: it would be nice if we could move the modifiers without needing to use the ops API, or at
    #  least suspend evaluation of the node tree while we do it.
    # TODO: we can use the data API to do this, but we need to know the index of the modifier in the list.
    # Update the modifiers on the terrain info object to reflect the new sort order.
    for i, modifier_id in enumerate(modifier_ids):
        bpy.ops.object.modifier_move_to_index(modifier=modifier_id, index=i)

    # Restore the mode and active object to what it was before.
    bpy.context.view_layer.objects.active = current_active_object

    if bpy.context.view_layer.objects.active:
        bpy.ops.object.mode_set(mode=current_mode)


def _add_terrain_info_driver(struct: bpy_struct, terrain_info: 'BDK_PG_terrain_info', data_path: str,
                             path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_info.terrain_info_object
    var.targets[0].data_path = f"bdk.terrain_info.{data_path}"

def _add_terrain_doodad_driver(struct: bpy_struct, terrain_doodad: 'BDK_PG_terrain_doodad', data_path: str,
                               path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_doodad.object
    var.targets[0].data_path = f"bdk.terrain_doodad.{data_path}"

def add_distance_to_doodad_layer_nodes(node_tree: NodeTree, layer, layer_type: str, terrain_doodad_object_info_node: Node) -> NodeSocket:
    terrain_doodad = layer.terrain_doodad_object.bdk.terrain_doodad

    if terrain_doodad.object.type == 'CURVE':

        curve_modifier_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_modifier_node.node_tree = ensure_curve_modifier_node_tree()

        distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_curve_node.node_tree = ensure_distance_to_curve_node_group()

        # Drivers
        add_doodad_layer_driver(curve_modifier_node.inputs['Is Curve Reversed'], layer, layer_type, 'is_curve_reversed')
        add_doodad_layer_driver(curve_modifier_node.inputs['Trim Mode'], layer, layer_type, 'curve_trim_mode')
        add_doodad_layer_driver(curve_modifier_node.inputs['Trim Factor Start'], layer, layer_type, 'curve_trim_factor_start')
        add_doodad_layer_driver(curve_modifier_node.inputs['Trim Factor End'], layer, layer_type, 'curve_trim_factor_end')
        add_doodad_layer_driver(curve_modifier_node.inputs['Trim Length Start'], layer, layer_type, 'curve_trim_length_start')
        add_doodad_layer_driver(curve_modifier_node.inputs['Trim Length End'], layer, layer_type, 'curve_trim_length_end')
        add_doodad_layer_driver(curve_modifier_node.inputs['Normal Offset'], layer, layer_type, 'curve_normal_offset')

        _add_terrain_doodad_driver(distance_to_curve_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        # Links
        node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'], curve_modifier_node.inputs['Curve'])
        node_tree.links.new(curve_modifier_node.outputs['Curve'], distance_to_curve_node.inputs['Curve'])

        return distance_to_curve_node.outputs['Distance']
    elif terrain_doodad.object.type == 'MESH':
        distance_to_mesh_node_group = ensure_distance_to_mesh_node_group()

        # Add a new node group node.
        distance_to_mesh_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_mesh_node.node_tree = distance_to_mesh_node_group

        node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'], distance_to_mesh_node.inputs['Geometry'])

        return distance_to_mesh_node.outputs['Distance']
    elif terrain_doodad.object.type == 'EMPTY':
        distance_to_empty_node_group = ensure_distance_to_empty_node_group()

        distance_to_empty_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_empty_node.node_tree = distance_to_empty_node_group

        node_tree.links.new(terrain_doodad_object_info_node.outputs['Location'], distance_to_empty_node.inputs['Location'])
        _add_terrain_doodad_driver(distance_to_empty_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        return distance_to_empty_node.outputs['Distance']
    else:
        raise Exception(f"Unsupported terrain doodad type: {terrain_doodad.object.type}")


def add_doodad_layer_driver(
        struct: bpy_struct,
        layer,
        layer_type: str,
        data_path: str,
        path: str = 'default_value'
):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = layer.terrain_doodad_object
    if layer_type == 'SCULPT':
        data_path = f"bdk.terrain_doodad.sculpt_layers[{layer.index}].{data_path}"
    elif layer_type == 'PAINT':
        data_path = f"bdk.terrain_doodad.paint_layers[{layer.index}].{data_path}"
    elif layer_type == 'DECO':
        data_path = f"bdk.terrain_doodad.deco_layers[{layer.index}].{data_path}"
    else:
        raise Exception(f"Unknown layer type: {layer_type}")
    var.targets[0].data_path = data_path


def add_doodad_sculpt_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'SCULPT', data_path, path)


def add_doodad_paint_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'PAINT', data_path, path)


def add_doodad_deco_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'DECO', data_path, path)


def ensure_sculpt_operation_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketFloat', 'Value 1'),
        ('INPUT', 'NodeSocketFloat', 'Value 2'),
        ('INPUT', 'NodeSocketFloat', 'Depth'),
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('OUTPUT', 'NodeSocketFloat', 'Output')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        set_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        set_socket = set_mix_node.outputs['Result']

        add_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_node.operation = 'ADD'
        add_socket = add_node.outputs['Value']

        add_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_multiply_node.operation = 'MULTIPLY'

        node_tree.links.new(input_node.outputs['Value 2'], add_multiply_node.inputs[0])
        node_tree.links.new(input_node.outputs['Depth'], add_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Value 1'], add_node.inputs[0])
        node_tree.links.new(add_multiply_node.outputs['Value'], add_node.inputs[1])
        node_tree.links.new(input_node.outputs['Value 2'], set_mix_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Value 1'], set_mix_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Depth'], set_mix_node.inputs['B'])

        operation_result_socket = add_geometry_node_switch_nodes(node_tree, input_node.outputs['Operation'], [add_socket, set_socket], 'FLOAT')

        node_tree.links.new(operation_result_socket, output_node.inputs['Output'])

    return ensure_geometry_node_tree('BDK Sculpt Operation', items, build_function)


def add_terrain_doodad_sculpt_layer_value_nodes(node_tree: NodeTree, sculpt_layer: 'BDK_PG_terrain_doodad_sculpt_layer') -> NodeSocket:
    sculpt_value_node = node_tree.nodes.new(type='GeometryNodeGroup')
    sculpt_value_node.node_tree = ensure_sculpt_value_node_group()

    doodad_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    doodad_object_info_node.inputs[0].default_value = sculpt_layer.terrain_doodad_object
    doodad_object_info_node.transform_space = 'RELATIVE'

    # Add the distance to the doodad layer nodes.
    distance_socket = add_distance_to_doodad_layer_nodes(node_tree, sculpt_layer, 'SCULPT', doodad_object_info_node)

    # Drivers
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Radius'], sculpt_layer, 'radius')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Falloff Radius'], sculpt_layer, 'falloff_radius')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Noise Strength'], sculpt_layer, 'noise_strength')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Perlin Noise Roughness'], sculpt_layer,
                                   'perlin_noise_roughness')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Perlin Noise Distortion'], sculpt_layer,
                                   'perlin_noise_distortion')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Perlin Noise Scale'], sculpt_layer, 'perlin_noise_scale')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Perlin Noise Lacunarity'], sculpt_layer,
                                   'perlin_noise_lacunarity')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Perlin Noise Detail'], sculpt_layer, 'perlin_noise_detail')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Use Noise'], sculpt_layer, 'use_noise')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Noise Radius Factor'], sculpt_layer, 'noise_radius_factor')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Interpolation Type'], sculpt_layer, 'interpolation_type')
    add_doodad_sculpt_layer_driver(sculpt_value_node.inputs['Noise Type'], sculpt_layer, 'noise_type')

    node_tree.links.new(distance_socket, sculpt_value_node.inputs['Distance'])

    return sculpt_value_node.outputs['Value']


def _add_sculpt_layers_to_node_tree(node_tree: NodeTree, z_socket: NodeSocket, terrain_doodad) -> NodeSocket:
    """
    Adds the nodes for a doodad's sculpt layers.
    :param node_tree: The node tree to add the nodes to.
    :param geometry_socket: The geometry socket to connect the nodes to.
    :param terrain_doodad: The terrain doodad to add the sculpt layers for.
    :return: The geometry output socket (either the one passed in or the one from the last node added).
    """
    # Now chain the node components together.
    for sculpt_layer in terrain_doodad.sculpt_layers:
        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'FLOAT'

        frozen_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        frozen_named_attribute_node.inputs['Name'].default_value = sculpt_layer.frozen_attribute_id

        is_frozen_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        is_frozen_switch_node.input_type = 'FLOAT'

        # TODO: combine this into a single node group.
        value_socket = add_terrain_doodad_sculpt_layer_value_nodes(node_tree, sculpt_layer)

        sculpt_operation_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sculpt_operation_node.node_tree = ensure_sculpt_operation_node_group()

        # Drivers
        add_doodad_sculpt_layer_driver(mute_switch_node.inputs[0], sculpt_layer, 'mute')
        add_doodad_sculpt_layer_driver(is_frozen_switch_node.inputs['Switch'], sculpt_layer, 'is_frozen')
        add_doodad_sculpt_layer_driver(sculpt_operation_node.inputs['Operation'], sculpt_layer, 'operation')
        add_doodad_sculpt_layer_driver(sculpt_operation_node.inputs['Depth'], sculpt_layer, 'depth')

        # Links
        node_tree.links.new(sculpt_operation_node.outputs['Output'], mute_switch_node.inputs[2])
        node_tree.links.new(z_socket, mute_switch_node.inputs[3])
        node_tree.links.new(value_socket, is_frozen_switch_node.inputs[2])  # False
        node_tree.links.new(frozen_named_attribute_node.outputs[1], is_frozen_switch_node.inputs[3])  # True
        node_tree.links.new(z_socket, sculpt_operation_node.inputs['Value 1'])
        node_tree.links.new(is_frozen_switch_node.outputs[0], sculpt_operation_node.inputs['Value 2'])

        z_socket = mute_switch_node.outputs['Output']

    return z_socket


def _ensure_terrain_doodad_sculpt_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

        z_socket = separate_xyz_node.outputs['Z']

        for terrain_doodad in terrain_doodads:
            ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad)
            z_socket = _add_sculpt_layers_to_node_tree(node_tree, z_socket, terrain_doodad)

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(z_socket, combine_xyz_node.inputs['Z'])

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        node_tree.links.new(combine_xyz_node.outputs['Vector'], set_position_node.inputs['Position'])
        node_tree.links.new(geometry_socket, set_position_node.inputs['Geometry'])

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs[1], terrain_info, 'is_sculpt_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs[15])  # True (muted)

        # Internal
        node_tree.links.new(set_position_node.outputs['Geometry'], mute_switch_node.inputs[14])  # False (not muted)

        # Outputs
        node_tree.links.new(mute_switch_node.outputs[6], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def terrain_doodad_scatter_layer_mask_node_data_path_get(dataptr_name: str, dataptr_index: int, node_index: int, property_name: str, index: Optional[int] = None) -> str:
    if index is not None:
        return f'bdk.terrain_doodad.{dataptr_name}[{dataptr_index}].mask_nodes[{node_index}].{property_name}[{index}]'
    else:
        return f'bdk.terrain_doodad.{dataptr_name}[{dataptr_index}].mask_nodes[{node_index}].{property_name}'


def _add_terrain_doodad_scatter_layer_mask_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket, scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeSocket:
    density_socket = add_density_from_terrain_layer_nodes(
        node_tree,
        scatter_layer.terrain_doodad_object,
        'scatter_layers', scatter_layer.index, scatter_layer.mask_nodes, terrain_doodad_scatter_layer_mask_node_data_path_get)

    return geometry_socket


def _add_terrain_doodad_paint_layer_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket,
                                                 terrain_doodad_paint_layer: 'BDK_PG_terrain_doodad_paint_layer',
                                                 attribute_override: Optional[str] = None,
                                                 operation_override: Optional[str] = None) -> NodeSocket:

    # Check if the terrain doodad is frozen.
    if terrain_doodad_paint_layer.terrain_doodad_object.bdk.terrain_doodad.is_frozen:
        pass

    def add_paint_layer_driver(struct: bpy_struct, paint_layer: 'BDK_PG_terrain_doodad_paint_layer', data_path: str,
                               path: str = 'default_value'):
        driver = struct.driver_add(path).driver
        driver.type = 'AVERAGE'
        var = driver.variables.new()
        var.name = data_path
        var.type = 'SINGLE_PROP'
        var.targets[0].id = paint_layer.terrain_doodad_object
        var.targets[0].data_path = f"bdk.terrain_doodad.paint_layers[{paint_layer.index}].{data_path}"

    doodad_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    doodad_object_info_node.inputs[0].default_value = terrain_doodad_paint_layer.terrain_doodad_object
    doodad_object_info_node.transform_space = 'RELATIVE'

    distance_socket = add_distance_to_doodad_layer_nodes(node_tree, terrain_doodad_paint_layer, 'PAINT', doodad_object_info_node)

    store_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_distance_attribute_node.inputs['Name'].default_value = terrain_doodad_paint_layer.id
    store_distance_attribute_node.data_type = 'FLOAT'
    store_distance_attribute_node.domain = 'POINT'

    node_tree.links.new(geometry_socket, store_distance_attribute_node.inputs['Geometry'])

    geometry_socket = store_distance_attribute_node.outputs['Geometry']

    paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
    paint_node.node_tree = ensure_doodad_paint_node_group()
    paint_node.label = 'Paint'

    if attribute_override is not None:
        paint_node.inputs['Attribute'].default_value = attribute_override
    else:
        # These attributes are not pre-calculated anymore, so we need to do it here.
        if terrain_doodad_paint_layer.layer_type == 'PAINT':
            paint_node.inputs['Attribute'].default_value = terrain_doodad_paint_layer.paint_layer_id
        elif terrain_doodad_paint_layer.layer_type == 'DECO':
            paint_node.inputs['Attribute'].default_value = terrain_doodad_paint_layer.deco_layer_id
        elif terrain_doodad_paint_layer.layer_type == 'ATTRIBUTE':
            paint_node.inputs['Attribute'].default_value = terrain_doodad_paint_layer.attribute_layer_id

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'GEOMETRY'

    add_paint_layer_driver(switch_node.inputs[1], terrain_doodad_paint_layer, 'mute')
    add_paint_layer_driver(paint_node.inputs['Radius'], terrain_doodad_paint_layer, 'radius')
    add_paint_layer_driver(paint_node.inputs['Falloff Radius'], terrain_doodad_paint_layer, 'falloff_radius')
    add_paint_layer_driver(paint_node.inputs['Strength'], terrain_doodad_paint_layer, 'strength')
    add_paint_layer_driver(paint_node.inputs['Use Distance Noise'], terrain_doodad_paint_layer, 'use_distance_noise')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Distortion'], terrain_doodad_paint_layer, 'distance_noise_distortion')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Factor'], terrain_doodad_paint_layer, 'distance_noise_factor')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Offset'], terrain_doodad_paint_layer, 'distance_noise_offset')
    add_paint_layer_driver(paint_node.inputs['Interpolation Type'], terrain_doodad_paint_layer, 'interpolation_type')

    if operation_override is not None:
        # Handle operation override. This is used when baking.
        operation_keys = [item[0] for item in terrain_doodad_operation_items]
        paint_node.inputs['Operation'].default_value = operation_keys.index(operation_override)
    else:
        add_paint_layer_driver(paint_node.inputs['Operation'], terrain_doodad_paint_layer, 'operation')

    add_paint_layer_driver(paint_node.inputs['Noise Type'], terrain_doodad_paint_layer, 'noise_type')

    node_tree.links.new(geometry_socket, paint_node.inputs['Geometry'])
    node_tree.links.new(distance_socket, paint_node.inputs['Distance'])
    node_tree.links.new(paint_node.outputs['Geometry'], switch_node.inputs[14])  # False (not muted)
    node_tree.links.new(geometry_socket, switch_node.inputs[15])  # True (muted)

    return switch_node.outputs[6]  # Output


def _ensure_terrain_doodad_paint_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'PAINT', terrain_doodad.paint_layers):
                geometry_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs[1], terrain_info, 'is_paint_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs[15])  # True (muted)

        # Internal
        node_tree.links.new(geometry_socket, mute_switch_node.inputs[14])  # False (not muted)

        # Outputs
        node_tree.links.new(mute_switch_node.outputs[6], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def _ensure_terrain_doodad_deco_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'DECO', terrain_doodad.paint_layers):
                geometry_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)

def _ensure_terrain_doodad_scatter_layer_mask_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for scatter_layer in terrain_doodad.scatter_layers:
                geometry_socket = _add_terrain_doodad_scatter_layer_mask_to_node_tree(node_tree, geometry_socket, scatter_layer)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)

def _ensure_terrain_doodad_attribute_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'ATTRIBUTE', terrain_doodad.paint_layers):
                geometry_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs[1], terrain_info, 'is_attribute_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs[15])  # True (muted)

        # Internal
        node_tree.links.new(geometry_socket, mute_switch_node.inputs[14])  # False (not muted)

        # Outputs
        node_tree.links.new(mute_switch_node.outputs[6], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def create_terrain_doodad_bake_node_tree(terrain_doodad: 'BDK_PG_terrain_doodad', layers: Set[str]) -> (NodeTree, Dict[str, str]):
    """
    Creates a node tree for baking a terrain doodad.
    :param terrain_doodad: The terrain doodad to make a baking node tree for.
    :return: The terrain doodad baking node tree and a mapping of the paint layer IDs to the baked attribute names.
    """
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry')
    }

    # Build a mapping of the paint layer IDs to the baked attribute names.
    attribute_map: Dict[str, str] = {}
    for paint_layer in terrain_doodad.paint_layers:
        attribute_map[paint_layer.id] = uuid4().hex

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        if 'SCULPT' in layers:
            # Add sculpt layers for the doodad.
            geometry_socket = _add_sculpt_layers_to_node_tree(node_tree, geometry_socket, terrain_doodad)

        # Add the paint layers for the doodad.
        if 'PAINT' in layers:
            for doodad_paint_layer in terrain_doodad.paint_layers:
                attribute_name = attribute_map[doodad_paint_layer.id]
                # We override the operation here because we want the influence of each layer to be additive for the bake.
                # Without this, if a "SUBTRACT" operation were used, the resulting bake for the attribute would be
                # completely black (painted with 0). The actual operation will be transferred to the associated node in the
                # layer node tree.
                # TODO: Ideally, we would not need these overrides because it is a little hacky. It would be cleaner to
                #  separate out the operation from the "Paint Layer" node group, although we would need a compelling reason
                #  to do so.
                geometry_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, geometry_socket, doodad_paint_layer,
                                                                               attribute_override=attribute_name,
                                                                               operation_override='ADD')

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    node_tree = ensure_geometry_node_tree(uuid.uuid4().hex, items, build_function, should_force_build=True)

    return node_tree, attribute_map


def ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad: 'BDK_PG_terrain_doodad'):
    """
    Ensures that all the freeze attribute IDs are set for the given terrain doodad.
    :param terrain_doodad:
    :return:
    """
    for sculpt_layer in terrain_doodad.sculpt_layers:
        if sculpt_layer.frozen_attribute_id == '':
            sculpt_layer.frozen_attribute_id = uuid4().hex


def ensure_terrain_doodad_freeze_node_group(terrain_doodad: 'BDK_PG_terrain_doodad') -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad)

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        # Now chain the node components together.
        for sculpt_layer in terrain_doodad.sculpt_layers:
            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.inputs['Name'].default_value = sculpt_layer.frozen_attribute_id

            value_socket = add_terrain_doodad_sculpt_layer_value_nodes(node_tree, sculpt_layer)

            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])
            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(f'BDK Terrain Doodad Freeze {terrain_doodad.id}', items, build_function, should_force_build=True)
