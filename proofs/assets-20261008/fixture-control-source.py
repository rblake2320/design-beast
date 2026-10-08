from pathlib import Path
OUTPUT=Path(__file__).resolve().parent
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,.5))
o=bpy.context.object;o.name='OneMeterControl';o.scale=(1,2,1)
m=bpy.data.materials.new('AmberControl');m.diffuse_color=(.8,.28,.04,1);m.use_nodes=True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.8,.28,.04,1)
o.data.materials.append(m)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT/'control.glb'),export_format='GLB')
