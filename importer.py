import math
import os
from typing import Optional, Dict, cast, Tuple
from pathlib import Path

from bpy.types import ShaderNodeTexImage
import bpy.types
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy_types import Operator

from .data import UMaterial, UTexture, ETexClampMode, UReference, UCombiner, EColorOperation, EAlphaOperation, \
    UConstantColor, UTexRotator, ETexRotationType, UTexOscillator, ETexOscillationType, UTexCoordSource
from .reader import read_material


class MaterialCache:
    def __init__(self, root_directory: str):
        self.__root_directory__ = root_directory
        self.__materials__: Dict[str, UMaterial] = {}

    def resolve_path_for_reference(self, reference: UReference) -> Optional[Path]:
        try:
            return Path(os.path.join(self.__root_directory__, reference.package_name, reference.type_name, f'{reference.object_name}.props.txt')).resolve()
        except RuntimeError:
            pass
        return None

    def load_material(self, reference: UReference) -> Optional[UMaterial]:
        if reference is None:
            return None
        key = str(reference)
        if key in self.__materials__:
            return self.__materials__[str(reference)]
        path = self.resolve_path_for_reference(reference)
        if path is None:
            return None
        material = read_material(str(path))
        self.__materials__[key] = material
        return material


class MaterialSocketOutputs:
    color_socket: bpy.types.NodeSocket = None
    alpha_socket: bpy.types.NodeSocket = None
    blend_method: str = 'OPAQUE'
    use_backface_culling: bool = False
    size: Tuple[int, int] = (1, 1)


class MaterialSocketInputs:
    uv_socket: bpy.types.NodeSocket = None


