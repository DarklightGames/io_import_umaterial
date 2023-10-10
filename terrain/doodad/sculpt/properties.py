from bpy.props import StringProperty, PointerProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.types import PropertyGroup, Object

from ....property_group_helpers import add_curve_modifier_properties
from ....constants import RADIUS_EPSILON
from ....data import map_range_interpolation_type_items
from ..data import terrain_doodad_noise_type_items
from ....units import meters_to_unreal


class BDK_PG_terrain_doodad_sculpt_layer(PropertyGroup):
    id: StringProperty(name='ID', default='')
    name: StringProperty(name='Name', default='Sculpt Layer')
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=RADIUS_EPSILON)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=RADIUS_EPSILON)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE')
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=RADIUS_EPSILON, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=meters_to_unreal(0.25), subtype='DISTANCE', min=0.0, soft_max=meters_to_unreal(2.0))
    perlin_noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    perlin_noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    perlin_noise_scale: FloatProperty(name='Noise Scale', default=1.0, min=0.0)
    perlin_noise_lacunarity: FloatProperty(name='Noise Lacunarity', default=2.0, min=0.0)
    perlin_noise_detail: FloatProperty(name='Noise Detail', default=8.0, min=0.0)
    mute: BoolProperty(name='Mute', default=False)
    interpolation_type: EnumProperty(name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')


add_curve_modifier_properties(BDK_PG_terrain_doodad_sculpt_layer)
# TODO: add noise settings in the same manner so that we can use the same settings

classes = (
    BDK_PG_terrain_doodad_sculpt_layer,
)