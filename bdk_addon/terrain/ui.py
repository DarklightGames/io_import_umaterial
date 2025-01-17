from bpy.types import Panel, UIList, UILayout, AnyType, Menu, Modifier
from typing import Optional, Any

from .properties import node_type_icons
from .context import has_terrain_paint_layer_selected, get_selected_terrain_paint_layer, get_selected_deco_layer, has_deco_layer_selected
from .operators import *
from ..helpers import is_active_object_terrain_info, get_terrain_info, should_show_bdk_developer_extras


class BDK_PT_terrain_info(Panel):
    bl_idname = 'BDK_PT_terrain_info'
    bl_label = 'Terrain Info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_INFO'

    def draw(self, context: Context):
        pass


class BDK_PT_terrain_info_advanced(Panel):
    bl_idname = 'BDK_PT_terrain_info_advanced'
    bl_label = 'Advanced'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 4

    def draw(self, context: Context):
        layout = self.layout

        terrain_info = get_terrain_info(context.active_object)
        layout = self.layout
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(terrain_info, 'terrain_scale_z')
        flow.prop(terrain_info, 'max_elevation')
        flow.prop(terrain_info, 'heightmap_resolution')
        self.layout.operator(BDK_OT_terrain_info_repair.bl_idname, icon='FILE_REFRESH', text='Repair')
        self.layout.operator(BDK_OT_terrain_info_shift.bl_idname, icon='TRANSFORM_ORIGINS', text='Shift')
        self.layout.operator(BDK_OT_terrain_info_heightmap_import.bl_idname, icon='IMPORT', text='Import Heightmap')
        self.layout.operator(BDK_OT_terrain_info_set_terrain_scale.bl_idname, icon='MOD_SOLIDIFY', text='Set Terrain Scale')

        # layout.operator(BDK_OT_terrain_info_.bl_idname, icon='FILE_REFRESH', text='Repair')


class BDK_PT_terrain_info_debug(Panel):
    bl_idname = 'BDK_PT_terrain_info_debug'
    bl_label = 'Debug'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 100

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True

        col = flow.column(align=True)

        col.prop(terrain_info, 'x_size', text='Size X', emboss=True)
        col.prop(terrain_info, 'y_size', text='Y', emboss=True)

        # Modifier Performance
        depsgraph = context.evaluated_depsgraph_get()
        object_eval = context.active_object.evaluated_get(depsgraph)

        # Sculpt
        modifier = object_eval.modifiers.get(terrain_info.doodad_sculpt_modifier_name)
        if modifier:
            row = flow.row()
            row.prop(modifier, 'execution_time', text='Doodad Sculpt Execution Time', emboss=False)
            row.prop(terrain_info, 'is_sculpt_modifier_muted', text='', icon='HIDE_ON' if terrain_info.is_sculpt_modifier_muted else 'HIDE_OFF')

        # Attribute
        modifier = object_eval.modifiers.get(terrain_info.doodad_attribute_modifier_name)
        if modifier:
            row = flow.row()
            row.prop(modifier, 'execution_time', text='Doodad Attribute Execution Time', emboss=False)
            row.prop(terrain_info, 'is_attribute_modifier_muted', text='', icon='HIDE_ON' if terrain_info.is_attribute_modifier_muted else 'HIDE_OFF')

        # Paint
        modifier = object_eval.modifiers.get(terrain_info.doodad_paint_modifier_name)
        if modifier:
            row = flow.row()
            row.prop(modifier, 'execution_time', text='Doodad Paint Execution Time', emboss=False)
            row.prop(terrain_info, 'is_paint_modifier_muted', text='', icon='HIDE_ON' if terrain_info.is_paint_modifier_muted else 'HIDE_OFF')

        # Deco
        modifier = object_eval.modifiers.get(terrain_info.doodad_deco_modifier_name)
        if modifier:
            row = flow.row()
            row.prop(modifier, 'execution_time', text='Doodad Deco Execution Time', emboss=False)
            row.prop(terrain_info, 'is_deco_modifier_muted', text='', icon='HIDE_ON' if terrain_info.is_deco_modifier_muted else 'HIDE_OFF')


