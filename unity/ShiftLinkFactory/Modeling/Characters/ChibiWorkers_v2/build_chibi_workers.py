"""Blender 5.2: original chibi worker pair from the user supplied reference.
Metres, Blender Z up/front -Y. Source T pose, separate posed presentation.
"""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
from mathutils.kdtree import KDTree
HERE=Path(__file__).resolve().parent
OUT=HERE.parents[2]/'Assets/Models/Characters/ChibiWorkers_v2'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
bpy.context.preferences.filepaths.save_version=0

def material(name,c,rough=.8):
    m=bpy.data.materials.new(name); m.diffuse_color=(*c,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough
    # A small emission contribution keeps the illustration palette in shadow.
    p.inputs['Emission Color'].default_value=(*c,1); p.inputs['Emission Strength'].default_value=.18
    return m
navy=material('Workwear - deep blue',(.025,.075,.245))
teal=material('Workwear - turquoise inserts',(.025,.43,.46))
yellow=material('Safety - sunshine yellow',(1,.67,.006),.6)
skin=material('Face - warm peach',(1,.55,.255))
ink=material('Details - midnight ink',(.004,.009,.028))
hair=material('Hair - charcoal',(.014,.019,.033))
glove=material('Gloves - charcoal',(.022,.028,.042))
boot=material('Boots - charcoal rubber',(.019,.024,.036))
frame=material('PDA - bumper grey',(.13,.16,.20))
screen=material('PDA - dark screen',(.015,.032,.052),.5)
uicolor=material('PDA - muted indicators',(.03,.46,.48))
coll=None; parts=[]

def finish(o,name,m,b=None):
    o.name=name
    for c in list(o.users_collection): c.objects.unlink(o)
    coll.objects.link(o); o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth=True
    if b:
        g=o.vertex_groups.new(name=b); g.add(list(range(len(o.data.vertices))),1,'REPLACE'); parts.append(o)
    return o

def ball(name,co,size,m,b=None,segments=24,rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=co)
    o=bpy.context.object; o.scale=size; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,m,b)

def box(name,co,size,m,b=None,bevel=.01):
    bpy.ops.mesh.primitive_cube_add(size=1,location=co)
    o=bpy.context.object; o.scale=size; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    mod=o.modifiers.new('Soft rounded edges','BEVEL'); mod.width=bevel; mod.segments=3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o,name,m,b)
    for p in o.data.polygons: p.use_smooth=False
    return o

def mesh(name,vertices,faces,m,b):
    d=bpy.data.meshes.new(name); d.from_pydata(vertices,[],faces); d.update()
    o=bpy.data.objects.new(name,d); coll.objects.link(o)
    return finish(o,name,m,b)

def shell(name,rings,m,b,n=40):
    v=[(x+rx*math.cos(i*2*math.pi/n),y+ry*math.sin(i*2*math.pi/n),z) for x,y,z,rx,ry in rings for i in range(n)]
    f=[tuple(reversed(range(n)))]
    for k in range(len(rings)-1):
        for i in range(n):
            j=(i+1)%n; f.append((k*n+i,k*n+j,(k+1)*n+j,(k+1)*n+i))
    f.append(tuple((len(rings)-1)*n+i for i in range(n)))
    return mesh(name,v,f,m,b)

def line(name,pts,r,m,b=None):
    d=bpy.data.curves.new(name,'CURVE'); d.dimensions='3D'; d.bevel_depth=r; d.bevel_resolution=3
    spl=d.splines.new('POLY'); spl.points.add(len(pts)-1)
    for p,v in zip(spl.points,pts): p.co=(*v,1)
    o=bpy.data.objects.new(name,d); coll.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o
    bpy.ops.object.convert(target='MESH'); return finish(bpy.context.object,name,m,b)

