"""Local Blender asset authoring; synthetic dimensions, no MES code changes."""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

PROJECT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT / 'unity/ShiftLinkFactory/Assets/Models/Equipment'
OUTPUT = PROJECT / 'unity/ShiftLinkFactory/Modeling'
ASSETS.mkdir(parents=True, exist_ok=True)
(OUTPUT / 'Previews').mkdir(parents=True, exist_ok=True)
(OUTPUT / 'Equipment').mkdir(parents=True, exist_ok=True)
CATALOG = json.loads((PROJECT / 'docs/data/reference/00_plant_and_relations.json').read_text(encoding='utf-8'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_percentage = 100
scene.world.color = (.12, .12, .12)
scene.view_settings.view_transform = 'AgX'
palette = {
    'blue': (.035, .17, .27, 1), 'frame': (.045, .075, .1, 1),
    'steel': (.48, .55, .61, 1), 'silver': (.69, .73, .76, 1),
    'yellow': (.94, .55, .055, 1), 'belt': (.045, .054, .063, 1),
    'white': (.76, .8, .81, 1), 'black': (.012, .02, .027, 1),
    'green': (.04, .6, .34, 1), 'red': (.66, .06, .035, 1),
    'oil': (.14, .68, .73, 1), 'air': (.13, .36, .88, 1),
}
mats = {}
for name, color in palette.items():
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = color
    shader.inputs['Metallic'].default_value = .85 if name in ('steel', 'silver') else .05
    shader.inputs['Roughness'].default_value = {'steel': .34, 'silver': .23, 'belt': .82, 'black': .65, 'frame': .52}.get(name, .4)
    mats[name] = mat


def empty(name, parent=None, loc=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    obj.empty_display_size = .15
    return obj


def finish(obj, name, color, parent, bevel=0):
    obj.name = name
    obj.parent = parent
    obj.data.materials.append(mats[color])
    if bevel:
        modifier = obj.modifiers.new('Machined edges', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        normal = obj.modifiers.new('Surface normals', 'WEIGHTED_NORMAL')
        bpy.ops.object.modifier_apply(modifier=normal.name)
    return obj


def box(name, loc, size, color, parent, bevel=.012):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, color, parent, min(bevel, min(size) / 4))


def cylinder(name, loc, radius, depth, color, parent, axis='Z', vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    if axis == 'X':
        obj.rotation_euler[1] = math.pi / 2
    elif axis == 'Y':
        obj.rotation_euler[0] = math.pi / 2
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return finish(obj, name, color, parent)


def pipe(name, points, radius, color, parent):
    # Trim hard routing corners into short swept bends; keep connection endpoints exact.
    route = [Vector(p) for p in points]
    rounded = [route[0]]
    for before, corner, after in zip(route, route[1:], route[2:]):
        incoming, outgoing = corner-before, after-corner
        if incoming.length > 1e-6 and outgoing.length > 1e-6 and incoming.normalized().dot(outgoing.normalized()) < .97:
            trim = min(radius*3, incoming.length*.3, outgoing.length*.3)
            start = corner-incoming.normalized()*trim
            end = corner+outgoing.normalized()*trim
            rounded.extend((1-t)**2*start+2*(1-t)*t*corner+t*t*end for t in (0, .2, .4, .6, .8, 1))
        else:
            rounded.append(corner)
    rounded.append(route[-1])
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new('POLY')
    spline.points.add(len(rounded) - 1)
    for point, value in zip(spline.points, rounded):
        point.co = (*value, 1)
    obj = bpy.data.objects.new(name, curve)
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.select_set(False)
    return finish(obj, name, color, parent)


def label(text, loc, size, parent, color='white'):
    bpy.ops.object.text_add(location=loc, rotation=(math.pi/2, 0, 0))
    obj = bpy.context.object
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = 'CENTER'
    obj.data.extrude = .001
    bpy.ops.object.convert(target='MESH')
    return finish(obj, 'Label_' + text, color, parent)


def feet(root, length, width, top=.75):
    for x in (-length/2 + .25, length/2 - .25):
        for y in (-width/2, width/2):
            box('Leg', (x, y, top/2), (.12, .12, top), 'frame', root)
            box('FootPlate', (x, y, .035), (.28, .26, .07), 'steel', root)
            for dx in (-.09, .09):
                cylinder('AnchorBolt', (x+dx, y, .08), .025, .025, 'silver', root, vertices=6)


def motor(root, loc, axis='X'):
    x, y, z = loc
    body = empty('Motor', root)
    cylinder('MotorBody', loc, .22, .64, 'blue', body, axis)
    for i in range(10):
        a = 2*math.pi*i/10
        if axis == 'X':
            fin = box('CoolingFin', (x, y+.215*math.cos(a), z+.215*math.sin(a)), (.5, .06, .018), 'blue', body, .002)
            fin.rotation_euler[0] = a
        else:
            fin = box('CoolingFin', (x+.215*math.cos(a), y+.215*math.sin(a), z), (.06, .018, .5), 'blue', body, .002)
            fin.rotation_euler[2] = a
    cylinder('FanCover', (x-.38, y, z) if axis == 'X' else (x,y,z+.38), .24, .12, 'frame', body, axis)
    box('TerminalBox', (x,y,z+.27) if axis=='X' else (x+.27,y,z), (.25,.22,.16), 'frame', body)
    for offset in (-.29,.29):
        cylinder('MotorEndShield', (x+offset,y,z) if axis=='X' else (x,y,z+offset), .235,.045,'blue',body,axis)
    fan = (x-.445,y,z) if axis=='X' else (x,y,z+.445)
    cylinder('FanGrilleRecess',fan,.193,.009,'black',body,axis)
    for offset in (-.14,-.07,0,.07,.14):
        span=2*math.sqrt(.19**2-offset**2)
        box('FanGrilleBar',(fan[0]-.006,y+offset,z) if axis=='X' else (x+offset,y,fan[2]+.006),(.012,.012,span) if axis=='X' else (.012,span,.012),'frame',body,.002)
    if axis=='X':
        for yoff in (-.19,.19):
            box('MotorMountFoot',(x,y+yoff,z-.28),(.49,.16,.10),'blue',body,.006)
            box('MotorPedestal',(x,y+yoff,.31),(.58,.21,.14),'steel',body,.006)
            for xoff in (-.19,.19):
                cylinder('MotorMountBolt',(x+xoff,y+yoff,z-.216),.021,.035,'silver',body,vertices=6)
    else:
        cylinder('MotorMountFlange',(x,y,z-.34),.29,.065,'steel',body)
        for a in (math.pi/4,3*math.pi/4,5*math.pi/4,7*math.pi/4):
            cylinder('MotorMountBolt',(x+.25*math.cos(a),y+.25*math.sin(a),z-.295),.02,.025,'silver',body,vertices=6)
    return body


def gauge(root, loc, tag):
    x,y,z = loc
    cylinder('GaugeRim_'+tag, loc, .095, .05, 'silver', root, 'Y')
    cylinder('GaugeFace_'+tag, (x,y-.029,z), .081, .012, 'white', root, 'Y')
    needle=box('GaugeNeedle_'+tag,(x+.02,y-.038,z+.015),(.085,.008,.009),'black',root,.001)
    needle.rotation_euler[1]=-.6
    cylinder('GaugeNeedleHub_'+tag,(x,y-.045,z),.012,.01,'black',root,'Y')
    cylinder('GaugeStem_'+tag,(x,y,z-.12),.021,.075,'silver',root,vertices=6)
    for i in range(13):
        a=math.radians(-45+i*22.5)
        tick=box('GaugeGraduation_'+tag,(x+.067*math.cos(a),y-.039,z+.067*math.sin(a)),(.013 if i%3==0 else .007,.003,.003),'black',root,.0005)
        tick.rotation_euler[1]=-a


def hydraulic(root, name, loc, height=.35):
    x,y,z=loc
    cylinder(name+'_Barrel',loc,.095,height,'blue',root)
    cylinder(name+'_Rod',(x,y,z+height*.55),.041,height*.8,'silver',root)
    pipe(name+'_Hose',[(x+.12,y,z),(x+.22,y,z),(x+.22,y,z-.2)],.018,'oil',root)


def roller_table(root, code):
    count=16 if code=='RT-02' else 12
    length=5.8 if code=='RT-02' else 4.8
    width=1.5
    feet(root,length,width)
    platform=empty('LiftPlatform' if code=='RT-02' else 'RollerAssembly',root)
    for y in (-.79,.79):
        box('SideFrame',(0,y,.89),(length,.15,.32),'blue',platform)
        box('SideSafetyStripe',(0,y-.081,.89),(length-.15,.012,.08),'yellow',platform,.002)
        for z in (.735,1.035):
            box('ChannelFlange',(0,y,z),(length,.23,.025),'blue',platform,.003)
    for x in (-length/2+.3,0,length/2-.3):
        box('CrossBeam',(x,0,.75),(.14,1.5,.14),'frame',platform)
    for i in range(count):
        x=-length/2+.22+i*(length-.44)/(count-1)
        rolling=empty('Roller_%02d'%(i+1),platform,(x,0,1.08))
        cylinder('RollerShell',(0,0,0),.12,1.45,'steel',rolling,'Y')
        cylinder('RollerShaft',(0,0,0),.039,1.78,'silver',rolling,'Y')
        for y in (-.87,.87):
            box('BearingBlock',(x,y,1.08),(.19,.12,.19),'frame',platform)
    # Unity coil top: 1.22 anchor + .02 path offset + .14 load offset + 1.20 diameter.
    # Keep .10 m below the jaw even at its illustrative .06 m downward stroke.
    coil_top=1.22+.02+.14+1.20
    jaw_center=coil_top+.10+.06+.11/2
    clamp_raise=jaw_center-1.43
    clamp=empty('ClampSlide',root)
    for y in (-.9,.9):
        box('ClampGuide',(length*.25,y,1.35+clamp_raise/2),(.12,.14,.65+clamp_raise),'yellow',root)
    box('ClampBridge',(length*.25,0,1.7+clamp_raise),(.2,1.95,.16),'yellow',root)
    box('ClampJaw',(length*.25,0,jaw_center),(.28,1.25,.11),'frame',clamp)
    for y in (-.38,.38):
        hydraulic(root,'ClampCylinder',(length*.25,y,1.68+clamp_raise),.19)
    if code=='RT-02':
        for x in (-1.6,1.6):
            hydraulic(root,'LiftCylinder',(x,0,.48),.4)
            for y in (-.45,.45):
                box('LiftGuide',(x,y,.47),(.12,.12,.75),'steel',root)
    # Preserve the lower side-feed route while raising its upper endpoint with the clamp.
    pipe('HydraulicFeed',[(-length/2,.94,.4),(length/2,.94,.4),(length/2,.94,1.55+clamp_raise)],.026,'oil',root)
    cylinder('DriveInput',(-length/2+.22,1.07,1.08),.09,.34,'steel',root,'Y')
    label(code,(0,-.877,.86),.2,root)
    root['roller_count']=count
    root['transport_surface_z_m']=1.20
    for y in (-.94,.94):
        box('ChainGuard',(0,y,1.0),(length,.09,.26),'yellow',root,.02)
        for i in range(count):
            x=-length/2+.22+i*(length-.44)/(count-1)
            cover=cylinder('BearingCover',(x,y*1.055,1.08),.065,.025,'steel',platform,'Y')
            # Children travel with the existing cover when Unity clones the RT-02 bearings.
            for dx in (-.048,.048):
                bolt=cylinder('BearingCapFastener',(x+dx,y*1.079,1.08),.012,.018,'silver',platform,'Y',6)
                bpy.context.view_layer.update()
                world=bolt.matrix_world.copy()
                bolt.parent=cover
                bolt.matrix_world=world
            cylinder('BearingGreaseNipple',(x,y*1.075,1.11),.012,.025,'silver',platform,'Y',6)
    for x in (-length/2+.3,0,length/2-.3):
        for y in (-.75,.75):
            box('FrameGusset',(x,y,.69),(.21,.07,.25),'blue',root)
    for x in (-length/2+.38,length/2-.38):
        for y in (-.75,.75):
            brace=box('LegKneeBrace',(x,y,.59),(.08,.09,.45),'frame',root,.004)
            brace.rotation_euler[1]=.55 if x<0 else -.55


def gearbox(root, code):
    box('Skid',(0,0,.12),(2.3,1.1,.24),'frame',root)
    box('GearHousing',(.43,0,.65),(1.05,.83,.95),'blue',root,.06)
    box('GearInspectionCover',(.43,0,1.15),(.74,.55,.05),'steel',root)
    for x in (.12,.76):
        for y in (-.36,.36):
            cylinder('HousingBolt',(x,y,1.17),.035,.035,'silver',root,vertices=6)
    motor(root,(-.68,0,.64))
    cylinder('CouplingGuard',(-.13,0,.64),.25,.24,'yellow',root,'X')
    rotating=empty('OutputShaft',root,(1.09,0,.67))
    cylinder('OutputShaftMesh',(0,0,0),.105,.5,'silver',rotating,'X')
    cylinder('OutputFlange',(.04,0,0),.2,.09,'steel',rotating,'X')
    box('BearingSensor',(.55,-.44,.85),(.11,.055,.09),'yellow',root)
    label(code,(.4,-.437,.64),.16,root)
    box('SplitHousingSeam',(.43,0,.78),(1.09,.87,.028),'frame',root,.003)
    for x in (.02,.24,.62,.84):
        for y in (-.425,.425):
            cylinder('SplitHousingBolt',(x,y,.81),.025,.04,'silver',root,vertices=6)
    for x in (.1,.78):
        cylinder('BearingCover',(x,-.44,.66),.16,.06,'blue',root,'Y')
        for i in range(8):
            a=i*math.pi/4
            cylinder('BearingCoverBolt',(x+.13*math.cos(a),-.478,.66+.13*math.sin(a)),.015,.02,'silver',root,'Y',6)
    for x in (.14,.3,.46,.62,.78):
        box('HousingRib',(x,.43,.57),(.035,.055,.5),'blue',root,.005)
        box('CastingRib',(x,-.43,.96),(.035,.055,.23),'blue',root,.005)
    for y in (-.36,.36):
        box('GearMountFlange',(.43,y,.25),(1.12,.19,.08),'blue',root,.006)
        for x in (.02,.84):
            cylinder('GearMountBolt',(x,y,.31),.027,.04,'silver',root,vertices=6)
    for y in (-.22,.22):
        box('CouplingGuardFoot',(-.13,y,.38),(.28,.055,.05),'yellow',root,.004)
    for i in range(5):
        a=math.pi*.22+i*math.pi*.14
        vent=box('CouplingGuardVent',(-.13,.252*math.cos(a),.64+.252*math.sin(a)),(.13,.006,.023),'frame',root,.002)
        vent.rotation_euler[0]=a
    for i in range(6):
        a=i*math.pi/3
        cylinder('OutputFlangeBolt',(.095,.15*math.cos(a),.15*math.sin(a)),.018,.02,'silver',rotating,'X',6)
    box('OutputShaftKey',(.15,0,.105),(.25,.038,.018),'steel',rotating,.002)
    cylinder('OilBreather',(.7,.18,1.23),.04,.12,'black',root)
    cylinder('OilDrainPlug',(.78,-.455,.3),.03,.03,'silver',root,'Y',6)
    for x in (-.98,.98):
        for y in (-.45,.45):
            cylinder('SkidAnchor',(x,y,.26),.032,.035,'silver',root,vertices=6)


def hpu(root, code):
    box('Reservoir',(0,0,.55),(1.75,1.1,1.0),'blue',root,.04)
    box('TankLidGasket',(0,0,1.048),(1.78,1.12,.014),'black',root,.003)
    box('TankLid',(0,0,1.07),(1.81,1.15,.03),'blue',root,.005)
    for x in (-.75,0,.75):
        for y in (-.49,.49):
            cylinder('TankLidBolt',(x,y,1.094),.018,.019,'silver',root,vertices=6)
    for x in (-.68,.68):
        box('TankFoot',(x,0,.07),(.2,1.25,.14),'frame',root)
    motor(root,(-.32,0,1.42),'Z')
    cylinder('PumpHousing',(-.32,0,1.09),.23,.21,'steel',root)
    box('ValveManifold',(.5,0,1.18),(.57,.44,.24),'steel',root)
    for x in (.34,.65):
        cylinder('SolenoidValve',(x,0,1.41),.07,.23,'black',root)
    cylinder('ReturnFilter',(.57,.34,1.48),.13,.45,'silver',root)
    cylinder('FilterCap',(.57,.34,1.73),.145,.035,'frame',root)
    cylinder('FillerBreather',(-.65,.29,1.14),.07,.17,'frame',root)
    box('OilSightGlass',(-.6,-.566,.65),(.12,.027,.4),'white',root)
    box('OilLevel',(-.6,-.586,.6),(.065,.012,.25),'oil',root,.002)
    gauge(root,(.52,-.25,1.49),'hpu_pressure')
    pipe('PressurePipe',[(.5,-.2,1.25),(.85,-.2,1.25),(.85,-.2,.6),(1,-.2,.6)],.028,'oil',root)
    pipe('ReturnPipe',[(1,.2,.6),(.82,.2,.6),(.82,.34,1.5),(.57,.34,1.5)],.028,'oil',root)
    pipe('PumpPressureHose',[(-.32,-.22,1.16),(-.32,-.34,1.16),(.35,-.34,1.2),(.35,-.2,1.2)],.024,'black',root)
    for x in (-.32,.35):
        cylinder('PressureHoseUnion',(x,-.23,1.16 if x<0 else 1.2),.038,.07,'silver',root,'Y',6)
    cylinder('TankDrainBoss',(-.68,-.585,.19),.048,.06,'blue',root,'Y')
    cylinder('TankDrainPlug',(-.68,-.627,.19),.028,.027,'silver',root,'Y',6)
    label(code,(.14,-.565,.62),.18,root)
    cylinder('TankInspectionFlange',(.48,-.574,.57),.24,.04,'silver',root,'Y')
    cylinder('TankInspectionCover',(.48,-.6,.57),.19,.025,'blue',root,'Y')
    for i in range(10):
        a=i*math.pi/5
        cylinder('InspectionBolt',(.48+.218*math.cos(a),-.62,.57+.218*math.sin(a)),.015,.02,'silver',root,'Y',6)
    cylinder('Accumulator',(-.67,.32,1.63),.15,.47,'blue',root)
    cylinder('AccumulatorTop',(-.67,.32,1.9),.045,.09,'silver',root)
    for z in (1.44,1.82):
        cylinder('AccumulatorCollar',(-.67,.32,z),.156,.04,'steel',root)
    pipe('AccumulatorLine',[(-.67,.32,1.4),(-.67,.32,1.25),(.4,.32,1.25)],.02,'steel',root)
    for x in (-.92,.92):
        for y in (-.59,.59):
            box('ServiceFramePost',(x,y,1.14),(.045,.045,2.2),'steel',root,.004)
        box('ServiceFrameTop',(x,0,2.22),(.045,1.22,.045),'steel',root,.004)
    for y in (-.59,.59):
        box('ServiceFrameCrossbar',(0,y,2.22),(1.88,.045,.045),'steel',root,.004)
    for x in (.34,.65):
        box('SolenoidConnector',(x,-.1,1.41),(.1,.12,.1),'frame',root)
        pipe('ValveCable',[(x,-.17,1.41),(x,-.22,1.12),(.85,-.22,1.12)],.01,'black',root)
    for y in (-.27,-.09,.09,.27):
        cylinder('HydraulicPort',(1,y,.6),.045,.09,'silver',root,'X')
    for y in (-.2,.2):
        cylinder('HydraulicUnion',(1,y,.6),.042,.075,'silver',root,'X',6)
    for z in (.48,.82):
        cylinder('SightGlassScrew',(-.6,-.593,z),.011,.014,'silver',root,'Y',6)


def pdp(root, code):
    for i in range(3):
        x=(i-1)*.66
        box('CabinetFrame',(x,0,1.05),(.65,.55,2.1),'white',root,.008)
        box('Plinth',(x,0,.065),(.65,.61,.13),'frame',root)
        box('DoorRecess',(x,-.279,1.18),(.621,.012,1.8),'frame',root,.001)
        box('CabinetRoofLip',(x,0,2.1),(.657,.58,.025),'white',root,.003)
        for z in (.57,1.18,1.78):
            box('Door',(x,-.293,z),(.6,.055,.53),'white',root,.003)
            box('DoorHandle',(x+.2,-.336,z),(.035,.045,.13),'black',root)
            box('BreakerWindow',(x-.08,-.328,z),(.19,.018,.14),'frame',root)
            cylinder('BreakerSwitch',(x-.08,-.35,z),.035,.025,'black',root,'Y')
            for dx in (-.25,.25):
                cylinder('DoorFastener',(x+dx,-.326,z+.21),.008,.009,'steel',root,'Y',6)
        for z in (.25,.3,.35):
            box('VentSlot',(x,-.325,z),(.43,.008,.014),'frame',root,.002)
            blade=box('CabinetVentLouvre',(x,-.331,z+.012),(.43,.025,.009),'white',root,.001)
            blade.rotation_euler[0]=-.4
    box('CabinetSidePanel',(-.99,0,1.14),(.015,.48,1.83),'white',root,.003)
    for y in (-.21,.21):
        for z in (.27,1.96):
            cylinder('SidePanelScrew',(-1.001,y,z),.009,.013,'steel',root,'X',6)
    box('BusVoltageDisplay',(0,-.344,1.9),(.25,.02,.11),'black',root)
    label('V',(0,-.36,1.865),.075,root,'green')
    label(code,(0,-.335,2.03),.15,root,'black')
    for x in (-.66,0,.66):
        pipe('CableOutlet',[(x,.3,.15),(x,.4,.15),(x,.4,.025)],.045,'black',root)
    box('MainIncomerPanel',(-.66,-.345,1.2),(.3,.025,.4),'frame',root)
    box('MainBreakerHandle',(-.66,-.37,1.17),(.07,.04,.17),'black',root)
    for x in (0,.66):
        for z in (.57,1.18,1.78):
            box('FeederPanel',(x,-.347,z),(.41,.022,.22),'steel',root)
            box('FeederPullHandle',(x+.14,-.377,z),(.14,.032,.025),'black',root,.003)
            for dx in (-.12,-.045,.03):
                box('FeederIndicator',(x+dx,-.366,z+.065),(.035,.012,.025),'black',root,.001)
    box('BusbarHeader',(0,-.285,2.105),(1.97,.06,.06),'red',root)
    for x in (-.95,-.29,.37):
        for z in (.4,.74,1.01,1.35,1.61,1.95):
            cylinder('CabinetHinge',(x,-.33,z),.015,.065,'steel',root)


def cau(root, code):
    box('CompressorPackage',(-.34,0,.86),(1.55,.95,1.65),'blue',root,.016)
    box('CabinetDoor',(-.34,-.49,.86),(1.4,.025,1.48),'frame',root,.004)
    box('ControlDisplay',(-.66,-.516,1.4),(.34,.02,.21),'black',root)
    label('AIR',(-.66,-.53,1.37),.075,root,'green')
    for z in (.34,.41,.48,.55,.62):
        box('AirVent',(-.37,-.515,z),(.83,.012,.025),'black',root,.002)
        blade=box('IntakeLouvre',(-.37,-.526,z+.018),(.83,.045,.012),'frame',root,.002)
        blade.rotation_euler[0]=-.45
    box('DoorHandle',(.17,-.54,1.0),(.035,.04,.21),'silver',root)
    box('AirServiceModule',(.84,0,.57),(.5,.6,1.08),'white',root)
    for x in (.69,.96):
        cylinder('AirFilter',(x,-.19,.62),.065,.32,'steel',root)
    gauge(root,(.84,-.33,.91),'air_pressure')
    pipe('AirDelivery',[(.4,.3,1.24),(.84,.3,1.24),(.84,.3,.87),(1.28,.3,.87)],.026,'air',root)
    label(code,(-.34,-.528,.9),.18,root)
    # Enclosed GA package: no external motor or receiver inferred from the workshop photo.
    box('GAAccent',(-1.04,-.525,.86),(.055,.03,1.6),'oil',root,.003)
    box('ServiceDoorSeam',(-.05,-.523,.86),(.01,.012,1.48),'black',root,.001)
    cylinder('EmergencyStop',(-.65,-.54,1.2),.038,.04,'red',root,'Y')
    cylinder('EmergencyStopCollar',(-.65,-.518,1.2),.055,.012,'yellow',root,'Y')
    box('ExhaustDuct',(-.34,.12,1.9),(.72,.57,.42),'steel',root,.02)
    box('ExhaustFlange',(-.34,.12,1.694),(.80,.65,.028),'steel',root,.003)
    for x in (-.7,.02):
        for y in (-.16,.4):
            cylinder('ExhaustFlangeBolt',(x,y,1.718),.014,.02,'silver',root,vertices=6)
    for i in range(10):
        box('ExhaustLouvre',(-.34,-.177,1.72+i*.035),(.63,.015,.012),'frame',root,.002)
    for x in (-1.06,.38):
        box('PackageFoot',(x,0,.04),(.12,.85,.08),'frame',root)
    for z in (.75,.82,.89, .96):
        box('SideAirIntake',(-1.128,0,z),(.02,.67,.025),'black',root,.002)
    box('SideServicePanel',(-1.121,0,1.3),(.018,.80,.48),'frame',root,.004)
    for y in (-.34,.34):
        for z in (1.12,1.48):
            cylinder('ServicePanelFastener',(-1.137,y,z),.011,.014,'silver',root,'X',6)
    for z in (.25,1.48):
        cylinder('ServiceDoorHinge',(-1.01,-.515,z),.017,.12,'steel',root)
    box('ControlKeypad',(-.66,-.528,1.31),(.24,.014,.027),'steel',root,.002)
    for x in (.69,.96):
        cylinder('FilterDrain',(x,-.19,.425),.022,.07,'black',root)
    cylinder('AirOutletUnion',(1.25,.3,.87),.043,.07,'silver',root,'X',6)


def conveyor(root, code):
    if code=='CV-01':
        feet(root,4.8,1.5)
        for y in (-.81,.81):
            box('ConveyorFrame',(0,y,.92),(4.8,.15,.32),'blue',root)
            box('EdgeGuard',(0,y,1.21),(4.8,.06,.2),'yellow',root)
            box('ConveyorChannelLip',(0,y,.775),(4.8,.23,.025),'blue',root,.003)
            for x in (-2.08,-.8,.8,2.08):
                box('GuardBracket',(x,y,1.10),(.08,.10,.27),'steel',root,.003)
                cylinder('GuardBracketBolt',(x,y*1.078,1.14),.015,.02,'silver',root,'Y',6)
        belt=empty('BeltSurface',root)
        box('BeltTop',(0,0,1.16),(4.42,1.47,.045),'belt',belt)
        box('BeltReturn',(0,0,.81),(4.42,1.47,.025),'belt',belt)
        for x,name in ((-2.16,'TailDrum'),(2.16,'HeadDrum')):
            drum=empty(name,root,(x,0,.99))
            cylinder(name+'Mesh',(0,0,0),.175,1.48,'belt',drum,'Y')
        tension=empty('TensionerSlide',root)
        box('TensionerMount',(-2.01,-1.0,.78),(.62,.14,.14),'steel',tension)
        cylinder('HydraulicTensioner',(-1.8,-1.0,.8),.075,.45,'blue',root,'X')
        cylinder('TensionerRod',(-2.1,-1.0,.8),.034,.3,'silver',tension,'X')
        diverter=empty('DiverterArm',root,(1.15,.82,1.35))
        box('DiverterGuide',(0,-.53,0),(.09,1.04,.13),'yellow',diverter)
        cylinder('PneumaticCylinder',(1.38,1.03,1.23),.065,.4,'white',root,'X')
        pipe('AirHose',[(1.15,1.06,1.21),(.7,1.06,1.21),(.7,1.06,.45)],.017,'air',root)
        label(code,(0,-.901,.93),.2,root)
        for x in (-1.6,-.8,0,.8,1.6):
            cylinder('ReturnIdler',(x,0,.76),.04,1.43,'steel',root,'Y')
        for x in (-2.16,2.16):
            for y in (-.9,.9):
                box('DrumBearing',(x,y,.99),(.23,.15,.24),'frame',root)
                cylinder('DrumBearingCover',(x,y*1.1,.99),.075,.025,'silver',root,'Y')
        box('DriveChainGuard',(2.08,1.05,.91),(.49,.15,.4),'yellow',root)
        for x in (-2.01,-1.8):
            cylinder('TensionerFastener',(x,-1.1,.8),.025,.03,'silver',root,'Y',6)
        box('TakeupGuide',(-2.04,-.97,1.02),(.54,.045,.06),'steel',root,.004)
        cylinder('TakeupAdjuster',(-2.19,-.99,1.06),.021,.37,'silver',root,'X',12)
        for x in (-2.31,-2.27):
            cylinder('TakeupLocknut',(x,-.99,1.06),.034,.024,'silver',root,'X',6)
        for x in (-1.65,0,1.65):
            box('BeltSupportCrossmember',(x,0,.91),(.10,1.54,.08),'frame',root,.004)
    else:
        feet(root,4.8,1.5,.8)
        for y in (-.61,.61):
            box('ScrapSideWall',(0,y*1.33,1.15),(4.8,.12,.57),'blue',root)
            box('ScrapGuard',(0,y*1.33,1.45),(4.8,.12,.055),'yellow',root)
            box('ScrapWallFold',(0,y*1.33,.88),(4.8,.20,.03),'blue',root,.003)
            box('BeltChainGuide',(0,y*1.2,1.13),(4.6,.065,.06),'frame',root,.003)
            for x in (-2.13,-.72,.72,2.13):
                box('ScrapWallStiffener',(x,y*1.448,1.15),(.055,.035,.48),'blue',root,.003)
                for z in (.98,1.31):
                    cylinder('ScrapWallFastener',(x,y*1.485,z),.017,.02,'silver',root,'Y',6)
        steelbelt=empty('SteelBelt',root)
        for i in range(24):
            x=-2.3+i*.2
            box('HingedSlat_%02d'%i,(x,0,1.16),(.192,1.4,.045),'steel',steelbelt,.003)
            cylinder('SlatHinge',(x+.097,0,1.15),.02,1.42,'silver',steelbelt,'Y')
            if i%4==0:
                box('ScrapCleat',(x,0,1.24),(.035,1.38,.12),'frame',steelbelt)
        chute=box('DischargeChute',(2.58,0,.99),(.62,1.48,.06),'steel',root)
        chute.rotation_euler[1]=.45
        for y in (-.72,.72):
            cheek=box('ChuteSideCheek',(2.61,y,1.08),(.63,.03,.20),'steel',root,.004)
            cheek.rotation_euler[1]=.45
        box('ScrapReturnTray',(0,0,.825),(4.42,1.4,.03),'frame',root,.003)
        label(code,(0,-.68,1.18),.18,root)
        for x,name in ((-2.16,'TailDrum'),(2.16,'HeadDrum')):
            drum=empty(name,root,(x,0,.99))
            cylinder(name+'Mesh',(0,0,0),.175,1.4,'steel',drum,'Y')
            for y in (-.91,.91):
                box('ScrapBearingBlock',(x,y,.99),(.23,.10,.19),'frame',root,.009)
                cylinder('ScrapBearingCap',(x,y*1.066,.99),.065,.025,'steel',root,'Y')
        box('ScrapChainGuard',(0,.93,1.02),(4.6,.1,.26),'yellow',root)



stage = 'detail'
OUTPUT = PROJECT / 'unity/ShiftLinkFactory/Modeling' / ('Blockout' if stage == 'blockout' else 'EquipmentTypes')
ASSETS = PROJECT / 'unity/ShiftLinkFactory/Assets/Models' / ('EquipmentBlockout' if stage == 'blockout' else 'EquipmentTypes')
OUTPUT.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
(OUTPUT/'Previews').mkdir(exist_ok=True)
bpy.context.preferences.filepaths.save_version = 0
scene.cycles.samples = 8
types = ['HPU','PDP','CAU','GR','RT','CV','CV02']
references = {
    'HPU': 'Bosch Rexroth ABPAC stationary hydraulic power unit',
    'GR': 'SEW X series industrial gearbox, process-adapted shared drive',
    'RT': 'Butech Bliss Coil & Sheet Runout Conveyor, process-adapted roller table',
    'CV': 'Mayfran flat-top steel belt family, process-adapted hydraulic tension and pneumatic diverter',
    'CV02': 'Miven Mayfran hinged steel belt scrap conveyor',
    'PDP': 'ABB MNS low-voltage switchgear exterior',
    'CAU': 'Atlas Copco GA enclosed screw compressor package',
}
roots=[]
positions=[(-6,4,0),(-2.7,4,0),(1,4,0),(5,4,0),(-3,0,0),(3,0,0),(9,0,0)]
for typ, position in zip(types,positions):
    root=empty('Equipment_'+typ)
    root['model_type']=typ
    root['reference_product']=references[typ]
    root['dimension_status']='synthetic modeling assumption in metres'
    root['front_direction']='Blender -Y; exported Unity -Z'
    body=empty('Body_'+typ,root)
    moving=empty('MovingParts_'+typ,root)
    if stage=='blockout':
        if typ in ('RT','CV'):
            feet(body,4.8,1.5)
            box('Frame',(0,0,.9),(4.8,1.65,.25),'blue',body)
            if typ=='RT':
                for i in range(12):
                    pivot=empty('RollerPivot_%02d'%i,moving,(-2.15+i*4.3/11,0,1.1))
                    cylinder('Roller',(0,0,0),.12,1.45,'steel',pivot,'Y')
            else:
                box('Belt',(0,0,1.12),(4.5,1.45,.08),'belt',moving)
        elif typ=='HPU':
            box('Tank',(0,0,.55),(1.8,1.1,1.1),'blue',body)
            cylinder('Motor',(-.4,0,1.4),.24,.6,'steel',body)
            box('Pump',(.4,0,1.2),(.5,.5,.3),'frame',body)
        elif typ=='PDP':
            box('Cabinet',(0,0,1.05),(1.9,.6,2.1),'white',body)
            box('Doors',(0,-.32,1.05),(1.8,.04,1.9),'frame',body)
        elif typ=='CAU':
            box('Compressor',(-.4,0,.85),(1.4,.9,1.7),'blue',body)
            cylinder('Receiver',(.9,0,.9),.34,1.8,'white',body)
        else:
            box('Base',(0,0,.12),(2.3,1.1,.24),'frame',body)
            box('GearHousing',(.4,0,.65),(1,.8,.95),'blue',body)
            cylinder('Motor',(-.65,0,.65),.23,.7,'steel',body,'X')
    else:
        {'HPU':hpu,'PDP':pdp,'CAU':cau,'GR':gearbox,'RT':roller_table,'CV':conveyor,'CV02':conveyor}[typ](body,'CV-02' if typ=='CV02' else typ+'-01')
        for obj in list(body.children_recursive):
            if obj.name.startswith('Label_'):
                bpy.data.objects.remove(obj,do_unlink=True)
        for obj in list(body.children):
            if obj.type=='EMPTY' and obj.name.startswith(('RollerAssembly','LiftPlatform','ClampSlide','OutputShaft','BeltSurface','HeadDrum','TailDrum','TensionerSlide','DiverterArm')):
                obj.parent=moving
        if typ=='GR':
            input_pivot=empty('InputShaftPivot',moving,(-.13,0,.64))
            cylinder('InputShaft',(0,0,0),.07,.28,'silver',input_pivot,'X')
        # Door pivots on the left edge; handles/windows follow the door.
        if typ=='PDP':
            for door in [o for o in list(body.children) if o.name.split('.')[0]=='Door']:
                old=door.location.copy()
                pivot=empty('DoorHinge',moving,(old.x-.3,old.y,old.z))
                for obj in list(body.children):
                    if obj==door or (obj.name.startswith(('DoorHandle','DoorFastener','BreakerWindow','BreakerSwitch','MainIncomerPanel','MainBreakerHandle','FeederPanel','FeederPullHandle','FeederIndicator')) and abs(obj.location.x-old.x)<.31 and abs(obj.location.z-old.z)<.27):
                        obj.parent=pivot
                        obj.location-=pivot.location
    status=empty('StatusIndicator_'+typ,root)
    if stage=='detail':
        low=2.1 if typ=='PDP' else .85
        high=2.35 if typ=='PDP' else 1.9
        cylinder('IndicatorSupport_'+typ,(0,-.62,(low+high)/2),.025,high-low,'frame',body)
    indicator=box('StatusLens_'+typ,(0,-.62,2.35 if typ=='PDP' else 1.9),(.18,.07,.12),'green',status)
    material=mats['green'].copy(); material.name='MES_Status_'+typ
    indicator.data.materials.clear(); indicator.data.materials.append(material)
    plate=empty('Nameplate_'+typ,root)
    box('BlankNameplate_'+typ,(0,-.64,.55),(.45,.025,.16),'white',plate)
    anchors=empty('Anchors_'+typ,root)
    height=2.6 if typ=='PDP' else 2.2
    empty('LabelAnchor_'+typ,anchors,(0,0,height))
    empty('SelectionAnchor_'+typ,anchors,(0,0,.8))
    empty('InputAnchor_'+typ,anchors,(-2.4,0,1.22) if typ in ('RT','CV','CV02') else (-1,0,.5))
    empty('OutputAnchor_'+typ,anchors,(2.4,0,1.22) if typ in ('RT','CV','CV02') else (1,0,.5))
    if typ=='CAU': empty('AirSupplyAnchor',anchors,(1.28,.3,.87))
    root.location=position
    roots.append(root)

coil=empty('Material_Coil')
# Hollow cylindrical strip, axis Y, outer diameter 1.2 m and bore 0.44 m.
verts=[]; faces=[]; n=64
for y,r in [(-.4,.6),(.4,.6),(-.4,.22),(.4,.22)]:
    verts.extend([(r*math.cos(2*math.pi*i/n),y,.6+r*math.sin(2*math.pi*i/n)) for i in range(n)])
for i in range(n):
    j=(i+1)%n
    faces.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)])
mesh=bpy.data.meshes.new('CoilHollowMesh'); mesh.from_pydata(verts,[],faces); mesh.update()
obj=bpy.data.objects.new('WoundSheet',mesh); scene.collection.objects.link(obj); finish(obj,'WoundSheet','steel',coil,.002)
if stage=='detail':
    for radius in (.25,.32,.39,.46,.53,.59):
        for side in (-.402,.402):
            points=[(radius*math.cos(2*math.pi*i/64),side,.6+radius*math.sin(2*math.pi*i/64)) for i in range(65)]
            pipe('WindingEdge',points,.0018,'silver',coil)
coil['dimensions_status']='synthetic coil, not verified against conveyor load capacity'
if stage=='detail':
    import bmesh
    for obj in [o for root in roots+[coil] for o in [root]+list(root.children_recursive) if o.type=='MESH']:
        bm=bmesh.new(); bm.from_mesh(obj.data); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(obj.data); bm.free()
        if not obj.data.uv_layers:
            bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(); bpy.ops.object.mode_set(mode='OBJECT')
    # Identical meshes share Blender data, including repeated rollers.
    shared={}
    for obj in [o for root in roots+[coil] for o in [root]+list(root.children_recursive) if o.type=='MESH']:
        key=(tuple(tuple(round(v,6) for v in p.co) for p in obj.data.vertices),tuple(tuple(p.vertices) for p in obj.data.polygons),tuple(m.name for m in obj.data.materials))
        if key in shared: obj.data=shared[key]
        else: shared[key]=obj.data
coil.location=(-3,0,1.22)
roots.append(coil)

def hierarchy(root): return [root]+list(root.children_recursive)
def bounding(root):
    points=[o.matrix_world@Vector(c) for o in hierarchy(root) if o.type=='MESH' for c in o.bound_box]
    return [min(p[i] for p in points) for i in range(3)]+[max(p[i] for p in points) for i in range(3)]

bpy.ops.object.camera_add(); camera=bpy.context.object; camera.data.type='ORTHO'; scene.camera=camera
for loc,energy in [((-5,-7,10),2000),((4,5,8),1600)]:
    bpy.ops.object.light_add(type='AREA',location=loc); light=bpy.context.object; light.data.energy=energy; light.data.size=8
    light.rotation_euler=(Vector((0,1,0))-light.location).to_track_quat('-Z','Y').to_euler()
lights=[o for o in scene.objects if o.type=='LIGHT']
def aim(target,offset,scale):
    camera.location=Vector(target)+Vector(offset); camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler(); camera.data.ortho_scale=scale
def render(path):
    scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
scene.render.resolution_x=1280; scene.render.resolution_y=720
aim((0,1.5,.7),(-12,-17,13),19)
render(OUTPUT/'Previews/overview.png')
records=[]
for root in roots:
    location=root.location.copy(); root.location=(0,0,0); bpy.context.view_layer.update()
    for other in roots:
        for obj in hierarchy(other): obj.hide_render=other!=root
    for light in lights: light.location.x-=location.x; light.location.y-=location.y
    bpy.ops.object.select_all(action='DESELECT')
    for obj in hierarchy(root): obj.select_set(True)
    bpy.context.view_layer.objects.active=root
    bpy.ops.export_scene.fbx(filepath=str(ASSETS/(root.name+'.fbx')),use_selection=True,object_types={'MESH','EMPTY'},axis_forward='-Z',axis_up='Y',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_custom_props=True,bake_anim=False,add_leaf_bones=False)
    meshes=[o for o in hierarchy(root) if o.type=='MESH']
    records.append({'model':root.name,'reference_product':root.get('reference_product','existing synthetic transport coil'),'bounds_metres':bounding(root),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),'materials':len({m.name for o in meshes for m in o.data.materials}),'moving_pivots':[o.name for o in hierarchy(root) if o.type=='EMPTY'],'fbx':root.name+'.fbx'})
    scene.render.resolution_x=640; scene.render.resolution_y=480
    scale=7.2 if root.name=='Equipment_RT' else 6.7 if root.name.endswith(('CV','CV02')) else 4.3
    for view,offset in [('front',(0,-9,0)),('side',(9,0,0)),('oblique',(-6,-8,5))]:
        aim((0,0,1.6 if root.name=='Equipment_RT' else 1),offset,scale); render(OUTPUT/'Previews'/(root.name+'_'+view+'.png'))
    for light in lights: light.location.x+=location.x; light.location.y+=location.y
    root.location=location