class BDK_PT_terrain_paint_layers(Panel):
    bl_idname = 'BDK_PT_terrain_paint_layers'
    bl_label = 'Paint Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        row = self.layout.row()
        row.template_list('BDK_UL_terrain_paint_layers', '', terrain_info, 'paint_layers', terrain_info,
                          'paint_layers_index', sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_paint_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_paint_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_terrain_paint_layer_move.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_terrain_paint_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'

        col.separator()
        col.menu(BDK_MT_terrain_paint_layers_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')


class BDK_PT_terrain_paint_layer_settings(Panel):
    bl_idname = 'BDK_PT_terrain_paint_layer_settings'
    bl_label = 'Settings'
    bl_parent_id = 'BDK_PT_terrain_paint_layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return has_terrain_paint_layer_selected(context)

    def draw(self, context: Context):
        paint_layer = get_selected_terrain_paint_layer(context)

        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True

        flow.column(align=True).prop(paint_layer, 'material')

        col = flow.row().column(align=True)
        col.prop(paint_layer, 'u_scale', text='Scale U')
        col.prop(paint_layer, 'v_scale', text='V')
        col.prop(paint_layer, 'texel_density')

        col = flow.row().column(align=True)
        col.prop(paint_layer, 'texture_rotation', text='Rotation')


class BDK_MT_terrain_paint_layers_context_menu(Menu):
    bl_idname = 'BDK_MT_terrain_paint_layers_context_menu'
    bl_label = "Layers Specials"

    def draw(self, context: Context):
        layout: UILayout = self.layout

        operator = layout.operator(BDK_OT_terrain_paint_layers_show.bl_idname, text='Show All', icon='HIDE_OFF')
        operator.mode = 'ALL'

        layout.separator()

        operator = layout.operator(BDK_OT_terrain_paint_layers_hide.bl_idname, text='Hide All', icon='HIDE_ON')
        operator.mode = 'ALL'
        operator = layout.operator(BDK_OT_terrain_paint_layers_hide.bl_idname, text='Hide Unselected')
        operator.mode = 'UNSELECTED'


class BDK_MT_terrain_layer_nodes_context_menu(Menu):
    bl_idname = 'BDK_MT_terrain_layer_nodes_context_menu'
    bl_label = "Nodes Specials"

    def draw(self, context: Context):
        layout: UILayout = self.layout
        layout.operator(BDK_OT_terrain_paint_layer_node_duplicate.bl_idname, text='Duplicate', icon='DUPLICATE')
        layout.separator()
        layout.operator(BDK_OT_terrain_layer_node_merge_down.bl_idname, text='Merge Down', icon='TRIA_DOWN_BAR')
        layout.operator(BDK_OT_terrain_layer_node_convert_to_paint_node.bl_idname, text='Convert to Paint Node', icon='BRUSH_DATA')
        layout.operator(BDK_OT_terrain_layer_paint_node_move_to_group.bl_idname, text='Move to Group', icon='FOLDER_REDIRECT')
        layout.operator(BDK_OT_terrain_paint_layer_node_transfer.bl_idname, text='Move to Terrain Layer', icon='MODIFIER')
        layout.separator()
        layout.operator(BDK_OT_terrain_paint_layer_node_fill.bl_idname, text='Fill', icon='BRUSH_DATA')
        layout.operator(BDK_OT_terrain_paint_layer_node_invert.bl_idname, text='Invert', icon='BRUSH_DATA')


class BDK_PT_terrain_paint_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_paint_layer_debug'
    bl_label = 'Debug'
    bl_parent_id = 'BDK_PT_terrain_paint_layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 100

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context) and has_terrain_paint_layer_selected(context)

    def draw(self, context: Context):
        paint_layer = get_selected_terrain_paint_layer(context)
        layout = self.layout
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(paint_layer, 'id')

        depsgraph = context.evaluated_depsgraph_get()
        object_eval = context.active_object.evaluated_get(depsgraph)
        modifier = object_eval.modifiers.get(paint_layer.id)
        if modifier:
            flow.prop(modifier, 'execution_time', emboss=False)


class BDK_MT_terrain_deco_layers_context_menu(Menu):
    bl_idname = 'BDK_MT_terrain_deco_layers_context_menu'
    bl_label = "Deco Layers Specials"

    def draw(self, context: Context):
        layout: UILayout = self.layout

        operator = layout.operator(BDK_OT_terrain_deco_layers_show.bl_idname, text='Show All', icon='HIDE_OFF')
        operator.mode = 'ALL'

        layout.separator()

        operator = layout.operator(BDK_OT_terrain_deco_layers_hide.bl_idname, text='Hide All', icon='HIDE_ON')
        operator.mode = 'ALL'
        operator = layout.operator(BDK_OT_terrain_deco_layers_hide.bl_idname, text='Hide Unselected')
        operator.mode = 'UNSELECTED'


def has_selected_deco_layer_node(context: Context) -> bool:
    deco_layer = get_selected_deco_layer(context)
    deco_layer_nodes = deco_layer.nodes
    deco_layer_nodes_index = deco_layer.nodes_index
    return 0 <= deco_layer_nodes_index < len(deco_layer_nodes)


def get_selected_deco_layer_node(context: Context) -> Optional[BDK_PG_terrain_layer_node]:
    if not has_selected_deco_layer_node(context):
        return None
    deco_layer = get_selected_deco_layer(context)
    return deco_layer.nodes[deco_layer.nodes_index]


def draw_terrain_layer_node_settings(layout: 'UILayout', node: 'BDK_PG_terrain_layer_node'):
    # TODO: this should probably be its own panel
    if not node:
        return

    layout.separator()

    flow = layout.grid_flow(align=True, columns=1)
    flow.use_property_split = True
    flow.use_property_decorate = False

    flow.prop(node, 'factor')
    flow.separator()

    if node.type == 'PAINT_LAYER':
        flow.column().prop(node, 'paint_layer_name')
    elif node.type == 'NORMAL':
        col = flow.column(align=True)
        col.prop(node, 'normal_angle_min')
        col.prop(node, 'normal_angle_max', text='Max')
    elif node.type == 'NOISE':
        flow.prop(node, 'noise_type')
        if node.noise_type == 'PERLIN':
            col = flow.column(align=True)
            col.prop(node, 'noise_perlin_scale', text='Scale')
            col.prop(node, 'noise_perlin_detail', text='Detail')
            col.prop(node, 'noise_perlin_roughness', text='Roughness')
            col.prop(node, 'noise_perlin_lacunarity', text='Lacunarity')
            col.prop(node, 'noise_perlin_distortion', text='Distortion')

    if node.type not in {'CONSTANT'}:
        flow.prop(node, 'use_map_range')
        if node.use_map_range:
            flow.prop(node, 'map_range_from_min')
            flow.prop(node, 'map_range_from_max', text='Max')


def draw_terrain_layer_node_list(
        layout: 'UILayout',
        listtype_name: str,
        dataptr: Any,
        propname: str,
        active_propname: str,
        add_operator_idname: str,
        remove_operator_idname: str,
        move_operator_idname: str):
    row = layout.row()
    row.column().template_list(
        listtype_name, 'neat',
        dataptr, propname,
        dataptr, active_propname,
        sort_lock=True, rows=5)

    col = row.column(align=True)
    col.operator_menu_enum(add_operator_idname, 'type', icon='ADD', text='')
    col.operator(remove_operator_idname, icon='REMOVE', text='')
    col.separator()
    col.operator(move_operator_idname, icon='TRIA_UP', text='').direction = 'UP'
    col.operator(move_operator_idname, icon='TRIA_DOWN', text='').direction = 'DOWN'
    col.separator()
    col.menu(BDK_MT_terrain_layer_nodes_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')


class BDK_PT_terrain_paint_layer_nodes(Panel):
    bl_parent_id = 'BDK_PT_terrain_paint_layers'
    bl_label = 'Nodes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 2

    @classmethod
    def poll(cls, context: 'Context'):
        return has_terrain_paint_layer_selected(context)

    def draw(self, context: 'Context'):
        layout = self.layout

        paint_layer = get_selected_terrain_paint_layer(context)
        draw_terrain_layer_node_list(layout,
                                     'BDK_UL_terrain_layer_nodes',
                                     paint_layer,
                                     'nodes',
                                     'nodes_index',
                                     add_operator_idname=BDK_OT_terrain_paint_layer_nodes_add.bl_idname,
                                     remove_operator_idname=BDK_OT_terrain_paint_layer_nodes_remove.bl_idname,
                                     move_operator_idname=BDK_OT_terrain_paint_layer_nodes_move.bl_idname)
        node = get_selected_terrain_paint_layer_node(context)
        draw_terrain_layer_node_settings(layout, node)


class BDK_PT_terrain_deco_layer_nodes(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Nodes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 2

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        layout = self.layout

        deco_layer = get_selected_deco_layer(context)
        draw_terrain_layer_node_list(layout,
                                     'BDK_UL_terrain_layer_nodes',
                                     deco_layer,
                                     'nodes',
                                     'nodes_index',
                                     add_operator_idname=BDK_OT_terrain_deco_layer_nodes_add.bl_idname,
                                     remove_operator_idname=BDK_OT_terrain_deco_layer_nodes_remove.bl_idname,
                                     move_operator_idname=BDK_OT_terrain_deco_layer_nodes_move.bl_idname)

        node = get_selected_deco_layer_node(context)
        draw_terrain_layer_node_settings(layout, node)


class BDK_PT_terrain_deco_layer_debug(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Debug'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context) and should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        deco_layer = get_selected_deco_layer(context)

        layout = self.layout
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(deco_layer, 'id', emboss=False)

        # Get the modifier on the deco layer object and get the execution time.
        # This is a bit hacky, but it works.

        if deco_layer.object is None:
            layout.label(text='No object found', icon='ERROR')
        else:
            depsgraph = context.evaluated_depsgraph_get()
            evaluated_object = deco_layer.object.evaluated_get(depsgraph)
            modifier: Modifier = evaluated_object.modifiers.get(deco_layer.id)
            if modifier:
                flow.prop(modifier, 'execution_time', text='Execution Time', emboss=False)
            else:
                layout.label(text='No modifier found', icon='ERROR')


class BDK_PT_terrain_deco_layer_mesh(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Mesh'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 0

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        box = self.layout.box()

        icon_id = 0
        if deco_layer.static_mesh and deco_layer.static_mesh.preview:
            icon_id = deco_layer.static_mesh.preview.icon_id
        box.template_icon(icon_value=icon_id, scale=4)

        self.layout.separator()

        flow = self.layout.grid_flow(row_major=True, columns=1, even_columns=True, even_rows=False, align=False)
        flow.use_property_split = True

        flow.column().prop(deco_layer, 'static_mesh', text='Static Mesh')


class BDK_PT_terrain_deco_layer_settings(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True

        flow.column().prop(deco_layer, 'max_per_quad')
        flow.column().prop(deco_layer, 'seed')
        flow.column().prop(deco_layer, 'offset')
        flow.separator()

        col = flow.column(align=True)
        col.prop(deco_layer, 'density_multiplier_min', text='Density Min')
        col.prop(deco_layer, 'density_multiplier_max', text='Max')
        flow.separator()

        col = flow.column(align=True)
        col.prop(deco_layer, 'fadeout_radius_min', text='Fadeout Radius Min')
        col.prop(deco_layer, 'fadeout_radius_max', text='Max')
        flow.separator()

        col = flow.column()
        col.prop(deco_layer, 'scale_multiplier_min', text='Scale Min')
        col.prop(deco_layer, 'scale_multiplier_max', text='Max')
        col.separator()

        flow.column().prop(deco_layer, 'align_to_terrain')
        flow.column().prop(deco_layer, 'show_on_invisible_terrain')
        row = flow.column(align=True)
        row.prop(deco_layer, 'random_yaw')
        flow.separator()

        flow.column().prop(deco_layer, 'force_draw')
        flow.column().prop(deco_layer, 'detail_mode')
        flow.column().prop(deco_layer, 'draw_order')


class BDK_PT_terrain_deco_layers(Panel):
    bl_idname = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Deco Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        layout = self.layout
        terrain_info = get_terrain_info(context.active_object)

        row = layout.row()
        row.template_list('BDK_UL_terrain_deco_layers', '',
                          terrain_info, 'deco_layers',
                          terrain_info, 'deco_layers_index', rows=3, sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_deco_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_deco_layer_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        col.menu(BDK_MT_terrain_deco_layers_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')

        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        # TODO: Add this to an "Advanced" panel so this isn't so cluttered
        flow.prop(terrain_info, 'deco_layer_offset')


class BDK_UL_terrain_paint_layers(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        icon = row.icon(item.material) if item.material else None
        if icon:
            row.prop(item, 'name', text='', emboss=False, icon_value=icon)
        else:
            row.prop(item, 'name', text='', emboss=False, icon='IMAGE')

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item, 'is_visible', icon=('HIDE_OFF' if item.is_visible else 'HIDE_ON'), text='', emboss=False)


class BDK_UL_terrain_deco_layers(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'name', text='', emboss=False)

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item.object, 'hide_viewport', icon=('HIDE_OFF' if not item.object.hide_viewport else 'HIDE_ON'), text='', emboss=False)


def draw_terrain_layer_node_item(layout: UILayout, item, mesh):
    color_attribute_index = mesh.color_attributes.find(item.id)
    is_active_color_attribute = color_attribute_index != -1 and color_attribute_index == mesh.color_attributes.active_color_index

    row = layout.row()
    # Display an icon if this is the active color attribute.
    row.label(text='', icon='VPAINT_HLT' if is_active_color_attribute else 'BLANK1')

    col = row.column(align=True)

    if item.type == 'PAINT_LAYER':
        if item.paint_layer_name:
            col.label(text=item.paint_layer_name, icon=node_type_icons[item.type])
        else:
            col.label(text='<no layer selected>', icon=node_type_icons[item.type])
    else:
        col.prop(item, 'name', text='', emboss=False, icon=node_type_icons[item.type])

    row = row.row(align=True)
    row.prop(item, 'operation', text='', emboss=False)
    row.prop(item, 'mute', text='', emboss=False, icon='HIDE_OFF' if not item.mute else 'HIDE_ON')


class BDK_UL_terrain_layer_nodes(UIList):

    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        mesh = cast(Mesh, context.active_object.data)
        draw_terrain_layer_node_item(layout, item, mesh)


classes = (
    BDK_PT_terrain_info,
    BDK_PT_terrain_info_advanced,
    BDK_PT_terrain_info_debug,
    BDK_UL_terrain_layer_nodes,
    BDK_PT_terrain_paint_layers,
    BDK_PT_terrain_deco_layers,
    BDK_UL_terrain_paint_layers,
    BDK_PT_terrain_paint_layer_settings,
    BDK_PT_terrain_paint_layer_debug,
    BDK_UL_terrain_deco_layers,
    BDK_PT_terrain_deco_layer_mesh,
    BDK_PT_terrain_deco_layer_settings,
    BDK_PT_terrain_deco_layer_nodes,
    BDK_PT_terrain_deco_layer_debug,
    BDK_MT_terrain_deco_layers_context_menu,
    BDK_MT_terrain_paint_layers_context_menu,
    BDK_PT_terrain_paint_layer_nodes,
    BDK_MT_terrain_layer_nodes_context_menu,
)