def patch(name,coords,depth,m,b,bevel=.008):
    # A rounded, extruded polygon on the front of the character.
    n=len(coords); vs=[(x,y,z) for x,y,z in coords]+[(x,y+depth,z) for x,y,z in coords]
    fs=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh(name,vs,fs,m,b)
    bpy.context.view_layer.objects.active=o; bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    # Recalculate polygon winding before beveling arbitrary profile polygons.
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    mod=o.modifiers.new('Rounded profile','BEVEL'); mod.width=bevel; mod.segments=3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return o

def head_shape(b):
    # Rounded squircle: the broad, almost flat face matches the chibi drawing.
    n=48; r=28; vs=[]
    sp=lambda v,e: math.copysign(abs(v)**e,v)
    for j in range(r+1):
        a=-math.pi/2+j*math.pi/r; ca=max(.00001,math.cos(a))
        for i in range(n):
            t=i*2*math.pi/n
            vs.append((.265*ca**.78*sp(math.cos(t),.82), .184*ca**.78*sp(math.sin(t),.82),1.225+.232*sp(math.sin(a),.78)))
    fs=[]
    for j in range(r):
        for i in range(n):
            k=(i+1)%n; fs.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    return mesh('Face - rounded chibi silhouette',vs,fs,skin,b)

def arm(side,s):
    # Continuous sleeve, with soft weights across the elbow.
    profile=[(.185,.068),(.205,.085),(.245,.088),(.30,.083),(.35,.078),(.38,.075),(.42,.071),(.48,.063),(.54,.058)]
    n=24; vs=[]
    for x,r in profile:
        for i in range(n):
            a=i*2*math.pi/n; vs.append((s*x,r*math.sin(a),.945+r*math.cos(a)))
    fs=[tuple(reversed(range(n)))]
    for j in range(len(profile)-1):
        for i in range(n):
            k=(i+1)%n; fs.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    fs.append(tuple((len(profile)-1)*n+i for i in range(n)))
    o=mesh('Sleeve - continuous volume',vs,fs,navy,side+'UpperArm')
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    a=o.vertex_groups.new(name=side+'UpperArm'); b=o.vertex_groups.new(name=side+'LowerArm')
    for v in o.data.vertices:
        w=max(0,min(1,(abs(v.co.x)-.35)/.065)); a.add([v.index],1-w,'REPLACE'); b.add([v.index],w,'REPLACE')
    ball('Sleeve - soft shoulder cap',(s*.19,0,.945),(.073,.082,.084),navy,side+'UpperArm')
    # Narrow yellow tapes are separate geometry, following the upper arm.
    for distance in [.287,.326]:
        pts=[(s*distance,.086*math.sin(i*2*math.pi/48),.945+.086*math.cos(i*2*math.pi/48)) for i in range(49)]
        line('Sleeve - yellow safety tape',pts,.010,yellow,side+'UpperArm')
    ball('Glove - rounded palm',(s*.590,-.003,.945),(.064,.042,.062),glove,side+'Hand')
    for i,L in enumerate([.034,.046,.05,.041]):
        ball('Glove - short finger',(s*(.641+L*.18),-.004,.909+i*.022),(L*.58,.019,.016),glove,side+'Hand',16,10)
    ball('Glove - thumb',(s*.594,-.014,.885),(.025,.028,.038),glove,side+'Hand',16,10)

