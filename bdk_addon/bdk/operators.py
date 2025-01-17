from collections import OrderedDict
from pathlib import Path
from typing import Set, cast

import bpy
from bpy.types import Operator, Context, Node, Event, Armature, Mesh
from bpy.props import StringProperty

from ..helpers import get_addon_preferences, tag_redraw_all_windows


# TODO: figure out a better name for this operator
class BDK_OT_select_all_of_active_class(Operator):
    bl_idname = 'bdk.select_all_of_active_class'
    bl_label = 'Select All Of Active Class'
    bl_description = 'Select all static mesh actors in the scene'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Return false if no doodad are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No doodad selected')
            return False
        # Return false if the active object does not have a class.
        if 'Class' not in context.object:
            cls.poll_message_set('Active object does not have a class')
            return False
        return True

    def execute(self, context):
        # Get the class of the active object.
        actor_class = context.object['Class']
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj.get('Class', None) == actor_class:
                obj.select_set(True)
        return {'FINISHED'}


class BDK_OT_force_node_tree_rebuild(Operator):
    bl_idname = 'bdk.force_node_tree_rebuild'
    bl_label = 'Force BDK Node Tree Rebuild'
    bl_description = 'Force all BDK node trees to be rebuilt'
    bl_options = {'REGISTER'}

    def execute(self, context: Context):
        for node_tree in bpy.data.node_groups:
            node_tree.bdk.build_hash = ''
        return {'FINISHED'}


class BDK_OT_generate_node_code(Operator):
    bl_idname = 'bdk.generate_node_code'
    bl_label = 'Generate Node Code'
    bl_description = 'Generate code for the selected nodes'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # Return true if we are currently in the node editor.
        if context.area.type != 'NODE_EDITOR':
            cls.poll_message_set('Not in node editor')
            return False
        return True

    def execute(self, context: Context):
        selected_nodes = context.selected_nodes
        nodes: OrderedDict[str, Node] = OrderedDict()

        for node in selected_nodes:
            if node.label:
                variable_name = node.label.replace(' ', '_').lower()
            else:
                variable_name = node.bl_label.replace(' ', '_').lower()
            variable_name += '_node'

            # Avoid name collisions by appending a number to the variable name.
            # If the variable already has a number appended, increment it.
            if variable_name in nodes:
                i = 1
                while f'{variable_name}_{i}' in nodes:
                    i += 1
                variable_name = f'{variable_name}_{i}'

            nodes[variable_name] = node

        lines = []

        for variable_name, node in nodes.items():
            lines.append(f'{variable_name} = node_tree.nodes.new(type=\'{node.bl_idname}\')')
            # If a label is set, set it.
            if node.label:
                lines.append(f'{variable_name}.label = \'{node.label}\'')

            # For any of the node's properties that are not default, set them.
            for property_name, property_meta in node.bl_rna.properties.items():
                if property_meta.is_readonly:
                    continue
                if property_name.startswith('bl_'):
                    continue
                # Ignore PointerProperty properties.
                if property_meta.type == 'POINTER':
                    continue
                if property_name in ('name', 'label', 'location', 'width', 'height', 'name', 'color', 'select', 'show_options', 'is_active_output'):
                    continue
                if getattr(node, property_name) != property_meta.default:  # TODO: the default value is not always correct.
                    value = getattr(node, property_name)
                    if isinstance(value, str):
                        value = f'\'{value}\''
                    print(property_name, type(value), value)
                    lines.append(f'{variable_name}.{property_name} = {value}')
                else:
                    print('default', property_meta.default, getattr(node, property_name))

            # Check if the node has any input sockets whose default value doesn't match the default value of the socket
            # type.
            for socket in node.inputs:
                if socket.is_linked or socket.is_unavailable:
                    continue
                # TODO: this is imprecise but should work for now
                if hasattr(socket, 'default_value') and socket.default_value:
                    default_value = socket.default_value
                    if type(socket.default_value) == str:
                        default_value = f'\'{default_value}\''
                    # TODO: other types are too much of a pain to handle right now
                    lines.append(f'{variable_name}.inputs[\'{socket.name}\'].default_value = {default_value}')

            lines.append('')

        # Get all the links between the selected nodes.
        links = set()
        for variable_name, node in nodes.items():
            for input_ in node.inputs:
                if input_.is_linked:
                    for link in input_.links:
                        links.add(link)
            for output in node.outputs:
                if output.is_linked:
                    for link in output.links:
                        links.add(link)

        internal_links = []
        incoming_links = []
        outgoing_links = []

        for link in links:
            from_node = link.from_node
            to_node = link.to_node

            from_variable_name = None
            from_socket_index = None
            to_variable_name = None
            to_socket_index = None

            if from_node and from_node in selected_nodes:
                # Get variable names for the nodes.
                for variable_name, node in nodes.items():
                    if node == from_node:
                        from_variable_name = variable_name
                        break
                # Get the index of the "from" socket.
                from_socket_index = link.from_socket.identifier

            if to_node and to_node in selected_nodes:
                for variable_name, node in nodes.items():
                    if node == to_node:
                        to_variable_name = variable_name
                        break
                # Get the index of the "to" socket.
                to_socket_index = link.to_socket.identifier

            if from_variable_name and from_socket_index is not None and to_variable_name and to_socket_index is not None:
                internal_links.append((link, from_variable_name, from_socket_index, to_variable_name, to_socket_index))
            elif from_variable_name and from_socket_index is not None and not to_variable_name and to_socket_index is None:
                outgoing_links.append((link, from_variable_name, from_socket_index))
            elif not from_variable_name and from_socket_index is None and to_variable_name and to_socket_index is not None:
                incoming_links.append((link, to_variable_name, to_socket_index))

        if internal_links:
            lines.append('')
            lines.append('# Links')
            for (link, from_variable_name, from_socket_index, to_variable_name, to_socket_index) in internal_links:
                lines.append(f'node_tree.links.new({from_variable_name}.outputs[\'{link.from_socket.name}\'], {to_variable_name}.inputs[\'{link.to_socket.name}\'])')

        if incoming_links:
            lines.append('')
            lines.append('# Incoming Links')
            for (link, to_variable_name, to_socket_index) in incoming_links:
                lines.append(f'# {to_variable_name}.inputs[\'{link.to_socket.name}\']')

        if outgoing_links:
            lines.append('')
            lines.append('# Outgoing Links')
            for (link, from_variable_name, from_socket_index) in outgoing_links:
                lines.append(f'# {from_variable_name}.outputs[\'{link.from_socket.name}\']')

        # Copy the lines to the clipboard.
        context.window_manager.clipboard = '\n'.join(lines)

        return {'FINISHED'}


