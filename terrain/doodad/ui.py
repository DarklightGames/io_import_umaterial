from typing import cast

import bpy
from bpy.types import Panel, Context, UIList, UILayout

from ...helpers import should_show_bdk_developer_extras, get_terrain_doodad, is_active_object_terrain_doodad
from .operators import BDK_OT_terrain_doodad_sculpt_layer_add, BDK_OT_terrain_doodad_sculpt_layer_remove, \
    BDK_OT_terrain_doodad_paint_layer_add, BDK_OT_terrain_doodad_paint_layer_remove, \
    BDK_OT_terrain_doodad_paint_layer_duplicate, BDK_OT_terrain_doodad_sculpt_layer_duplicate, \
    BDK_OT_terrain_doodad_bake, BDK_OT_terrain_doodad_duplicate, BDK_OT_terrain_doodad_delete, \
    BDK_OT_terrain_doodad_scatter_layer_add, BDK_OT_terrain_doodad_scatter_layer_remove, \
    BDK_OT_terrain_doodad_scatter_layer_objects_add, BDK_OT_terrain_doodad_scatter_layer_objects_remove, \
    BDK_OT_terrain_doodad_scatter_layer_duplicate, BDK_OT_terrain_doodad_bake_debug
from .properties import BDK_PG_terrain_doodad


