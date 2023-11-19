from typing import List

from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from ...constants import RADIUS_EPSILON
from ...property_group_helpers import add_curve_modifier_properties
from ...data import map_range_interpolation_type_items
from ...helpers import get_terrain_info
from ...units import meters_to_unreal
from .scatter.properties import BDK_PG_terrain_doodad_scatter_layer
from .sculpt.properties import BDK_PG_terrain_doodad_sculpt_layer
from .builder import ensure_terrain_info_modifiers
from .data import terrain_doodad_noise_type_items, terrain_doodad_operation_items

empty_set = set()


def terrain_doodad_sort_order_update_cb(self: 'BDK_PG_terrain_doodad', context: Context):
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons. (TODO: NOT TRUE!)
    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


def terrain_doodad_paint_layer_paint_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers
    return [paint_layer.name for paint_layer in paint_layers]


def terrain_doodad_paint_layer_deco_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of deco layer names for the selected terrain info object.
    deco_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.deco_layers
    return [deco_layer.name for deco_layer in deco_layers]


def terrain_doodad_paint_layer_paint_layer_name_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # Update the terrain layer ID when the terrain layer name is changed.
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers

    # Get the index of the terrain layer with the given name.
    paint_layer_names = [paint_layer.name for paint_layer in paint_layers]

    try:
        paint_layer_index = paint_layer_names.index(self.paint_layer_name)
        self.paint_layer_id = paint_layers[paint_layer_index].id
    except ValueError:
        self.paint_layer_id = ''

    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


def terrain_doodad_paint_layer_deco_layer_name_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # Update the deco layer ID when the deco layer name is changed.
    deco_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.deco_layers

    # Get the index of the deco layer with the given name.
    deco_layer_names = [deco_layer.name for deco_layer in deco_layers]

    try:
        deco_layer_index = deco_layer_names.index(self.deco_layer_name)
        self.deco_layer_id = deco_layers[deco_layer_index].id
    except ValueError:
        self.deco_layer_id = ''

    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


class BDK_PG_terrain_doodad_paint_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=terrain_doodad_operation_items, default='ADD')
    interpolation_type: EnumProperty(
        name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')
    index: IntProperty(options={'HIDDEN'})
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0), min=RADIUS_EPSILON)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=RADIUS_EPSILON)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('PAINT', 'Paint', 'Paint layer'),
        ('DECO', 'Deco', 'Deco layer'),
        ('ATTRIBUTE', 'Attribute', 'Attribute layer')
    ), default='PAINT', update=terrain_doodad_update_cb)  # TODO: switch node this as well
    paint_layer_name: StringProperty(
        name='Paint Layer',
        search=terrain_doodad_paint_layer_paint_layer_name_search_cb,
        update=terrain_doodad_paint_layer_paint_layer_name_update_cb,
        search_options={'SORT'}
    )
    deco_layer_name: StringProperty(
        name='Deco Layer',
        search=terrain_doodad_paint_layer_deco_layer_name_search_cb,
        update=terrain_doodad_paint_layer_deco_layer_name_update_cb,
        search_options={'SORT'}
    )
    attribute_layer_id: StringProperty(name='Attribute Layer ID', default='')
    paint_layer_id: StringProperty(name='Terrain Layer ID', default='', options={'HIDDEN'})
    deco_layer_id: StringProperty(name='Deco Layer ID', default='', options={'HIDDEN'})
    mute: BoolProperty(name='Mute', default=False)

    use_distance_noise: BoolProperty(name='Distance Noise', default=False)
    # TODO: Convert this to just use a switch node
    noise_type: EnumProperty(
        name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE', update=terrain_doodad_update_cb)
    distance_noise_factor: FloatProperty(
        name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')

    frozen_attribute_id: StringProperty(name='Frozen Attribute ID', default='', options={'HIDDEN'})


add_curve_modifier_properties(BDK_PG_terrain_doodad_paint_layer)


class BDK_PG_terrain_doodad(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_doodad_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Layers', type=BDK_PG_terrain_doodad_sculpt_layer)
    sculpt_layers_index: IntProperty()

    # TODO: not yet implemented
    radius_factor: FloatProperty(name='Radius Factor', default=1.0, min=RADIUS_EPSILON, soft_max=10, subtype='FACTOR',
                                 description='All radius values will be multiplied by this value. This is useful for '
                                                'scaling the radius of all layers at once.')

    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain doodad.
    #  we are currently using the ID of the terrain doodad, but this isn't ideal because the sort order is effectively
    #  random for terrain doodad that share the same sort order.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain doodad are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_doodad_sort_order_update_cb)
    scatter_layers: CollectionProperty(name='Scatter Layers', type=BDK_PG_terrain_doodad_scatter_layer)
    scatter_layers_index: IntProperty()

    is_frozen: BoolProperty(name='Is Frozen', default=False)


classes = (
    BDK_PG_terrain_doodad_paint_layer,
    BDK_PG_terrain_doodad,
)