def vertex_group_name_search_cb(self, context: Context, edit_text: str):
    # List all the bones in the armature.
    armature_object = context.object
    armature_data: Armature = cast(Armature, armature_object.data)
    return [bone.name for bone in armature_data.bones if edit_text.lower() in bone.name.lower()]


class BDK_OT_assign_all_vertices_to_vertex_group_and_add_armature_modifier(Operator):
    bl_idname = 'bdk.assign_all_vertices_to_vertex_group'
    bl_label = 'Assign All Vertices To Vertex Group'
    bl_description = 'Assign all vertices to a vertex group'
    bl_options = {'REGISTER', 'UNDO'}

    vertex_group_name: StringProperty(name='Vertex Group Name', search=vertex_group_name_search_cb)

    @classmethod
    def poll(cls, context):
        # Return true if the active object is a mesh.
        if context.object is None:
            cls.poll_message_set('No active object')
            return False
        if context.object.type != 'ARMATURE':
            cls.poll_message_set('Active object is not an armature')
            return False
        return True

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: 'Context'):
        layout = self.layout
        layout.prop(self, 'vertex_group_name')

    def execute(self, context):
        # For all selected objects:
        armature_object = context.object
        for bpy_object in context.selected_objects:
            if bpy_object.type != 'MESH':
                continue
            # Create a vertex group if it doesn't exist.
            vertex_group = bpy_object.vertex_groups.get(self.vertex_group_name, None)
            if vertex_group is None:
                vertex_group = bpy_object.vertex_groups.new(name=self.vertex_group_name)
            # Add all vertices to the vertex group.
            mesh_data = cast(Mesh, bpy_object.data)
            vertex_group.add(range(len(mesh_data.vertices)), 1.0, 'REPLACE')
            # Add an armature modifier if it doesn't exist.
            armature_modifier = bpy_object.modifiers.get('Armature', None)
            if armature_modifier is None:
                armature_modifier = bpy_object.modifiers.new(name='Armature', type='ARMATURE')
                armature_modifier.object = armature_object
        return {'FINISHED'}


class BDK_OT_node_join_group_input_nodes(Operator):
    bl_label = "Join Group Input Nodes"
    bl_idname = "bdk.node_join_group_input_nodes"
    bl_description = "Join all group input nodes into a single node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not hasattr(context, 'active_node') or context.active_node is None:
            cls.poll_message_set('A node must be active')
            return False
        if context.active_node.bl_idname != 'NodeGroupInput':
            cls.poll_message_set('The active node must be a group input node')
            return False
        return True

    def execute(self, context):
        # Get the selected nodes in the node editor.
        node_tree = context.space_data.edit_tree
        active_node = context.active_node

        # Iterate over the selected nodes that are group input nodes.
        group_input_nodes = list(filter(lambda node: node.bl_idname == 'NodeGroupInput' and node != active_node, context.selected_nodes))

        # TODO: doesn't seem to work in nested groups

        # Reroute the links from the group input nodes to the active node.
        new_links = []
        for group_input_node in group_input_nodes:
            for output in filter(lambda x: x.is_linked, group_input_node.outputs):
                for link in output.links:
                    new_links.append((active_node.outputs[link.from_socket.name], link.to_socket))

            node_tree.nodes.remove(group_input_node)

        # Create the new links.
        for (from_socket, to_socket) in new_links:
            node_tree.links.new(from_socket, to_socket)

        node_tree.update_tag()

        return {'FINISHED'}