class BDK_UL_terrain_doodad_scatter_layer_objects(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.object.name if item.object is not None else '<no object selected>', icon='OBJECT_DATA')
        # layout.prop(item, 'random_weight', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_scatter_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='PARTICLE_POINT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_sculpt_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='SCULPTMODE_HLT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_paint_layers(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        if item.layer_type == 'PAINT':
            layout.label(text=item.paint_layer_name if item.paint_layer_name else '<no layer selected>', icon='VPAINT_HLT')
        elif item.layer_type == 'DECO':
            layout.label(text=item.deco_layer_name if item.deco_layer_name else '<no layer selected>', icon='MONKEY')
        layout.prop(item, 'operation', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_PT_terrain_doodad_paint_layer_settings(Panel):

    bl_idname = 'BDK_PT_terrain_doodad_paint_layer_settings'
    bl_label = 'Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'BDK_PT_terrain_doodad_paint_layers'

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_doodad(context):
            return False
        terrain_doodad = context.active_object.bdk.terrain_doodad
        return len(terrain_doodad.paint_layers) > 0 and terrain_doodad.paint_layers_index >= 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        row = flow.row()
        row.prop(paint_layer, 'layer_type', expand=True)

        if paint_layer.layer_type == 'PAINT':
            flow.prop(paint_layer, 'paint_layer_name')
        elif paint_layer.layer_type == 'DECO':
            row = flow.row()
            row.prop(paint_layer, 'deco_layer_name')
            deco_layer_object = bpy.data.objects[paint_layer.deco_layer_id] if paint_layer.deco_layer_id in bpy.data.objects else None
            if deco_layer_object:
                row.prop(deco_layer_object, 'hide_viewport', icon_only=True)

        flow.separator()

        flow.prop(paint_layer, 'interpolation_type')

        col = flow.column()

        col.prop(paint_layer, 'radius')
        col.prop(paint_layer, 'falloff_radius')
        col.prop(paint_layer, 'strength')

        if terrain_doodad.object.type == 'CURVE':
            draw_curve_modifier_settings(flow, paint_layer)
            flow.separator()

        flow.prop(paint_layer, 'use_distance_noise')

        if paint_layer.use_distance_noise:
            col = flow.column(align=True)
            col.prop(paint_layer, 'noise_type', icon='MOD_NOISE')
            col.prop(paint_layer, 'distance_noise_offset')
            col.prop(paint_layer, 'distance_noise_factor')
            if paint_layer.noise_type == 'PERLIN':
                col.prop(paint_layer, 'distance_noise_distortion')


class BDK_PT_terrain_doodad_paint_layers(Panel):
    bl_label = 'Paint Layers'
    bl_idname = 'BDK_PT_terrain_doodad_paint_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        # TODO: make sure there is at least one paint layer
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: Context):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        # Paint Layers
        row = layout.row()

        row.template_list(
            'BDK_UL_terrain_doodad_paint_layers', '',
            terrain_doodad, 'paint_layers',
            terrain_doodad, 'paint_layers_index',
            sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_paint_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_paint_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        col.operator(BDK_OT_terrain_doodad_paint_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad_operators(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_operators'
    bl_label = 'Operators'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        self.layout.operator(BDK_OT_terrain_doodad_bake.bl_idname, icon='RENDER_RESULT')
        self.layout.operator(BDK_OT_terrain_doodad_duplicate.bl_idname, icon='DUPLICATE')
        self.layout.operator(BDK_OT_terrain_doodad_delete.bl_idname, icon='X')


class BDK_PT_terrain_doodad_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad: 'BDK_PG_terrain_doodad' = context.active_object.bdk.terrain_doodad
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(terrain_doodad, 'id', emboss=False)
        flow.prop(terrain_doodad, 'object', emboss=False)
        flow.prop(terrain_doodad, 'node_tree', emboss=False)
        flow.prop(terrain_doodad, 'terrain_info_object', emboss=False)


class BDK_PT_terrain_doodad_advanced(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_advanced'
    bl_label = 'Advanced'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        terrain_doodad: 'BDK_PG_terrain_doodad' = context.active_object.bdk.terrain_doodad
        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(terrain_doodad, 'sort_order')


class BDK_PT_terrain_doodad_sculpt_layer_settings(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_settings'
    bl_label = 'Settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        sculpt_layer = terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index]
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(sculpt_layer, 'depth')

        col = flow.column(align=True)
        col.prop(sculpt_layer, 'radius')
        col.prop(sculpt_layer, 'falloff_radius')
        col.prop(sculpt_layer, 'interpolation_type')

        flow.separator()

        if terrain_doodad.object.type == 'CURVE':
            draw_curve_modifier_settings(flow, sculpt_layer)
            flow.separator()

        flow.prop(sculpt_layer, 'use_noise')

        if sculpt_layer.use_noise:
            flow.prop(sculpt_layer, 'noise_type')

            if sculpt_layer.use_noise:
                col = flow.column(align=True)
                col.prop(sculpt_layer, 'noise_radius_factor')
                if sculpt_layer.noise_type == 'PERLIN':
                    col.prop(sculpt_layer, 'noise_distortion')
                    col.prop(sculpt_layer, 'noise_roughness')
                    col.prop(sculpt_layer, 'noise_strength')


class BDK_PT_terrain_doodad_sculpt_layers(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_label = 'Sculpt Layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: Context):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        row = layout.row()

        row.template_list('BDK_UL_terrain_doodad_sculpt_layers',
                          '',
                          terrain_doodad,
                          'sculpt_layers',
                          terrain_doodad,
                          'sculpt_layers_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_sculpt_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_sculpt_layer_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        # operator = col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_UP', text='')
        # operator.direction = 'UP'
        # operator = col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        # operator.direction = 'DOWN'

        # col.separator()

        col.operator(BDK_OT_terrain_doodad_sculpt_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad(Panel):
    bl_label = 'Terrain Doodad'
    bl_idname = 'BDK_PT_terrain_doodad'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        pass


class BDK_PT_terrain_doodad_scatter_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return len(terrain_doodad.scatter_layers) > 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(scatter_layer, 'id', emboss=False)

        depsgraph = context.evaluated_depsgraph_get()
        if scatter_layer.seed_object:
            seed_object_evaluated = scatter_layer.seed_object.evaluated_get(depsgraph)
            for modifier in seed_object_evaluated.modifiers:
                flow.prop(modifier, 'execution_time', emboss=False)
        if scatter_layer.sprout_object:
            sprout_object_evaluated = scatter_layer.sprout_object.evaluated_get(depsgraph)
            for modifier in sprout_object_evaluated.modifiers:
                flow.prop(modifier, 'execution_time', emboss=False)


class BDK_PT_terrain_doodad_scatter_layers(Panel):
    bl_label = 'Scatter Layers'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'BDK_PT_terrain_doodad'

    @classmethod
    def poll(cls, context: 'Context'):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        row = layout.row()

        row.template_list('BDK_UL_terrain_doodad_scatter_layers', '',
                          terrain_doodad,
                          'scatter_layers',
                          terrain_doodad,
                          'scatter_layers_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_scatter_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_scatter_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        col.operator(BDK_OT_terrain_doodad_scatter_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad_scatter_layer_curve_settings(Panel):
    bl_label = 'Curve Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_curve_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 10

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        if terrain_doodad.object.type != 'CURVE':
            return False
        # Get selected scatter layer.
        if len(terrain_doodad.scatter_layers) == 0:
            return False
        return True

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        # Curve settings
        draw_curve_modifier_settings(flow, scatter_layer)

        flow.separator()

        flow.prop(scatter_layer, 'curve_spacing_method')

        if scatter_layer.curve_spacing_method == 'RELATIVE':
            flow.prop(scatter_layer, 'curve_spacing_relative_axis', text='Axis')
            flow.prop(scatter_layer, 'curve_spacing_relative_factor', text='Factor')
        elif scatter_layer.curve_spacing_method == 'ABSOLUTE':
            flow.prop(scatter_layer, 'curve_spacing_absolute', text='Distance')

        flow.separator()

        flow.prop(scatter_layer, 'curve_normal_offset_min', text='Normal Offset Min')
        flow.prop(scatter_layer, 'curve_normal_offset_max', text='Max')
        flow.prop(scatter_layer, 'curve_normal_offset_seed', text='Seed')

class BDK_PT_terrain_doodad_scatter_layer_objects(Panel):
    bl_label = 'Objects'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 20

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return len(terrain_doodad.scatter_layers) > 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'object_select_mode', text='Object Mode')

        if scatter_layer.object_select_mode == 'RANDOM':
            flow.prop(scatter_layer, 'object_select_random_seed', text='Seed')
        elif scatter_layer.object_select_mode == 'CYCLIC':
            flow.prop(scatter_layer, 'object_select_cyclic_offset', text='Offset')

        row = layout.row()
        row.template_list('BDK_UL_terrain_doodad_scatter_layer_objects', '',
                          scatter_layer,
                          'objects',
                          scatter_layer,
                          'objects_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_scatter_layer_objects_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_scatter_layer_objects_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        scatter_layer_object = scatter_layer.objects[scatter_layer.objects_index] if len(
            scatter_layer.objects) else None

        if scatter_layer_object:
            flow = layout.grid_flow(align=True, columns=1)
            flow.use_property_split = True
            flow.use_property_decorate = False

            flow.prop(scatter_layer_object, 'object', text='Object')

            flow.separator()

            flow.prop(scatter_layer_object, 'snap_to_terrain')

            if scatter_layer_object.snap_to_terrain:
                flow.prop(scatter_layer_object, 'align_to_terrain_factor')
                flow.prop(scatter_layer_object, 'terrain_normal_offset_min', text='Terrain Offset Min')
                flow.prop(scatter_layer_object, 'terrain_normal_offset_max', text='Max')
                flow.prop(scatter_layer_object, 'terrain_normal_offset_seed', text='Seed')

            flow.separator()

            flow.prop(scatter_layer_object, 'scale_min', text='Scale Min')
            flow.prop(scatter_layer_object, 'scale_max', text='Max')
            flow.prop(scatter_layer_object, 'scale_seed', text='Seed')

            flow.separator()

            flow.prop(scatter_layer_object, 'random_rotation')

            if terrain_doodad.object.type == 'CURVE':
                flow.separator()

                col = flow.column(align=True)
                col.prop(scatter_layer_object, 'curve_normal_offset_min')
                col.prop(scatter_layer_object, 'curve_normal_offset_max', text='Max')
                col.prop(scatter_layer_object, 'curve_normal_offset_seed', text='Seed')


def draw_curve_modifier_settings(layout: UILayout, data):
    layout.prop(data, 'is_curve_reversed')
    layout.prop(data, 'curve_normal_offset')
    layout.prop(data, 'curve_trim_mode')

    if data.curve_trim_mode == 'FACTOR':
        col = layout.column(align=True)
        col.prop(data, 'curve_trim_factor_start', text='Trim Start')
        col.prop(data, 'curve_trim_factor_end', text='End')
    elif data.curve_trim_mode == 'LENGTH':
        col = layout.column(align=True)
        col.prop(data, 'curve_trim_length_start', text='Trim Start')
        col.prop(data, 'curve_trim_length_end', text='End')


class BDK_PT_terrain_doodad_scatter_layer_settings(Panel):
    bl_label = 'Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 0

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad and len(terrain_doodad.scatter_layers) and terrain_doodad.scatter_layers_index >= 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(scatter_layer, 'global_seed')


class BDK_PT_terrain_doodad_paint_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_paint_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_paint_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.row().prop(paint_layer, 'id')


class BDK_PT_terrain_doodad_sculpt_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        sculpt_layer = terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index]
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.prop(sculpt_layer, 'id')


classes = (
    BDK_PT_terrain_doodad,
    BDK_UL_terrain_doodad_sculpt_layers,
    BDK_PT_terrain_doodad_sculpt_layers,
    BDK_PT_terrain_doodad_sculpt_layer_settings,
    BDK_PT_terrain_doodad_sculpt_layer_debug,
    BDK_UL_terrain_doodad_paint_layers,
    BDK_PT_terrain_doodad_paint_layers,
    BDK_PT_terrain_doodad_paint_layer_settings,
    BDK_PT_terrain_doodad_paint_layer_debug,
    BDK_UL_terrain_doodad_scatter_layers,
    BDK_PT_terrain_doodad_scatter_layers,
    BDK_UL_terrain_doodad_scatter_layer_objects,
    BDK_PT_terrain_doodad_scatter_layer_objects,
    BDK_PT_terrain_doodad_scatter_layer_settings,
    BDK_PT_terrain_doodad_scatter_layer_curve_settings,
    BDK_PT_terrain_doodad_scatter_layer_debug,
    BDK_PT_terrain_doodad_advanced,
    BDK_PT_terrain_doodad_operators,
    BDK_PT_terrain_doodad_debug,
)
