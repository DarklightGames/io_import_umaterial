from typing import Optional, Iterable, AbstractSet, Tuple

import bpy
from bpy.types import NodeTree, NodeSocket, Node


def add_operation_switch_nodes(
        node_tree: NodeTree,
        operation_socket: NodeSocket,
        value_1_socket: Optional[NodeSocket],
        value_2_socket: Optional[NodeSocket],
        operations: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, operation in enumerate(operations):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(operation_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = operation
        math_node.inputs[0].default_value = 0.0
        math_node.inputs[1].default_value = 0.0

        if value_1_socket:
            node_tree.links.new(value_1_socket, math_node.inputs[0])

        if value_2_socket:
            node_tree.links.new(value_2_socket, math_node.inputs[1])

        node_tree.links.new(math_node.outputs['Value'], switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def add_interpolation_type_switch_nodes(
        node_tree: NodeTree,
        interpolation_type_socket: NodeSocket,
        value_socket: NodeSocket,
        interpolation_types: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, interpolation_type in enumerate(interpolation_types):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(interpolation_type_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
        map_range_node.data_type = 'FLOAT'
        map_range_node.interpolation_type = interpolation_type
        map_range_node.inputs[3].default_value = 1.0  # To Min
        map_range_node.inputs[4].default_value = 0.0  # To Max

        node_tree.links.new(value_socket, map_range_node.inputs[0])
        node_tree.links.new(map_range_node.outputs[0], switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def add_noise_type_switch_nodes(
        node_tree: NodeTree,
        vector_socket: NodeSocket,
        noise_type_socket: NodeSocket,
        noise_distortion_socket: Optional[NodeSocket],
        noise_roughness_socket: Optional[NodeSocket],
) -> NodeSocket:

    """
    Adds a noise type node setup to the node tree.
    :param node_tree: The node tree to add the nodes to.
    :param vector_socket: The node socket that has the vector value.
    :param noise_type_socket: The node socket that has the noise type value.
    :param noise_distortion_socket: The node socket for the noise distortion value.
    :param noise_roughness_socket:
    :return: The noise value node socket.
    """

    noise_types = ['PERLIN', 'WHITE']

    last_output_node_socket: Optional[NodeSocket] = None

    for index, noise_type in enumerate(noise_types):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(noise_type_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        noise_value_socket = None

        if noise_type == 'PERLIN':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
            noise_node.noise_dimensions = '2D'
            noise_node.inputs['Scale'].default_value = 0.5
            noise_node.inputs['Detail'].default_value = 16
            noise_node.inputs['Distortion'].default_value = 0.5

            if noise_distortion_socket:
                node_tree.links.new(noise_distortion_socket, noise_node.inputs['Distortion'])

            if noise_roughness_socket:
                node_tree.links.new(noise_roughness_socket, noise_node.inputs['Roughness'])

            node_tree.links.new(vector_socket, noise_node.inputs['Vector'])
            noise_value_socket = noise_node.outputs['Fac']
        elif noise_type == 'WHITE':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexWhiteNoise')
            noise_node.noise_dimensions = '2D'
            noise_value_socket = noise_node.outputs['Value']

        node_tree.links.new(noise_value_socket, switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def ensure_geometry_node_tree(name: str, inputs: AbstractSet[Tuple[str, str]],
                              outputs: AbstractSet[Tuple[str, str]]) -> NodeTree:
    """
    Ensures that a geometry node tree with the given name, inputs and outputs exists.
    """
    return ensure_node_tree(name, 'GeometryNodeTree', inputs, outputs)


def ensure_shader_node_tree(
    name: str, inputs: AbstractSet[Tuple[str, str]], outputs: AbstractSet[Tuple[str, str]]) -> NodeTree:
    """
    Ensures that a shader node tree with the given name, inputs and outputs exists.
    """
    return ensure_node_tree(name, 'ShaderNodeTree', inputs, outputs)


def ensure_node_tree(name: str, node_group_type: str, inputs: AbstractSet[Tuple[str, str]],
                     outputs: AbstractSet[Tuple[str, str]]) -> NodeTree:
    """
    Ensures that a node tree with the given name, type, inputs and outputs exists.
    """
    if name in bpy.data.node_groups:
        node_tree = bpy.data.node_groups[name]
    else:
        node_tree = bpy.data.node_groups.new(name=name, type=node_group_type)

    # Compare the inputs and outputs of the node tree with the given inputs and outputs.
    # If they are different, clear the inputs and outputs and add the new ones.
    node_tree_inputs = set(map(lambda x: (x.bl_socket_idname, x.name), node_tree.inputs))
    node_tree_outputs = set(map(lambda x: (x.bl_socket_idname, x.name), node_tree.outputs))

    # For inputs that do not exist in the node tree, add them.
    for input_type, input_name in inputs - node_tree_inputs:
        node_tree.inputs.new(input_type, input_name)

    # For inputs that exist in the node tree but not in the given inputs, remove them.
    for input_type, input_name in node_tree_inputs - inputs:
        node_tree.inputs.remove(node_tree.inputs[input_name])

    # For outputs that do not exist in the node tree, add them.
    for output_type, output_name in outputs - node_tree_outputs:
        node_tree.outputs.new(output_type, output_name)

    # For outputs that exist in the node tree but not in the given outputs, remove them.
    for output_type, output_name in node_tree_outputs - outputs:
        node_tree.outputs.remove(node_tree.outputs[output_name])

    node_tree.nodes.clear()

    return node_tree


def ensure_input_and_output_nodes(node_tree: NodeTree) -> Tuple[Node, Node]:
    """
    Ensures that the node tree has input and output nodes.
    :param node_tree: The node tree to check and potentially add input and output nodes to.
    :return: The input and output nodes.
    """

    # Check if the node tree already has input and output nodes.
    # If it does, return them.
    input_node = None
    output_node = None
    for node in node_tree.nodes:
        if node.bl_idname == 'NodeGroupInput':
            input_node = node
        elif node.bl_idname == 'NodeGroupOutput':
            output_node = node

    input_node = node_tree.nodes.new(type='NodeGroupInput') if input_node is None else input_node
    output_node = node_tree.nodes.new(type='NodeGroupOutput') if output_node is None else output_node

    return input_node, output_node


def ensure_curve_normal_offset_node_tree() -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Curve'), ('NodeSocketFloat', 'Normal Offset')}
    outputs = {('NodeSocketGeometry', 'Curve')}
    node_tree = ensure_geometry_node_tree('BDK Offset Curve Normal', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add Set Position Node
    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    # Add Resample Curve node.
    resample_curve_node = node_tree.nodes.new(type='GeometryNodeResampleCurve')
    resample_curve_node.mode = 'EVALUATED'

    # Add Vector Scale node.
    vector_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vector_scale_node.operation = 'SCALE'

    # Add Input Normal node.
    input_normal_node = node_tree.nodes.new(type='GeometryNodeInputNormal')

    # Add Switch node.
    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'GEOMETRY'

    # Add Compare node.
    compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_node.operation = 'EQUAL'

    node_tree.links.new(input_node.outputs['Normal Offset'], compare_node.inputs[0])  # A
    node_tree.links.new(input_node.outputs['Normal Offset'], vector_scale_node.inputs[3])  # Scale
    node_tree.links.new(input_node.outputs['Curve'], resample_curve_node.inputs['Curve'])
    node_tree.links.new(resample_curve_node.outputs['Curve'], set_position_node.inputs['Geometry'])

    node_tree.links.new(input_normal_node.outputs['Normal'], vector_scale_node.inputs[0])
    node_tree.links.new(input_node.outputs['Normal Offset'], vector_scale_node.inputs[1])

    node_tree.links.new(input_node.outputs['Curve'], switch_node.inputs[15])  # True
    node_tree.links.new(set_position_node.outputs['Geometry'], switch_node.inputs[14])  # False
    node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs[1])  # Switch

    node_tree.links.new(vector_scale_node.outputs['Vector'], set_position_node.inputs['Offset'])
    node_tree.links.new(switch_node.outputs[6], output_node.inputs['Curve'])

    return node_tree


# def ensure_curve_extend_node_tree() -> NodeTree:
#     inputs = {('NodeSocketGeometry', 'Geometry'), ('NodeSocketFloat', 'Root Length'), ('NodeSocketFloat', 'Tip Length')}
#     outputs = {('NodeSocketGeometry', 'Geometry')}
#     node_tree = ensure_geometry_node_tree('BDK Extend Curve', inputs, outputs)
#     input_node, output_node = ensure_input_and_output_nodes(node_tree)
#
#     # Add Mesh to Curve node.
#     mesh_to_curve_node = node_tree.nodes.new(type='GeometryNodeMeshToCurve')
#     node_tree.links.new(mesh_to_curve_node.outputs['Curve'], output_node.inputs['Geometry'])
#
#     # Create a Curve tip and Curve root node group. (don't reuse the assets since they can change underfoot)
#
#     # Add Set Position nodes.
#     tip_set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
#     root_set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
#
#     # Add Curve Tip node group node.
#     curve_tip_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
#     curve_tip_node_group_node.node_tree = bpy.data.
