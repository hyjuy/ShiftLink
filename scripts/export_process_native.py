"""Isolate editable models from the generated scene without partial scene copying."""
from pathlib import Path
import bpy
from mathutils import Vector

folder = Path(__file__).resolve().parents[1] / 'unity/ShiftLinkFactory/Modeling/EquipmentTypes'
for name in ['Equipment_HPU','Equipment_PDP','Equipment_CAU','Equipment_GR','Equipment_RT','Equipment_CV','Equipment_CV02','Material_Coil']:
    bpy.ops.wm.open_mainfile(filepath=str(folder / 'ShiftLink_detail.blend'))
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    root = scene.objects[name]
    origin = root.location.copy()
    keep = {root, *root.children_recursive}
    for obj in list(scene.objects):
        if obj not in keep and obj.type not in {'CAMERA','LIGHT'}:
            bpy.data.objects.remove(obj, do_unlink=True)
    root.location = (0,0,0)
    bpy.context.view_layer.update()
    if name=='Equipment_CAU' and not any(o.name.startswith('AirSupplyAnchor') for o in keep):
        anchor=bpy.data.objects.new('AirSupplyAnchor',None); scene.collection.objects.link(anchor)
        anchor.parent=root; anchor.location=(1.28,.3,.87); keep.add(anchor)
    if name=='Equipment_RT':
        platform=next(o for o in keep if o.name.startswith('RollerAssembly'))
        for obj in keep:
            if obj.name.startswith(('BearingCover','BearingGreaseNipple')):
                world=obj.matrix_world.copy(); obj.parent=platform; obj.matrix_world=world
    for obj in keep:
        if obj.type == 'MESH':
            obj.data = obj.data.copy()
    for obj in scene.objects:
        obj.hide_render = False
        if obj.type == 'LIGHT':
            obj.location -= origin
    camera = scene.camera
    camera.location = Vector((-6,-8,6))
    camera.rotation_euler = (Vector((0,0,1.6 if name=='Equipment_RT' else 1)) - camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale = 7.2 if name=='Equipment_RT' else 6.7 if name.endswith(('CV','CV02')) else 4.3
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / (name + '.blend')))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in keep:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.fbx(filepath=str(folder.parent.parent / 'Assets/Models/EquipmentTypes' / (name+'.fbx')),
        use_selection=True,object_types={'MESH','EMPTY'},axis_forward='-Z',axis_up='Y',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_custom_props=True,
        bake_anim=False,add_leaf_bones=False)
print('SHIFTLINK NATIVE EXPORT PASS: 8 isolated editable models')