def continuous_coverall(objects):
    # Union the torso and trouser volumes, retaining the nearby deform weights.
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]; bpy.ops.object.join(); source=bpy.context.object
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    tree=KDTree(len(source.data.vertices))
    for v in source.data.vertices:tree.insert(v.co,v.index)
    tree.balance()
    weights=[{source.vertex_groups[g.group].name:g.weight for g in v.groups} for v in source.data.vertices]
    target=source.copy(); target.data=source.data.copy(); coll.objects.link(target)
    bpy.ops.object.select_all(action='DESELECT'); target.select_set(True); bpy.context.view_layer.objects.active=target
    mod=target.modifiers.new('Continuous coverall volume','REMESH'); mod.mode='VOXEL'; mod.voxel_size=.007; mod.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod=target.modifiers.new('Soft cloth silhouette','SMOOTH'); mod.factor=.55; mod.iterations=4; bpy.ops.object.modifier_apply(modifier=mod.name)
    tris=sum(len(f.vertices)-2 for f in target.data.polygons)
    mod=target.modifiers.new('Game mesh reduction','DECIMATE'); mod.ratio=min(1,8500/tris); bpy.ops.object.modifier_apply(modifier=mod.name)
    for g in list(target.vertex_groups):target.vertex_groups.remove(g)
    groups={g.name:target.vertex_groups.new(name=g.name) for g in source.vertex_groups}
    for v in target.data.vertices:
        combined={}
        for co,i,d in tree.find_n(v.co,4):
            factor=1/max(d,.0001)**2
            for n,w in weights[i].items():combined[n]=combined.get(n,0)+w*factor
        total=sum(combined.values())
        for n,w in combined.items():
            if w>0:groups[n].add([v.index],w/total,'REPLACE')
    bpy.data.objects.remove(source,do_unlink=True); target.name='Coverall - continuous body and legs'
    return target