# TODO: test this
def import_tex_coord_source(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, tex_coord_source: UTexCoordSource, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    uv_map_node = node_tree.nodes.new('ShaderNodeUVMap')
    if tex_coord_source.SourceChannel == 0:
        uv_map_node.uv_map = 'VTXW0000'
    elif tex_coord_source.SourceChannel > 0:
        uv_map_node.uv_map = f'EXTRAUV{tex_coord_source.SourceChannel - 1}'
    else:
        raise RuntimeError('SourceChannel cannot be < 0')

    socket_inputs.uv_socket = uv_map_node.outputs['UV']

    material = material_cache.load_material(tex_coord_source.Material)
    material_outputs = import_material(material_cache, node_tree, material, socket_inputs)

    return material_outputs


def import_tex_oscillator(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, tex_oscillator: UTexOscillator, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    tex_coord_node = node_tree.nodes.new('ShaderNodeTexCoord')
    vector_subtract_node = node_tree.nodes.new('ShaderNodeVectorMath')
    vector_subtract_node.operation = 'SUBTRACT'
    vector_add_node = node_tree.nodes.new('ShaderNodeVectorMath')
    vector_add_node.operation = 'ADD'
    vector_transform_node = node_tree.nodes.new('ShaderNodeVectorMath')

    offset_node = node_tree.nodes.new('ShaderNodeCombineXYZ')

    node_tree.links.new(vector_subtract_node.inputs[0], tex_coord_node.outputs['UV'])
    node_tree.links.new(vector_add_node.inputs[0], vector_transform_node.outputs[0])
    node_tree.links.new(vector_transform_node.inputs[0], vector_subtract_node.outputs[0])
    node_tree.links.new(vector_subtract_node.inputs[1], offset_node.outputs['Vector'])
    node_tree.links.new(vector_add_node.inputs[1], offset_node.outputs['Vector'])

    socket_inputs.uv_socket = vector_add_node.outputs['Vector']

    material = material_cache.load_material(tex_oscillator.Material)
    material_outputs = import_material(material_cache, node_tree, material, socket_inputs)

    offset_node.inputs['X'].default_value = tex_oscillator.UOffset / material_outputs.size[0]
    offset_node.inputs['Y'].default_value = tex_oscillator.VOffset / material_outputs.size[1]

    def get_driver_expression_for_pan(rate, amplitude):
        return f'sin((frame / bpy.context.scene.render.fps) * {rate * math.pi * 2}) * {amplitude}'

    def get_driver_expression_for_stretch(rate, amplitude):
        return f'1.0 + sin((frame / bpy.context.scene.render.fps) * {rate * math.pi * 2}) * {amplitude}'

    def add_driver_to_vector_transform_input(expression: str, index: int):
        fcurve = vector_transform_node.inputs[1].driver_add('default_value', index)
        fcurve.driver.expression = expression

    if tex_oscillator.UOscillationType == ETexOscillationType.OT_Pan:
        vector_transform_node.operation = 'ADD'
        if tex_oscillator.UOscillationRate != 0 and tex_oscillator.UOscillationAmplitude != 0:
            add_driver_to_vector_transform_input(
                get_driver_expression_for_pan(tex_oscillator.UOscillationRate, tex_oscillator.UOscillationAmplitude), 0)
        if tex_oscillator.VOscillationRate != 0 and tex_oscillator.VOscillationAmplitude != 0:
            add_driver_to_vector_transform_input(
                get_driver_expression_for_pan(tex_oscillator.VOscillationRate, tex_oscillator.VOscillationAmplitude), 1)
    elif tex_oscillator.UOscillationType == ETexOscillationType.OT_Jitter:
        vector_transform_node.operation = 'ADD'
        # same as add, but weird
        pass
    elif tex_oscillator.UOscillationType == ETexOscillationType.OT_Stretch:
        vector_transform_node.operation = 'MULTIPLY'
        if tex_oscillator.UOscillationRate != 0 and tex_oscillator.UOscillationAmplitude != 0:
            add_driver_to_vector_transform_input(
                get_driver_expression_for_stretch(tex_oscillator.UOscillationRate, tex_oscillator.UOscillationAmplitude), 0)
        if tex_oscillator.VOscillationRate != 0 and tex_oscillator.VOscillationAmplitude != 0:
            add_driver_to_vector_transform_input(
                get_driver_expression_for_stretch(tex_oscillator.VOscillationRate, tex_oscillator.VOscillationAmplitude), 1)
    elif tex_oscillator.UOscillationType == ETexOscillationType.OT_StretchRepeat:
        vector_transform_node.operation = 'MULTIPLY'
        # same as stretch, but weird...
        pass

    return material_outputs


def import_tex_rotator(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, tex_rotator: UTexRotator, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    tex_coord_node = node_tree.nodes.new('ShaderNodeTexCoord')
    vector_rotate_node = node_tree.nodes.new('ShaderNodeVectorRotate')
    vector_rotate_node.rotation_type = 'EULER_XYZ'

    socket_inputs.uv_socket = vector_rotate_node.outputs['Vector']

    material = material_cache.load_material(tex_rotator.Material)
    material_outputs = import_material(material_cache, node_tree, material, socket_inputs)

    u = tex_rotator.UOffset / material_outputs.size[0]
    v = tex_rotator.VOffset / material_outputs.size[1]
    vector_rotate_node.inputs['Center'].default_value = (u, v, 0.0)
    vector_rotate_node.inputs['Axis'].default_value = (0.0, 0.0, -1.0)

    rotation_radians = tex_rotator.Rotation.get_radians()

    def add_driver_to_vector_rotate_rotation_input(expression: str, index: int):
        fcurve = vector_rotate_node.inputs['Rotation'].driver_add('default_value', index)
        fcurve.driver.expression = expression

    if tex_rotator.TexRotationType == ETexRotationType.TR_FixedRotation:
        vector_rotate_node.inputs['Rotation'].default_value = rotation_radians
    elif tex_rotator.TexRotationType == ETexRotationType.TR_OscillatingRotation:
        amplitude_radians = tex_rotator.OscillationAmplitude.get_radians()
        rate_radians = tex_rotator.OscillationRate.get_radians()
        for i, amplitude, rate in enumerate(zip(amplitude_radians, rate_radians)):
            if amplitude != 0 or rate != 0:
                add_driver_to_vector_rotate_rotation_input(
                    f'sin(frame / bpy.context.scene.render.fps * {rate}) * {amplitude}', i)
    elif tex_rotator.TexRotationType == ETexRotationType.TR_ConstantlyRotating:
        for i, radians in enumerate(rotation_radians):
            if radians != 0:
                add_driver_to_vector_rotate_rotation_input(f'(frame / bpy.context.scene.render.fps) * {radians}', i)

    node_tree.links.new(vector_rotate_node.inputs['Vector'], tex_coord_node.outputs['UV'])

    return material_outputs


def import_constant_color(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, constant_color: UConstantColor, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    outputs = MaterialSocketOutputs()

    rgb_node = node_tree.nodes.new('ShaderNodeRGB')
    rgb_node.outputs[0].default_value = (
        float(constant_color.Color.R) / 255.0,
        float(constant_color.Color.G) / 255.0,
        float(constant_color.Color.B) / 255.0,
        float(constant_color.Color.A) / 255.0
    )

    outputs.color_socket = rgb_node.outputs[0]

    return outputs


def import_texture(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, texture: UTexture, socket_inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    outputs = MaterialSocketOutputs()

    if texture.Reference is None:
        return outputs

    image_node = cast(ShaderNodeTexImage, node_tree.nodes.new('ShaderNodeTexImage'))
    image_path = material_cache.resolve_path_for_reference(texture.Reference)
    image_path = str(image_path)
    image_path = image_path.replace('.props.txt', '.tga')

    image_node.image = bpy.data.images.load(str(image_path), check_existing=True)

    if socket_inputs.uv_socket is not None:
        # Hook up UV socket input to image texture.
        node_tree.links.new(image_node.inputs['Vector'], socket_inputs.uv_socket)

    match texture.UClampMode:
        case ETexClampMode.TC_Clamp:
            image_node.extension = 'EXTEND'
        case ETexClampMode.TC_Wrap:
            image_node.extension = 'REPEAT'

    # Detail texture
    detail_material = None if texture.Detail is None else material_cache.load_material(texture.Detail)
    if detail_material is not None:

        # Create UV scaling sockets.
        texcoord_node = node_tree.nodes.new('ShaderNodeTexCoord')

        scale_node = node_tree.nodes.new('ShaderNodeVectorMath')
        scale_node.operation = 'SCALE'
        scale_node.inputs['Scale'].default_value = texture.DetailScale

        node_tree.links.new(scale_node.inputs[0], texcoord_node.outputs['UV'])

        detail_socket_inputs = MaterialSocketInputs()
        detail_socket_inputs.uv_socket = scale_node.outputs['Vector']

        # Import the detail material.
        detail_socket_outputs = import_material(material_cache, node_tree, detail_material, detail_socket_inputs)

        # This is a decent approximation for how detail textures look in-engine.

        hsv_node = node_tree.nodes.new('ShaderNodeHueSaturation')
        hsv_node.inputs['Value'].default_value = 4.0

        node_tree.links.new(hsv_node.inputs['Color'], detail_socket_outputs.color_socket)

        mix_node = node_tree.nodes.new('ShaderNodeMix')
        mix_node.data_type = 'RGBA'
        mix_node.blend_type = 'MULTIPLY'
        mix_node.inputs['Factor'].default_value = 1.0

        #
        node_tree.links.new(mix_node.inputs[6], image_node.outputs['Color'])
        node_tree.links.new(mix_node.inputs[7], hsv_node.outputs['Color'])

        outputs.color_socket = mix_node.outputs[2]
    else:
        outputs.color_socket = image_node.outputs['Color']

    outputs.use_backface_culling = not texture.bTwoSided

    if texture.bAlphaTexture or texture.bMasked:
        outputs.alpha_socket = image_node.outputs['Alpha']

    if texture.bMasked:
        outputs.blend_method = 'CLIP'
    elif texture.bAlphaTexture:
        outputs.blend_method = 'BLEND'
    else:
        outputs.blend_method = 'OPAQUE'

    outputs.size = (texture.UClamp, texture.VClamp)

    return outputs


def import_combiner(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, combiner: UCombiner, inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    # https://docs.unrealengine.com/udk/Two/MaterialsCombiners.html

    outputs = MaterialSocketOutputs()

    material1 = material_cache.load_material(combiner.Material1)
    material2 = material_cache.load_material(combiner.Material2)
    mask_material = material_cache.load_material(combiner.Mask)

    material1_outputs = import_material(material_cache, node_tree, material1, inputs)
    material2_outputs = import_material(material_cache, node_tree, material2, inputs)
    mask_outputs = import_material(material_cache, node_tree, mask_material, inputs)

    def create_color_combiner_mix_node(blend_type: str) -> bpy.types.ShaderNode:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = blend_type
        mix_node.inputs['Fac'].default_value = 1.0

        if combiner.InvertMask:
            node_tree.links.new(mix_node.inputs['Color2'], material1_outputs.color_socket)
            node_tree.links.new(mix_node.inputs['Color1'], material2_outputs.color_socket)
        else:
            node_tree.links.new(mix_node.inputs['Color1'], material1_outputs.color_socket)
            node_tree.links.new(mix_node.inputs['Color2'], material2_outputs.color_socket)

        return mix_node

    # Color Operation
    if combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material1:
        outputs.color_socket = material1_outputs.color_socket
    elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Material2:
        outputs.color_socket = material2_outputs.color_socket
    elif combiner.CombineOperation == EColorOperation.CO_Multiply:
        mix_node = create_color_combiner_mix_node('MULTIPLY')
        if combiner.Modulate2x or combiner.Modulate4x:
            modulate_node = node_tree.nodes.new('ShaderNodeVectorMath')
            modulate_node.operation = 'SCALE'
            modulate_node.inputs['Scale'].default_value = 4.0 if combiner.Modulate4x else 2.0
            node_tree.links.new(modulate_node.inputs['Vector'], mix_node.outputs[2])
            outputs.color_socket = modulate_node.outputs['Vector']
        else:
            outputs.color_socket = mix_node.outputs[0]
    elif combiner.CombineOperation == EColorOperation.CO_Add:
        mix_node = create_color_combiner_mix_node('ADD')
        outputs.color_socket = mix_node.outputs[2]
    elif combiner.CombineOperation == EColorOperation.CO_Subtract:
        mix_node = create_color_combiner_mix_node('SUBTRACT')
        outputs.color_socket = mix_node.outputs[2]
    elif combiner.CombineOperation == EColorOperation.CO_AlphaBlend_With_Mask:
        mix_node = create_color_combiner_mix_node('MIX')
        node_tree.links.new(mix_node.inputs['Fac'], mask_outputs.alpha_socket)
        outputs.color_socket = mix_node.outputs[0]
    elif combiner.CombineOperation == EColorOperation.CO_Add_With_Mask_Modulation:
        mix_node = create_color_combiner_mix_node('ADD')
        outputs.color_socket = mix_node.outputs[2]
        # This doesn't use the Mask, but instead uses the alpha channel of Material 2, or if it hasn't got one,
        # modulates it on Material1.
        if material2_outputs.alpha_socket is not None:
            node_tree.links.new(mix_node.inputs['Fac'], material2_outputs.alpha_socket)
        else:
            node_tree.links.new(mix_node.inputs['Fac'], material1_outputs.alpha_socket)
    elif combiner.CombineOperation == EColorOperation.CO_Use_Color_From_Mask:   # dropped in UE3, apparently
        outputs.color_socket = mask_outputs.color_socket

    # Alpha Operation
    if combiner.AlphaOperation == EAlphaOperation.AO_Use_Mask:
        outputs.alpha_socket = mask_outputs.alpha_socket if mask_outputs else None
    elif combiner.AlphaOperation == EAlphaOperation.AO_Multiply:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'MULTIPLY'
        if material1_outputs.alpha_socket:
            node_tree.links.new(mix_node.inputs[1], material1_outputs.alpha_socket)
            node_tree.links.new(mix_node.inputs[2], material2_outputs.alpha_socket)
        outputs.alpha_socket = mix_node.outputs[0]
    elif combiner.AlphaOperation == EAlphaOperation.AO_Add:
        mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
        mix_node.blend_type = 'ADD'
        if material1_outputs.alpha_socket:
            node_tree.links.new(mix_node.inputs[6], material1_outputs.alpha_socket)
            node_tree.links.new(mix_node.inputs[7], material2_outputs.alpha_socket)
        outputs.alpha_socket = mix_node.outputs[2]
    elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material1:
        outputs.alpha_socket = material1_outputs.alpha_socket
    elif combiner.AlphaOperation == EAlphaOperation.AO_Use_Alpha_From_Material2:
        outputs.alpha_socket = material2_outputs.alpha_socket

    # NOTE: This is a bit of guess. Maybe investigate how this is actually determined.
    if material1_outputs is not None:
        outputs.size = material1_outputs.size
    elif material2_outputs is not None:
        outputs.size = material2_outputs.size
    elif mask_outputs is not None:
        outputs.size = mask_outputs.size

    return outputs


def import_material(material_cache: MaterialCache, node_tree: bpy.types.NodeTree, umaterial: UMaterial, inputs: MaterialSocketInputs) -> MaterialSocketOutputs:
    if isinstance(umaterial, UTexture):
        return import_texture(material_cache, node_tree, umaterial, inputs)
    elif isinstance(umaterial, UCombiner):
        return import_combiner(material_cache, node_tree, umaterial, inputs)
    elif isinstance(umaterial, UConstantColor):
        return import_constant_color(material_cache, node_tree, umaterial, inputs)
    elif isinstance(umaterial, UTexRotator):
        return import_tex_rotator(material_cache, node_tree, umaterial, inputs)
    elif isinstance(umaterial, UTexOscillator):
        return import_tex_oscillator(material_cache, node_tree, umaterial, inputs)
    elif isinstance(umaterial, UTexCoordSource):
        return import_tex_coord_source(material_cache, node_tree, umaterial, inputs)
    else:
        print(f'Unhandled material type {type(umaterial)}')


class UMATERIAL_OT_import(Operator, ImportHelper):
    bl_idname = 'import.umaterial'
    bl_label = 'Import Unreal Material'
    filename_ext = '.props.txt'
    filepath: StringProperty()
    filter_glob: StringProperty(default='*.props.txt', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='')

    def execute(self, context: bpy.types.Context):
        cache_path = 'C:\\dev\\bdk-git\\bdk-build'
        material_cache = MaterialCache(cache_path)

        reference = UReference.from_path(Path(self.filepath))

        umaterial = material_cache.load_material(reference)
        material_name = os.path.basename(self.filepath).strip('.props.txt')

        material = bpy.data.materials.new(material_name)
        material.use_nodes = True
        node_tree = material.node_tree
        node_tree.nodes.clear()

        # Add custom property with Unreal reference string.
        material['bdk_reference'] = str(reference)

        socket_inputs = MaterialSocketInputs()
        outputs = import_material(material_cache, node_tree, umaterial, socket_inputs)
        material.use_backface_culling = outputs.use_backface_culling
        material.blend_method = outputs.blend_method

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')
        diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')

        node_tree.links.new(diffuse_node.inputs['Color'], outputs.color_socket)

        if outputs.blend_method in ['CLIP', 'BLEND']:
            transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
            mix_node = node_tree.nodes.new('ShaderNodeMixShader')
            node_tree.links.new(mix_node.inputs['Fac'], outputs.alpha_socket)
            node_tree.links.new(mix_node.inputs[1], transparent_node.outputs['BSDF'])
            node_tree.links.new(mix_node.inputs[2], diffuse_node.outputs['BSDF'])
            node_tree.links.new(output_node.inputs['Surface'], mix_node.outputs['Shader'])
        else:
            node_tree.links.new(output_node.inputs['Surface'], diffuse_node.outputs['BSDF'])

        return {'FINISHED'}


classes = (
    UMATERIAL_OT_import,
)
