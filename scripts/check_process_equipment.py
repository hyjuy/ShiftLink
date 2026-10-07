"""Run with Blender --background --python scripts/check_process_equipment.py."""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

project = Path(__file__).resolve().parents[1]
native = project / 'unity/ShiftLinkFactory/Modeling/EquipmentTypes'
assets = project / 'unity/ShiftLinkFactory/Assets/Models/EquipmentTypes'
expected = {
    'HPU': ['Accumulator', 'TankInspectionFlange', 'ValveManifold', 'TankLid', 'PumpPressureHose'],
    'GR': ['SplitHousingSeam', 'GearInspectionCover', 'OutputShaft', 'MotorPedestal', 'FanGrilleBar'],
    'RT': ['Roller_01', 'BearingCover', 'ChainGuard', 'ChannelFlange', 'BearingCapFastener'],
    'CV': ['BeltTop', 'ReturnIdler', 'DiverterArm', 'TakeupAdjuster'],
    'CV02': ['SteelBelt', 'HingedSlat_00', 'DischargeChute', 'ChuteSideCheek'],
    'PDP': ['MainIncomerPanel', 'FeederPanel', 'CableOutlet', 'DoorRecess'],
    'CAU': ['CompressorPackage', 'ControlDisplay', 'ExhaustDuct', 'IntakeLouvre', 'SideServicePanel'],
}


def bounds(objects):
    points = [o.matrix_world @ Vector(c) for o in objects if o.type == 'MESH' for c in o.bound_box]
    assert points and all(math.isfinite(v) for p in points for v in p)
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


results = []
for family, required in expected.items():
    name = 'Equipment_' + family
    bpy.ops.wm.open_mainfile(filepath=str(native / (name + '.blend')))
    scene = bpy.data.scenes[0]
    bpy.context.window.scene = scene
    root = scene.objects[name]
    assert root.get('reference_product'), (name, 'Missing process product reference')
    assert root.location.length < 1e-6
    for prefix in required:
        assert any(o.name.startswith(prefix) for o in scene.objects), (name, prefix)
    if family == 'CAU':
        assert not any(o.name.startswith(('MotorBody', 'AirReceiver')) for o in scene.objects), 'GA package must be enclosed'
    if family == 'CV':
        assert not any(o.name.startswith('MotorBody') for o in scene.objects), 'CV-01 is driven by GR-02'
    if family == 'RT':
        rollers = [o for o in scene.objects if o.type == 'EMPTY' and o.name.startswith('Roller_')]
        assert len(rollers) == 12
        assert all(o.parent.name.startswith('BearingCover') for o in scene.objects if o.name.startswith('BearingCapFastener'))
        bpy.context.view_layer.update()
        anchor = next(o for o in scene.objects if o.name.startswith('InputAnchor_'))
        # Match FactoryRig.MaterialPosition/CreateLoad and the native coil's 1.20 m diameter.
        coil_top = anchor.matrix_world.translation.z + .02 + .14 + 1.20
        jaws = [o for o in scene.objects if o.name.startswith('ClampJaw')]
        bridges = [o for o in scene.objects if o.name.startswith('ClampBridge')]
        assert len(jaws) == len(bridges) == 1
        jaw_clearance = bounds(jaws)[2] - .06 - coil_top
        bridge_clearance = bounds(bridges)[2] - coil_top
        assert jaw_clearance >= .10 - 1e-5, ('RT jaw clearance at maximum downstroke', jaw_clearance)
        assert bridge_clearance >= .10 - 1e-5, ('RT bridge clearance', bridge_clearance)
    if family == 'PDP':
        assert all(o.parent.name.startswith('DoorHinge') for o in scene.objects if o.name.startswith(('DoorFastener', 'FeederPanel', 'MainIncomerPanel')))
    bpy.context.view_layer.update()
    original = bounds(scene.objects)
    meshes = [o for o in scene.objects if o.type == 'MESH']
    assert all(o.data.uv_layers and o.data.materials for o in meshes)
    assert all(p.area > 1e-12 for o in meshes for p in o.data.polygons)
    assert all(abs(p.normal.length - 1) < 1e-4 for o in meshes for p in o.data.polygons)
    count = len(meshes)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(assets / (name + '.fbx')))
    bpy.context.view_layer.update()
    imported = bounds(scene.objects)
    assert len([o for o in scene.objects if o.type == 'MESH']) == count
    assert max(abs(a - b) for a, b in zip(original, imported)) < .002, (name, original, imported)
    results.append({'model': name, 'meshes': count, 'bounds_metres': original, 'fbx_roundtrip': 'passed'})

manifest = json.loads((assets / 'model-manifest.json').read_text(encoding='utf-8'))
mapping = {r['code']: r['model'] for r in manifest['mapping']}
assert mapping['CV-02'] == 'Equipment_CV02'
assert len(mapping) == 10
(native / 'process-validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print('SHIFTLINK PROCESS MODEL CHECK PASS: 7 equipment assets, materials, UV, normals, FBX roundtrip, 10 MES IDs')