def character(name,female=False):
    global coll,parts
    coll=bpy.data.collections.new(name); scene.collection.children.link(coll); parts=[]
    shell('Coverall - round torso',[(0,0,.49,.17,.112),(0,0,.54,.207,.135),(0,0,.66,.204,.143),(0,0,.82,.185,.132),(0,0,.94,.193,.112),(0,0,.997,.126,.081)],navy,'Chest')
    # Torso stretches continuously through hips/spine/chest.
    o=parts[-1]
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    g1=o.vertex_groups.new(name='Hips'); g2=o.vertex_groups.new(name='Spine'); g3=o.vertex_groups.new(name='Chest')
    for v in o.data.vertices:
        a=max(0,min(1,(.68-v.co.z)/.14)); c=max(0,min(1,(v.co.z-.74)/.15)); mid=1-a-c
        for g,w in [(g1,a),(g2,mid),(g3,c)]:
            if w>0:g.add([v.index],w,'REPLACE')
    ball('Neck',(0,0,1.006),(.062,.058,.066),skin,'Neck')
    for s in [-1,1]:
        side='Left' if s>0 else 'Right'; x=s*.122
        leg=shell('Trousers - short rounded leg',[(s*.142,0,.195,.088,.102),(s*.142,0,.23,.099,.11),(s*.136,0,.34,.103,.116),(s*.123,0,.46,.108,.117),(s*.106,0,.58,.101,.11)],navy,side+'UpperLeg')
        for g in list(leg.vertex_groups): leg.vertex_groups.remove(g)
        up=leg.vertex_groups.new(name=side+'UpperLeg'); low=leg.vertex_groups.new(name=side+'LowerLeg')
        for v in leg.data.vertices:
            w=max(0,min(1,(v.co.z-.32)/.10)); up.add([v.index],w,'REPLACE'); low.add([v.index],1-w,'REPLACE')
        shell('Trousers - yellow band',[(s*.14,0,.269,.102,.115),(s*.14,0,.300,.103,.117)],yellow,side+'LowerLeg')
        shell('Boot - soft round toe',[(s*.145,-.033,0,.09,.12),(s*.145,-.05,.04,.113,.155),(s*.145,-.05,.085,.117,.158),(s*.145,-.032,.15,.105,.132),(s*.145,0,.213,.081,.084)],boot,side+'Foot')
        # Broad teal side inserts, avoiding the detailed pockets of the old version.
        patch('Coverall - teal side panel',[(s*.151,-.094,.90),(s*.187,-.075,.85),(s*.210,-.084,.58),(s*.168,-.115,.60)],.018,teal,'Chest',.012)
        patch('Shoulder - yellow strap',[(s*.105,-.095,.983),(s*.144,-.098,.962),(s*.167,-.120,.888),(s*.135,-.136,.88)],.012,yellow,'Chest',.004)
        patch('Collar - folded blue',[(s*.035,-.085,1.003),(s*.096,-.089,.996),(s*.112,-.108,.938),(s*.041,-.132,.95),(s*.001,-.138,.916)],.012,navy,'Chest',.004)
        arm(side,s)
    head_shape('Head')
    for s in [-1,1]:
        ball('Ear - round',(s*.266,-.007,1.205),(.061,.037,.069),skin,'Head')
        line('Ear - inner curve',[(s*(.264+.023*math.cos(t)),-.044,1.211+.025*math.sin(t)) for t in [i*.12 for i in range(16)]],.005,material_ear,'Head')
        # Flat black ovals and no nose: deliberate match to the supplied drawing.
        ball('Eye - oval dot',(s*.091,-.186,1.232),(.020,.010,.033),ink,'Head',24,16)
        line('Eyebrow - simple arc',[(s*(.09+.031*math.cos(t)),-.177,1.310+.015*math.sin(t)) for t in [i*math.pi/18 for i in range(19)]],.006,ink,'Head')
    line('Smile - soft U',[(.037*math.cos(t),-.191,1.154-.020*math.sin(t)) for t in [i*math.pi/24 for i in range(25)]],.005,ink,'Head')
    # Dark cap sits behind the face. Broad planar locks make a readable swept fringe.
    ball('Hair - cap',(0,.028,1.384),(.274,.187,.109),hair,'Head')
    fringe=[(-.249,-.13,1.43),(.188,-.14,1.435),(.116,-.174,1.372),(.031,-.184,1.334),(.052,-.184,1.365),(-.054,-.181,1.327),(-.033,-.18,1.359),(-.144,-.165,1.321),(-.199,-.15,1.257),(-.222,-.139,1.28)]
    if female:
        fringe=[(-.247,-.13,1.43),(.092,-.18,1.445),(.030,-.185,1.376),(-.055,-.184,1.332),(-.140,-.17,1.305),(-.193,-.14,1.25),(-.222,-.13,1.274)]
    patch('Hair - swept fringe',fringe,.037,hair,'Head',.008)
    for s in [-1,1]:
        ball('Hair - temple',(s*.239,-.052,1.346),(.029,.095,.094),hair,'Head')
    if female:
        ball('Hair - low bun',(-.225,.142,1.065),(.083,.078,.079),hair,'Head')
        lock=ball('Hair - side lock',(.239,-.075,1.245),(.021,.044,.131),hair,'Head'); lock.rotation_euler.y=-.13
    # Simple dome and rolled brim; the reference has no industrial ribs.
    rings=[]
    for i in range(17):
        a=i/16*math.pi/2; r=max(.001,math.cos(a))
        rings.append((0,.008,1.438+.281*math.sin(a),.302*r,.235*r))
    shell('Helmet - smooth yellow dome',rings,yellow,'Head',64)
    shell('Helmet - dark lower trim',[(0,-.009,1.416,.328,.259),(0,-.009,1.429,.332,.264)],ink,'Head',64)
    shell('Helmet - rolled yellow brim',[(0,-.009,1.425,.331,.263),(0,-.009,1.431,.342,.271),(0,-.009,1.447,.342,.271),(0,-.009,1.455,.330,.258)],yellow,'Head',64)
    volumes=[o for o in parts if o.name.startswith(('Coverall - round torso','Trousers - short rounded leg'))]
    selected=set(volumes); parts=[o for o in parts if o not in selected]
    parts.append(continuous_coverall(volumes))
    # Join the character only, preserving materials and skin weights.
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]; bpy.ops.object.join(); body=bpy.context.object; body.name=name+'_Body'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.smart_project(angle_limit=1.1519,island_margin=.012); bpy.ops.object.mode_set(mode='OBJECT')
    data=bpy.data.armatures.new(name+'_Skeleton'); rig=bpy.data.objects.new(name,data); coll.objects.link(rig)
    bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True); bpy.context.view_layer.objects.active=rig; bpy.ops.object.mode_set(mode='EDIT')
    def bone(n,h,t,p=None):
        b=data.edit_bones.new(n); b.head=h; b.tail=t
        if p:b.parent=data.edit_bones[p]
    bone('Root',(0,0,0),(0,0,.15)); bone('Hips',(0,0,.56),(0,0,.66),'Root')
    bone('Spine',(0,0,.66),(0,0,.82),'Hips'); bone('Chest',(0,0,.82),(0,0,.98),'Spine')
    bone('Neck',(0,0,.98),(0,0,1.04),'Chest'); bone('Head',(0,0,1.04),(0,0,1.44),'Neck')
    for s in [-1,1]:
        side='Left' if s>0 else 'Right'
        bone(side+'UpperLeg',(s*.106,0,.56),(s*.136,0,.36),'Hips'); bone(side+'LowerLeg',(s*.136,0,.36),(s*.145,0,.18),side+'UpperLeg')
        bone(side+'Foot',(s*.145,0,.18),(s*.145,-.12,.075),side+'LowerLeg'); bone(side+'Toes',(s*.145,-.12,.075),(s*.145,-.19,.065),side+'Foot')
        bone(side+'Shoulder',(s*.07,0,.945),(s*.19,0,.945),'Chest'); bone(side+'UpperArm',(s*.19,0,.945),(s*.38,0,.945),side+'Shoulder')
        bone(side+'LowerArm',(s*.38,0,.945),(s*.54,0,.945),side+'UpperArm'); bone(side+'Hand',(s*.54,0,.945),(s*.65,0,.945),side+'LowerArm')
    bpy.ops.object.mode_set(mode='OBJECT')
    mod=body.modifiers.new('Skeleton deformation','ARMATURE'); mod.object=rig; body.parent=rig; rig.show_in_front=True
    rig['reference']='User supplied chibi worker pair, 2026-10-23'
    rig['status']='Chibi prototype v2. No facial bones, individual finger bones or animation clips.'
    return rig,body
