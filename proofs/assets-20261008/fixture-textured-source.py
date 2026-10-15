from pathlib import Path
OUTPUT=Path(__file__).resolve().parent
import bpy,math
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
bpy.ops.object.empty_add(location=(.25,-.1,0));parent=bpy.context.object;parent.rotation_euler.z=math.pi/6
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,.5));obj=bpy.context.object;obj.name='TexturedScaleControl';obj.parent=parent;obj.scale=(1.2,.6,1.5)
image=bpy.data.images.new('CheckerControl',width=16,height=16)
pixels=[]
for y in range(16):
 for x in range(16): pixels.extend((.1,.45,.8,1) if ((x//4+y//4)%2) else (.9,.65,.2,1))
image.pixels=pixels;image.pack()
mat=bpy.data.materials.new('EmbeddedTexture');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/'textured-control.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUTPUT/'textured-control.glb'),export_format='GLB')
