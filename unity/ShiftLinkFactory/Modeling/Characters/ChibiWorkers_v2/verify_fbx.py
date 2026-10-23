"""Independent FBX re-import verification; no source or output mutation."""
import bpy,json,math
from pathlib import Path
here=Path(__file__).resolve().parent
out=here.parents[2]/'Assets/Models/Characters/ChibiWorkers_v2'
result=[]
for name in ['ChibiWorker_Male','ChibiWorker_Female','ChibiWorker_PDA']:
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(out/(name+'.fbx')))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(meshes)==1,(name,'mesh count',len(meshes))
    mesh=meshes[0]
    assert mesh.data.materials and len(mesh.data.polygons)>100
    assert all(math.isfinite(c) for v in mesh.data.vertices for c in v.co)
    if name!='ChibiWorker_PDA':
        assert len(rigs)==1
        rig=rigs[0]
        assert len(rig.data.bones)==22
        assert any(m.type=='ARMATURE' and m.object==rig for m in mesh.modifiers)
        assert all(v.groups and abs(sum(g.weight for g in v.groups)-1)<.002 for v in mesh.data.vertices)
        assert mesh.data.uv_layers
        bpy.context.view_layer.update()
        pts=[mesh.matrix_world@v.co for v in mesh.data.vertices]
        # Imported FBX is returned to Blender's Z-up coordinates.
        height=max(p.z for p in pts)-min(p.z for p in pts)
        assert 1.65<height<1.80,(name,height)
        # Move an arm bone and evaluate the actual exported skinning.
        rest=[v.co.copy() for v in mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices]
        pb=rig.pose.bones['LeftUpperArm']; pb.rotation_mode='XYZ'; pb.rotation_euler.x=.35
        bpy.context.view_layer.update()
        posed=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        changed=sum((v.co-rest[i]).length>.001 for i,v in enumerate(posed.data.vertices))
        assert changed>100,(name,'no skin deformation')
        result.append({'name':name,'height_m':round(height,4),'bones':len(rig.data.bones),'deformed_vertices':changed,'fbx_reimport':'passed'})
    else:
        assert not rigs
        result.append({'name':name,'fbx_reimport':'passed'})
(here/'fbx_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('FBX_VERIFY_OK',json.dumps(result))