material_ear=material('Face - warm ear detail',(.57,.21,.085))
male,mm=character('ChibiWorker_Male'); female,fm=character('ChibiWorker_Female',True)
coll=bpy.data.collections.new('PDA_Accessory'); scene.collection.children.link(coll)
pieces=[]
for name,co,size,m,bev in [('PDA - rubber bumper',(0,0,0),(.179,.039,.238),glove,.021),('PDA - grey frame',(0,-.021,0),(.154,.009,.208),frame,.014),('PDA - screen',(0,-.027,0),(.132,.005,.181),screen,.009)]:pieces.append(box(name,co,size,m,bevel=bev))
bpy.ops.object.select_all(action='DESELECT')
for o in pieces:o.select_set(True)
bpy.context.view_layer.objects.active=pieces[0]; bpy.ops.object.join(); pda=bpy.context.object; pda.name='ChibiWorker_PDA'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)

def export(name,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,object_types={'ARMATURE','MESH'},axis_forward='-Z',axis_up='Y',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',add_leaf_bones=False,bake_anim=False,use_mesh_modifiers=True,mesh_smooth_type='FACE')
export('ChibiWorker_Male',[male,mm]); export('ChibiWorker_Female',[female,fm]); export('ChibiWorker_PDA',[pda])
report={'reference':'supplied chibi illustration','rest_pose':'T','units':'metres','clips':0,'characters':[]}
for rig,body in [(male,mm),(female,fm)]:
    assert len(rig.data.bones)==22 and body.data.uv_layers
    assert all(v.groups and abs(sum(g.weight for g in v.groups)-1)<.001 for v in body.data.vertices)
    assert all(g.name in rig.data.bones for g in body.vertex_groups)
    tris=sum(len(p.vertices)-2 for p in body.data.polygons)
    assert tris<65000
    report['characters'].append({'name':rig.name,'vertices':len(body.data.vertices),'triangles':tris,'bones':22,'materials':len(body.data.materials),'height_m':round(max(v.co.z for v in body.data.vertices)-min(v.co.z for v in body.data.vertices),4)})
for path in OUT.glob('*.fbx'):assert path.stat().st_size>10000
male.location.x=-.66; female.location.x=.66; pda.location=(1.25,0,.8)
scene['README']='T-pose source. Separate posed studio scene. Unity FBX assets under Assets/Models/Characters/ChibiWorkers_v2.'
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'ChibiWorkers_TPose.blend'))