class BDK_OT_node_split_group_input_nodes(Operator):
    bl_label = "Split Group Input Nodes"
    bl_idname = "bdk.node_split_group_input_nodes"
    bl_description = "Split a group input node into multiple nodes, one for each node that is linked to it"

    @classmethod
    def poll(cls, context: Context):
        if not hasattr(context, 'active_node') or context.active_node is None:
            cls.poll_message_set('A node must be active')
            return False
        if context.active_node.bl_idname != 'NodeGroupInput':
            cls.poll_message_set('The active node must be a group input node')
            return False
        return True

    def execute(self, context: Context):
        node_tree = context.space_data.edit_tree
        active_node = context.active_node
        location = active_node.location.copy()

        # Create new input nodes for each node link.
        node_input_nodes = dict()
        for output in filter(lambda output: output.is_linked, active_node.outputs):
            for link in output.links:
                if link.to_node not in node_input_nodes:
                    if len(node_input_nodes) == 0:
                        input_node = active_node
                    else:
                        input_node = node_tree.nodes.new(type='NodeGroupInput')
                    input_node.location = location
                    location[1] -= 100
                    node_input_nodes[link.to_node] = input_node
                else:
                    input_node = node_input_nodes[link.to_node]
                node_tree.links.new(input_node.outputs[link.from_socket.name], link.to_socket)

        # Hide unlinked sockets for the new input nodes.
        for input_node in node_input_nodes.values():
            for socket in input_node.outputs:
                if not socket.is_linked:
                    socket.hide = True

        # TODO: instead, keep the active node, that way we don't need to reselect anything.

        return {'FINISHED'}


class BDK_OT_toggle_level_visibility(Operator):
    bl_idname = 'bdk.toggle_level_visibility'
    bl_label = 'Toggle Level Visibility'
    bl_description = 'Toggle the visibility of the level object'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context: Context):
        return context.scene.bdk.level_object is not None

    def execute(self, context: Context):
        context.scene.bdk.level_object.hide_viewport = not context.scene.bdk.level_object.hide_viewport
        return {'FINISHED'}


class BDK_OT_asset_import_data_linked(Operator):
    bl_idname = 'bdk_asset_browser.import_data_linked'
    bl_description = 'Link asset from a library'
    bl_label = 'Import Data (Linked)'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context: 'Context'):
        assets = context.selected_assets
        if len(assets) == 0:
            cls.poll_message_set('No assets selected')
            return False
        if any(map(lambda asset: asset.id_type != 'MATERIAL', assets)):
            cls.poll_message_set('Only materials can be imported')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        library_path: Path
        assets = context.selected_assets

        linked_count = 0
        skipped_count = 0

        for asset in assets:
            if asset.local_id is not None:
                # Asset is local to this file.
                skipped_count += 1
                continue

            with bpy.data.libraries.load(asset.full_library_path, link=True) as (data_from, data_to):
                match asset.id_type:
                    case 'MATERIAL':
                        data_to.materials = [asset.name]

            linked_count += 1

        self.report({'INFO'}, f'Linked {linked_count} | Skipped {skipped_count}')

        return {'FINISHED'}


class BDK_OT_scene_repository_set(Operator):
    bl_idname = 'bdk.scene_repository_set'
    bl_label = 'Set Scene Repository'
    bl_description = 'Set the repository for the current scene'
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context: Context):
        addon_prefs = get_addon_preferences(context)
        repository = addon_prefs.repositories[addon_prefs.repositories_index]

        context.scene.bdk.repository_id = repository.id

        self.report({'INFO'}, f'Scene repository set to {repository.name}')

        tag_redraw_all_windows(context)

        return {'FINISHED'}


classes = (
    BDK_OT_select_all_of_active_class,
    BDK_OT_generate_node_code,
    BDK_OT_force_node_tree_rebuild,
    BDK_OT_assign_all_vertices_to_vertex_group_and_add_armature_modifier,
    BDK_OT_node_join_group_input_nodes,
    BDK_OT_node_split_group_input_nodes,
    BDK_OT_asset_import_data_linked,
    BDK_OT_toggle_level_visibility,
    BDK_OT_scene_repository_set,
)