for root in roots:
    for obj in hierarchy(root): obj.hide_render=False
aim((0,1.5,.7),(-12,-17,13),19)
scene.render.resolution_x=1280; scene.render.resolution_y=720
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D': area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT/('ShiftLink_'+stage+'.blend')))
manifest={'stage':'process-adapted detail','blender_version':bpy.app.version_string,'units':'metres','models':records,'mapping':[{'equipment_id':r['equipment_id'],'code':r['code'],'model':'Equipment_CV02' if r['code']=='CV-02' else 'Equipment_'+r['code'].split('-')[0]} for r in CATALOG['equipment']],'textures':[],'unity_import':'pending validation','assumptions':['Manufacturer product families are exterior references, not exact installed models or certified engineering selections','Dimensions adapted to existing 4.8 m transport spans and MES anchors; no mixing ML-series dimension tables with X-series exterior','Coil handling and load support remain conceptual; existing MES transport semantics retained','RT-02 uses existing 16-roller Unity variant','CV-01 shared GR-02 drive retained without an extra local motor','CV-02 has a dedicated hinged steel belt model; motion uses installed MES cv_speed, without inferring a motor relationship','CAU enclosed package without inferred external motor or receiver','Lift, clamp, diverter and hydraulic tension geometry are project-specific adaptations','No procedural textures; constant PBR colors for Built-in Standard shader']}
(ASSETS/'model-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('SHIFTLINK PROCESS BUILD PASS: seven equipment variants plus existing coil')