# Poses are deliberately saved separately from the neutral FBX assets.
def direction(rig,name,desired):
    bpy.context.view_layer.update(); pb=rig.pose.bones[name]
    rest=pb.bone.matrix_local.to_quaternion(); axis=(pb.bone.tail_local-pb.bone.head_local).normalized()
    target=axis.rotation_difference(Vector(desired).normalized())@rest
    parent_deform=pb.parent.matrix.to_quaternion()@pb.parent.bone.matrix_local.to_quaternion().inverted()
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=(parent_deform@rest).inverted()@target
    bpy.context.view_layer.update()
for rig in [male,female]:
    for s in [-1,1]:
        side='Left' if s>0 else 'Right'
        direction(rig,side+'UpperArm',(s*.36,0,-.933))
        direction(rig,side+'LowerArm',(-s*.65,-.72,.25))
# Male left hand waves; female holds a tablet in both hands.
direction(male,'LeftUpperArm',(.866,0,-.5)); direction(male,'LeftLowerArm',(.309,-.06,.949))
pda.location=(-.66-.076,-.196,.852); pda.rotation_euler=(math.radians(-9),0,math.radians(-10))
pda2=pda.copy(); pda2.data=pda.data; pda.users_collection[0].objects.link(pda2); pda2.name='PDA_Female_Presentation'
pda2.location=(.66,-.196,.854); pda2.rotation_euler=(math.radians(-9),0,math.radians(2))
# Render-only outlines via Freestyle. Unity materials deliberately remain ordinary.
coll=bpy.data.collections.new('Studio - presentation only'); scene.collection.children.link(coll)
floor=box('Studio floor',(0,0,-.025),(200,200,.04),material('Studio - midnight',(.009,.016,.032)),bevel=.001)
world=bpy.data.worlds.new('Chibi studio'); world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.035,.052,.09,1); world.node_tree.nodes['Background'].inputs[1].default_value=.3; scene.world=world

def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
def light(name,co,power,color,size):
    d=bpy.data.lights.new(name,'AREA'); d.energy=power; d.color=color; d.shape='DISK'; d.size=size
    o=bpy.data.objects.new(name,d); coll.objects.link(o); o.location=co; aim(o,(0,0,.85))
light('Key',(-3,-4,5),260,(1,.86,.69),4)
light('Fill',(3,-3,2),160,(.66,.80,1),3)
light('Rim',(0,2,4),350,(1,.79,.35),3)
d=bpy.data.cameras.new('Chibi review camera'); camera=bpy.data.objects.new('Chibi review camera',d); coll.objects.link(camera)
camera.location=(.35,-8,2.6); aim(camera,(0,0,.86)); d.type='ORTHO'; d.ortho_scale=2.86; scene.camera=camera
scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.render.resolution_x=1500; scene.render.resolution_y=1150; scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'
scene.view_settings.exposure=-.35
scene.render.use_freestyle=True
ls=scene.view_layers[0].freestyle_settings.linesets[0]
ls.select_crease=False; ls.select_border=True; ls.select_silhouette=True; ls.select_material_boundary=False
ls.linestyle.color=(.003,.009,.035); ls.linestyle.thickness=2.6
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(HERE/'ChibiWorkers_Preview.png')
(HERE/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'ChibiWorkers_Presentation.blend'))
bpy.ops.render.render(write_still=True)
print('CHIBI_BUILD_OK',json.dumps(report))
