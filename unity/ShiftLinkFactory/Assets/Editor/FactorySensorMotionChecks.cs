using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactorySensorMotionChecks
{
    [Serializable] public class Expected { public string equipment_id,signal,state; }
    [Serializable] public class Frame { public string scenario_id; public MesSnapshot snapshot; public Expected[] expected; }
    [Serializable] public class Frames { public Frame[] frames; }
    static void Check(bool value,string message) { if(!value) throw new Exception(message); }
    static Transform Part(Transform node,string name) { return node.GetComponentsInChildren<Transform>(true).First(t=>t.name.StartsWith(name)); }
    static Bounds MeshBounds(Renderer renderer)
    {
        // Renderer.bounds encloses a rotated local AABB; use actual vertices for cylinder contact.
        var vertices=renderer.GetComponent<MeshFilter>().sharedMesh.vertices;
        var bounds=new Bounds(renderer.transform.TransformPoint(vertices[0]),Vector3.zero);
        foreach(var vertex in vertices.Skip(1)) bounds.Encapsulate(renderer.transform.TransformPoint(vertex));
        return bounds;
    }
    static float SlatDisplacement(Transform slat,Vector3 before) { return Mathf.Repeat(slat.localPosition.x-before.x+2.4f,4.8f)-2.4f; }
    static float SlatDistance(Transform slat,Vector3 before) { return Mathf.Abs(SlatDisplacement(slat,before)); }
    public static void Run()
    {
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var baseline=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Sensor motion check").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(baseline);
            var motion=demo.GetComponentInChildren<FactorySensorMotion>();
            Check(motion!=null,"Sensor motion rig required");
            var nodes=demo.transform.Find("MES equipment");
            Check(Part(nodes.Find("EQ-0010"),"SteelBelt")!=null,"CV-02 must use dedicated hinged steel belt");
            Check(!nodes.Find("EQ-0009").GetComponentsInChildren<Transform>().Any(t=>t.name.StartsWith("MotorBody")),"CV-01 must retain shared GR drive");
            Check(!nodes.Find("EQ-0003").GetComponentsInChildren<Transform>().Any(t=>t.name.StartsWith("MotorBody")),"CAU must be an enclosed package");
            Check(nodes.Find("EQ-0007").GetComponentsInChildren<Transform>().Count(t=>t.name.StartsWith("BearingCover"))==32,"RT-02 needs bearing covers at both ends of all 16 rollers");
            var scrapRenderers=nodes.Find("EQ-0010").GetComponentsInChildren<Renderer>();
            var walls=scrapRenderers.Where(r=>r.name.StartsWith("ScrapSideWall") || r.name=="Scrap conveyor side wall").ToArray();
            Check(walls.Length>0 && walls.All(r=>!r.enabled),"CV-02 side panels must not hide the operating passage view");
            foreach(string prefix in new[]{"ScrapWallStiffener","ScrapWallFastener","ScrapGuard","BeltChainGuide","HingedSlat_"}) {
                var structural=scrapRenderers.Where(r=>r.name.StartsWith(prefix)).ToArray();
                Check(structural.Length>0 && structural.All(r=>r.enabled),"Passage visibility must preserve functional guard or structure: "+prefix);
            }
            var chute=nodes.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("Connection_ScrapChute"));
            var chuteSides=chute.GetComponentsInChildren<Renderer>().Where(r=>r.name.Split('.')[0]=="Side").ToArray();
            Check(chuteSides.Length>0 && chuteSides.All(r=>!r.enabled),"Branch chute side panels must preserve the line's passage sightline");
            CheckRollerClearance(demo,config,baseline,nodes,dir);
            CheckLiveTransport(demo,baseline);
            CheckScrapDischarge(demo,baseline,nodes,dir);
            demo.Apply(baseline);
            Check(FactorySensorMotion.Persona("gr","gr_vib_rms")=="V-11","V-11 sensory focus");
            Check(FactorySensorMotion.Persona("cv","cv_queue_len")=="V-12","V-12 transport focus");
            Check(FactorySensorMotion.Persona("pdp","breaker_trip")=="V-13","V-13 electrical/maintenance focus");
            var acquisitionKinds=new[]{"continuous","manual_sample","event","derived"};
            var acquisitionLabels=new[]{"연속 계측","시료","완료 이벤트","산출값"};
            var acquisitionCounts=new[]{59,5,1,4};
            for(int i=0;i<acquisitionKinds.Length;i++) {
                var specs=config.equipment.SelectMany(e=>e.signals).Where(s=>s.semantics?.acquisition==acquisitionKinds[i]).ToArray();
                Check(specs.Length==acquisitionCounts[i],"Actual MES acquisition kind count: "+acquisitionKinds[i]);
                foreach(var eq in config.equipment) foreach(var spec in eq.signals.Where(s=>s.semantics?.acquisition==acquisitionKinds[i])) {
                    var reading=baseline.measurements.First(m=>m.equipment_id==eq.equipment_id && m.signal==spec.signal);
                    var description=motion.SensorDescription(eq.equipment_id,spec.signal);
                    Check(description.Contains(acquisitionLabels[i]),"GUI must display actual acquisition kind: "+spec.signal);
                    Check(!string.IsNullOrEmpty(reading.observed_at) && description.Contains(reading.observed_at),"GUI must preserve actual observation time: "+spec.signal);
                }
            }
            var metadata=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            metadata.measurements.First(m=>m.equipment_id=="EQ-0001" && m.signal=="fluid_viscosity").observed_at=null;
            demo.Apply(metadata);
            Check(motion.SensorDescription("EQ-0001","fluid_viscosity").Contains("관측 시각 미확인"),"Missing sample time must remain unknown");
            Check(motion.SensorDescription("EQ-0007","rt_lift_delay").Contains("계측 확인 불가"),"Absent completed lift event must remain unavailable");
            metadata.line_mode="stopped";
            metadata.equipment.First(e=>e.equipment_id=="EQ-0004").operating_state="stopped";
            var gearbox=config.equipment.First(e=>e.equipment_id=="EQ-0004");
            foreach(var spec in gearbox.signals.Where(s=>s.zero_when_stopped))
                metadata.measurements.First(m=>m.equipment_id==gearbox.equipment_id && m.signal==spec.signal).value=0;
            demo.Apply(metadata);
            string stoppedObservation=motion.Observation("EQ-0004");
            Check(stoppedObservation.Contains("정지 영값 "+gearbox.signals.Count(s=>s.zero_when_stopped)+"개") && stoppedObservation.Contains("가동 중 정상 범위 판정과 구분"),"Stopped zero values must be distinguished from running normal bands");
            Check(!stoppedObservation.Contains("확인 가능한 계측값은 구성의 정상 범위입니다"),"Stopped sensors must not be summarized as all within normal bands");
            metadata.line_mode="running";
            metadata.equipment.First(e=>e.equipment_id=="EQ-0004").operating_state="running";
            metadata.measurements.First(m=>m.equipment_id=="EQ-0004" && m.signal=="gr_vib_rms").value=5;
            metadata.measurements.First(m=>m.equipment_id=="EQ-0004" && m.signal=="gr_rpm").quality="bad";
            demo.Apply(metadata);
            string mixedObservation=motion.Observation("EQ-0004");
            Check(mixedObservation.Contains("미확인 1개") && mixedObservation.Contains("정상 범위 초과"),"Anomaly observations must also retain unavailable sensor count");
            demo.Apply(baseline);
            var band=new SignalSpec {signal="air_pressure",unit="kPa",normal_min=550,normal_max=700};
            var sample=new MeasurementReading {unit="kPa",quality="good",value=550};
            Check(FactorySensorMotion.State(sample,band,true)=="normal","Lower boundary is inclusive");
            sample.value=700; Check(FactorySensorMotion.State(sample,band,true)=="normal","Upper boundary is inclusive");
            sample.unit="bar"; Check(FactorySensorMotion.State(sample,band,true)=="unavailable","Wrong unit rejected");
            sample.unit="kPa"; sample.value=float.NaN; Check(FactorySensorMotion.State(sample,band,true)=="unavailable","NaN rejected");
            sample.value=float.PositiveInfinity; Check(FactorySensorMotion.State(sample,band,true)=="unavailable","Infinity rejected");
            sample.value=-1; Check(FactorySensorMotion.State(sample,band,true)=="unavailable","Negative value rejected");
            var frames=JsonUtility.FromJson<Frames>(File.ReadAllText(Path.Combine(dir,"sensor-motion-frames.json"))).frames;
            int checks=0;
            foreach(var frame in frames) {
                Check(FactoryRules.Matches(config,frame.snapshot),"Scenario fixture must match Unity contract: "+frame.scenario_id);
                demo.Apply(frame.snapshot);
                foreach(var e in frame.expected) {
                    var reading=frame.snapshot.equipment.First(r=>r.equipment_id==e.equipment_id);
                    var spec=config.equipment.First(r=>r.equipment_id==e.equipment_id).signals.First(s=>s.signal==e.signal);
                    string expected=spec.zero_when_stopped && frame.snapshot.measurements.First(m=>m.equipment_id==e.equipment_id && m.signal==e.signal).value==0 && reading.operating_state!="running" ? "stopped" : e.state;
                    if(frame.scenario_id=="hpu_accumulator_precharge" && new[]{"hpu_accumulator_gas_pressure","hpu_accumulator_fluid_pressure","hpu_pressure"}.Contains(e.signal)) expected="normal";
                    Check(motion.SensorState(e.equipment_id,e.signal)==expected,frame.scenario_id+" / "+e.equipment_id+" / "+e.signal+" expected "+expected); checks++;
                }
                demo.AdvanceVisuals(.1f);
            }
            Check(frames.Length>=100 && checks>60,"Actual MES scenarios and sensor anomaly coverage required");
            foreach(var item in new[]{Tuple.Create("EQ-0001","hydraulic_fault"),Tuple.Create("EQ-0002","pdp_trip"),Tuple.Create("EQ-0003","cau_supply_fault"),Tuple.Create("EQ-0004","sensor_anomaly_EQ-0004_gr_vib_rms"),Tuple.Create("EQ-0007","sensor_anomaly_EQ-0007_rt_vib_rms"),Tuple.Create("EQ-0009","sensor_anomaly_EQ-0009_cv_belt_tension"),Tuple.Create("EQ-0010","sensor_anomaly_EQ-0010_cv_queue_len")}) {
                demo.Apply(baseline); demo.AdvanceVisuals(.2f); Capture(nodes.Find(item.Item1),Path.Combine(dir,"process-normal-"+item.Item1+".png"));
                demo.Apply(frames.First(f=>f.scenario_id==item.Item2).snapshot); demo.AdvanceVisuals(.2f); Capture(nodes.Find(item.Item1),Path.Combine(dir,"process-abnormal-"+item.Item1+".png"));
            }
            demo.Apply(baseline);
            var input=Part(nodes.Find("EQ-0004"),"InputShaftPivot"); var rotation=input.localRotation;
            var slat=Part(nodes.Find("EQ-0010"),"HingedSlat_00"); var pos=slat.localPosition;
            var hinge=Part(nodes.Find("EQ-0010"),"SlatHinge"); var hingePos=hinge.localPosition; var hingeWorld=hinge.position;
            var cleat=Part(nodes.Find("EQ-0010"),"ScrapCleat"); var cleatPos=cleat.localPosition; var cleatWorld=cleat.position;
            var worldPos=slat.position;
            demo.AdvanceVisuals(.2f);
            Check(Quaternion.Angle(rotation,input.localRotation)>.1f,"Measured GR drive RPM animates input shaft");
            Check(Vector3.Distance(pos,slat.localPosition)>.001f,"CV-02 measured speed animates actual steel slats");
            Check(Vector3.Dot(slat.position-worldPos,nodes.Find("EQ-0010").right)>0,"Steel belt must move towards the MES output, not backwards through FBX axes");
            Check(Mathf.Abs(SlatDisplacement(hinge,hingePos)-SlatDisplacement(slat,pos))<.0001f && Mathf.Abs(SlatDisplacement(cleat,cleatPos)-SlatDisplacement(slat,pos))<.0001f,"Steel belt hinges and cleats travel with their slats");
            Check(Vector3.Dot(hinge.position-hingeWorld,nodes.Find("EQ-0010").right)>0 && Vector3.Dot(cleat.position-cleatWorld,nodes.Find("EQ-0010").right)>0,"Steel belt hinges and cleats move towards the MES output");
            var transitions=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            transitions.run_id="sensor-transition-check"; transitions.line_mode="running";
            var conveyor=transitions.equipment.First(e=>e.equipment_id=="EQ-0010"); conveyor.operating_state="running"; conveyor.fault_level="none";
            var speed=transitions.measurements.First(m=>m.equipment_id=="EQ-0010" && m.signal=="cv_speed"); speed.quality="good"; speed.value=18;
            demo.Apply(transitions); demo.AdvanceVisuals(.2f);
            speed.value=9; demo.Apply(transitions); pos=slat.localPosition; demo.AdvanceVisuals(.1f);
            Check(Mathf.Abs(SlatDistance(slat,pos)-9f/60*.1f)<.0001f,"Speed changes affect only the next timestep, without repositioning belt history");
            foreach(string blocked in new[]{"waiting","critical","bad_quality"}) {
                conveyor.operating_state=blocked=="waiting" ? "waiting" : "running"; conveyor.fault_level=blocked=="critical" ? "critical" : "none"; speed.quality=blocked=="bad_quality" ? "bad" : "good";
                demo.Apply(transitions); pos=slat.localPosition; hingePos=hinge.localPosition; cleatPos=cleat.localPosition; demo.AdvanceVisuals(.8f);
                Check(SlatDistance(slat,pos)<.0001f,"Steel belt freezes while "+blocked);
                Check(SlatDistance(hinge,hingePos)<.0001f && SlatDistance(cleat,cleatPos)<.0001f,"Steel belt hinges and cleats freeze while "+blocked);
                conveyor.operating_state="running"; conveyor.fault_level="none"; speed.quality="good";
                demo.Apply(transitions); pos=slat.localPosition; hingePos=hinge.localPosition; cleatPos=cleat.localPosition; demo.AdvanceVisuals(.1f);
                Check(Mathf.Abs(SlatDistance(slat,pos)-9f/60*.1f)<.0001f,"Steel belt resumes with one timestep after "+blocked);
                Check(Mathf.Abs(SlatDisplacement(hinge,hingePos)-SlatDisplacement(slat,pos))<.0001f && Mathf.Abs(SlatDisplacement(cleat,cleatPos)-SlatDisplacement(slat,pos))<.0001f,"Steel belt hinges and cleats resume with their slats after "+blocked);
            }
            var air=transitions.equipment.First(e=>e.equipment_id=="EQ-0003"); air.operating_state="running"; air.fault_level="none";
            var pressure=transitions.measurements.First(m=>m.equipment_id=="EQ-0003" && m.signal=="air_pressure"); pressure.quality="good"; pressure.value=600;
            var owner=transitions.equipment.First(e=>e.equipment_id=="EQ-0009"); owner.operating_state="running"; owner.fault_level="none";
            var diverter=Part(nodes.Find("EQ-0009"),"DiverterArm"); demo.Apply(transitions); rotation=diverter.localRotation; demo.AdvanceVisuals(.2f);
            Check(Quaternion.Angle(rotation,diverter.localRotation)>.01f,"Healthy air supply permits a running conveyor's illustrative diverter cycle");
            foreach(string blocked in new[]{"waiting","critical"}) {
                owner.operating_state=blocked=="waiting" ? "waiting" : "running"; owner.fault_level=blocked=="critical" ? "critical" : "none";
                demo.Apply(transitions); rotation=diverter.localRotation; demo.AdvanceVisuals(.8f);
                Check(Quaternion.Angle(rotation,diverter.localRotation)<.001f,"Normal CAU supply cannot move a conveyor diverter while its owner is "+blocked);
            }
            var load=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            load.run_id="loaded-motion-check";
            load.coils[0].equipment_id="EQ-0007";
            var delay=load.measurements.First(m=>m.equipment_id=="EQ-0007" && m.signal=="rt_lift_delay"); delay.quality="good"; delay.value=.01f;
            demo.Apply(load);
            var clamp=Part(nodes.Find("EQ-0007"),"ClampSlide"); var clampPos=clamp.position;
            var lift=Part(nodes.Find("EQ-0007"),"LiftPlatform"); var liftPos=lift.position;
            demo.AdvanceVisuals(.2f);
            Check(clamp.position.y<clampPos.y && Mathf.Abs(clamp.position.x-clampPos.x)<.0001f && Mathf.Abs(clamp.position.z-clampPos.z)<.0001f,"Illustrative clamp travels vertically");
            Check(lift.position.y>liftPos.y && Mathf.Abs(lift.position.x-liftPos.x)<.0001f && Mathf.Abs(lift.position.z-liftPos.z)<.0001f,"Illustrative lift travels vertically");
            var table=load.equipment.First(e=>e.equipment_id=="EQ-0007"); table.operating_state="waiting";
            demo.Apply(load); var waitingLift=lift.position; demo.AdvanceVisuals(.8f);
            Check(Vector3.Distance(waitingLift,lift.position)<.0001f,"Lift phase freezes during individual equipment waiting");
            table.operating_state="running"; demo.Apply(load); demo.AdvanceVisuals(.2f);
            float liftTravel=.025f*(.5f-.5f*Mathf.Cos(.4f/(delay.value*60+1)));
            Check(Mathf.Abs(lift.position.y-liftPos.y-liftTravel)<.0001f,"Lift resumes from active cycle time without consuming waiting time");
            var pausedLift=lift.position; load.coils=new CoilReading[0]; load.line_mode="paused"; demo.Apply(load);
            Check(Vector3.Distance(pausedLift,lift.position)<.0001f,"Unloading does not alter the frozen pose while paused");
            load.line_mode="running"; demo.Apply(load);
            Check(Vector3.Distance(clamp.position,clampPos)<.0001f && Vector3.Distance(lift.position,liftPos)<.0001f,"Unloaded running clamp and lift return to their illustrative rest poses");
            var level=Part(nodes.Find("EQ-0001"),"OilLevel").GetComponent<Renderer>(); var height=level.bounds.size.y; var bottom=level.bounds.min.y;
            load.measurements.First(m=>m.equipment_id=="EQ-0001" && m.signal=="hpu_oil_level").value=40;
            demo.Apply(load);
            Check(level.bounds.size.y<height && Mathf.Abs(level.bounds.min.y-bottom)<.001f,"Measured oil level changes fill height while keeping its bottom fixed");
            var vibration=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var vib=vibration.measurements.First(m=>m.equipment_id=="EQ-0004" && m.signal=="gr_vib_rms"); vib.value=5; vib.quality="good";
            demo.Apply(vibration); var housing=Part(nodes.Find("EQ-0004"),"GearHousing"); pos=housing.localPosition; demo.AdvanceVisuals(.1f);
            Check(Vector3.Distance(pos,housing.localPosition)>.001f,"GR high vibration produces bounded illustrative displacement");
            vib.value=0; demo.Apply(vibration); pos=housing.localPosition; demo.AdvanceVisuals(.1f);
            Check(Vector3.Distance(pos,housing.localPosition)<.0001f,"Low vibration must not produce an excessive vibration motion");
            vib.value=5;
            vib.quality="bad"; demo.Apply(vibration);
            Check(motion.SensorState("EQ-0004","gr_vib_rms")=="unavailable","Bad sensor cannot animate a fault");
            demo.Apply(baseline);
            foreach(string mode in new[]{"paused","stopped"}) {
                baseline.line_mode=mode; demo.Apply(baseline); pos=slat.localPosition; rotation=input.localRotation; demo.AdvanceVisuals(.2f);
                Check(Vector3.Distance(pos,slat.localPosition)<.001f && Quaternion.Angle(rotation,input.localRotation)<.001f,"Freeze on "+mode);
            }
            baseline.line_mode="running"; demo.Apply(baseline); rotation=input.localRotation;
            foreach(float dt in new[]{0,-1,float.NaN,float.PositiveInfinity}) demo.AdvanceVisuals(dt);
            Check(Quaternion.Angle(rotation,input.localRotation)<.001f,"Invalid timestep freezes motion");
            demo.Disconnect("offline"); pos=slat.localPosition; rotation=input.localRotation; demo.AdvanceVisuals(.2f);
            Check(Vector3.Distance(pos,slat.localPosition)<.001f && Quaternion.Angle(rotation,input.localRotation)<.001f,"Offline freezes motion");
            Check(motion.SensorState("EQ-0004","gr_vib_rms")=="unavailable","Offline clears sensor state");
            File.WriteAllText(Path.Combine(dir,"sensor-motion-result.txt"),"PASS: "+frames.Length+" MES scenarios, "+checks+" sensor checks, seven process equipment variants, RT-01/02/03 pallet roller contact and coil clearance at full clamp stroke, live pallet transport, CV-02 visible scrap discharge/bin/reset, persona roles, observation states, acquisition/time metadata, RPM, steel slats, belt hinges/cleats, speed transitions, equipment resume, diverter owner gating, lift phase, unloaded rest, vibration, bad quality, pause, stop, invalid dt, offline");
            Debug.Log("SHIFTLINK SENSOR MOTION CHECK PASS");
            FactoryMotionChecks.Run();
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
    static void CheckRollerClearance(FactoryDemo demo,FactoryConfig config,MesSnapshot baseline,Transform nodes,string dir)
    {
        var rig=demo.GetComponentInChildren<FactoryRig>();
        foreach(var eq in config.equipment.Where(e=>e.profile_id=="rt")) {
            var frame=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(baseline));
            frame.run_id="roller-clearance-"+eq.equipment_id; frame.line_mode="running";
            frame.coils=new[]{new CoilReading {coil_id="Clearance coil",equipment_id=eq.equipment_id,position=.75f}};
            var state=frame.equipment.First(e=>e.equipment_id==eq.equipment_id); state.operating_state="running"; state.fault_level="none";
            var spec=eq.signals.First(s=>s.signal=="rt_clamp_press");
            var pressure=frame.measurements.First(m=>m.equipment_id==eq.equipment_id && m.signal==spec.signal);
            pressure.value=(spec.normal_min+spec.normal_max)*.5f; pressure.quality="good";
            demo.Apply(frame);
            var node=nodes.Find(eq.equipment_id);
            var coil=demo.transform.Find("MES coils").GetChild(0);
            var jaw=Part(node,"ClampJaw").GetComponent<Renderer>();
            var bridge=Part(node,"ClampBridge").GetComponent<Renderer>();
            float rest=jaw.bounds.min.y;
            for(int phase=0;phase<2;phase++) {
                if(phase==1) {
                    demo.AdvanceVisuals(Mathf.PI/1.5f);
                    Check(Mathf.Abs(rest-jaw.bounds.min.y-.06f)<.0001f,eq.code+" clearance check reaches the full clamp stroke");
                }
                foreach(float position in new[]{0,.25f,.5f,.75f,1}) {
                    coil.position=rig.MaterialPosition(eq.equipment_id,position);
                    var renderers=coil.GetComponentsInChildren<Renderer>(); var loadBounds=renderers[0].bounds;
                    foreach(var renderer in renderers.Skip(1)) loadBounds.Encapsulate(renderer.bounds);
                    var runners=renderers.Where(r=>r.name=="Line pallet runner").ToArray();
                    Check(runners.Length==2 && renderers.Count(r=>r.name=="Line pallet crossmember")==2 && renderers.Count(r=>r.name=="Line V saddle")==2,
                        eq.code+" coil travels on a complete pallet with two runners, crossmembers and V saddles");
                    Check(Mathf.Abs(loadBounds.max.y-2.58f)<.001f,eq.code+" line pallet preserves the existing 2.58 m coil top");
                    var rollers=node.GetComponentsInChildren<Renderer>().Where(r=>r.name.StartsWith("RollerShell")).Select(MeshBounds).ToArray();
                    foreach(var runner in runners) {
                        var contact=rollers.Where(r=>r.max.x>=runner.bounds.min.x && r.min.x<=runner.bounds.max.x && r.max.z>=runner.bounds.min.z && r.min.z<=runner.bounds.max.z).ToArray();
                        Check(contact.Length>0 && contact.Any(r=>Mathf.Abs(r.max.y-runner.bounds.min.y)<.002f),
                            eq.code+" pallet runners contact actual roller shell vertices along the transport path (phase "+phase+", position "+position+", runner bottom "+runner.bounds.min.y+", shell top "+(contact.Length==0 ? "no overlap" : contact.Max(r=>r.max.y).ToString())+")");
                    }
                    Check(jaw.bounds.min.y-loadBounds.max.y>=.0999f && bridge.bounds.min.y-loadBounds.max.y>=.0999f,
                        eq.code+" clamp and bridge require 0.10 m clearance above the actual coil and saddle across the transport path");
                    foreach(var guide in node.GetComponentsInChildren<Renderer>().Where(r=>r.name.StartsWith("ClampGuide")))
                        Check(!guide.bounds.Intersects(loadBounds),eq.code+" clamp uprights must remain outside the coil path");
                }
            }
            coil.position=rig.MaterialPosition(eq.equipment_id,.75f);
            Capture(node,Path.Combine(dir,"roller-coil-clearance-"+eq.equipment_id+".png"));
        }
    }
    static void CheckLiveTransport(FactoryDemo demo,MesSnapshot baseline)
    {
        var frame=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(baseline));
        frame.run_id="live-pallet-transport-check"; frame.line_mode="running";
        frame.coils=new[]{new CoilReading {coil_id="Transport pallet",equipment_id="EQ-0006",position=0}};
        var state=frame.equipment.First(e=>e.equipment_id=="EQ-0006"); state.operating_state="running"; state.fault_level="none";
        var speed=frame.measurements.First(m=>m.equipment_id=="EQ-0006" && m.signal=="rt_speed"); speed.value=12; speed.unit="m_min"; speed.quality="good";
        demo.Apply(frame);
        var coil=demo.transform.Find("MES coils").Find("Transport pallet");
        var before=coil.position; frame.coils[0].position=1; demo.Apply(frame); demo.AdvanceVisuals(1);
        var rig=demo.GetComponentInChildren<FactoryRig>();
        Check(Mathf.Abs(Vector3.Distance(before,coil.position)-.2f)<.0001f && Vector3.Dot(coil.position-before,rig.MaterialPosition("EQ-0006",1)-before)>0,"A real MES target moves the complete coil pallet at measured roller surface speed");
        foreach(string blocked in new[]{"paused","stopped","bad_speed"}) {
            frame.line_mode=blocked=="bad_speed" ? "running" : blocked; speed.quality=blocked=="bad_speed" ? "bad" : "good";
            demo.Apply(frame); before=coil.position; demo.AdvanceVisuals(1);
            Check(Vector3.Distance(before,coil.position)<.0001f,"Live coil pallet freezes on "+blocked);
            frame.line_mode="running"; speed.quality="good"; demo.Apply(frame); demo.AdvanceVisuals(.5f);
            Check(Mathf.Abs(Vector3.Distance(before,coil.position)-.1f)<.0001f,"Live coil pallet resumes from its last position on "+blocked);
        }
    }
    static void CheckScrapDischarge(FactoryDemo demo,MesSnapshot baseline,Transform nodes,string dir)
    {
        var frame=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(baseline));
        frame.run_id="scrap-discharge-check"; frame.line_mode="running";
        frame.coils=new[]{new CoilReading {coil_id="Rejected transport sheet",equipment_id="EQ-0010",position=.7f}};
        var state=frame.equipment.First(e=>e.equipment_id=="EQ-0010"); state.operating_state="running"; state.fault_level="none";
        var speed=frame.measurements.First(m=>m.equipment_id=="EQ-0010" && m.signal=="cv_speed"); speed.value=12; speed.unit="m_min"; speed.quality="good";
        demo.Apply(frame);
        var sheet=demo.transform.Find("MES coils").Find("Rejected transport sheet"); var before=sheet.position;
        Check(sheet.Find("Rejected cut sheet")!=null && !sheet.GetComponentsInChildren<Renderer>().Any(r=>r.name=="Line pallet runner"),"CV-02 rejection is sheet scrap without a coil pallet");
        frame.coils=new CoilReading[0]; demo.Apply(frame);
        Check(demo.CoilCount==0 && demo.DischargingScrapCount==1 && demo.ScrapCount==0,"Removed CV-02 snapshot load enters visible discharge before reaching the collection bin");
        var discharge=demo.transform.Find("MES scrap discharge");
        sheet=discharge.Find("Rejected transport sheet");
        Check(sheet!=null && Vector3.Distance(before,sheet.position)<.0001f,"Snapshot removal preserves scrap's position for physical exit animation");
        demo.AdvanceVisuals(1);
        var output=demo.GetComponentInChildren<FactoryRig>().MaterialPosition("EQ-0010",1);
        Check(Mathf.Abs(Vector3.Distance(before,sheet.position)-.2f)<.0001f && Vector3.Dot(sheet.position-before,output-before)>0,"Pending scrap first travels at measured CV-02 belt speed towards the output");
        foreach(string blocked in new[]{"paused","stopped","bad_speed","critical"}) {
            frame.line_mode=blocked=="paused" || blocked=="stopped" ? blocked : "running";
            speed.quality=blocked=="bad_speed" ? "bad" : "good"; state.fault_level=blocked=="critical" ? "critical" : "none";
            demo.Apply(frame); before=sheet.position; demo.AdvanceVisuals(1);
            Check(Vector3.Distance(before,sheet.position)<.0001f && demo.DischargingScrapCount==1 && demo.ScrapCount==0,"Scrap discharge freezes on "+blocked);
        }
        frame.line_mode="running"; speed.quality="good"; state.fault_level="none"; demo.Apply(frame);
        for(int i=0;i<200 && demo.DischargingScrapCount>0;i++) demo.AdvanceVisuals(.25f);
        Check(demo.DischargingScrapCount==0 && demo.ScrapCount==1 && sheet!=null,"Scrap passes the conveyor output/chute and remains visibly collected in the bin");
        var bin=Part(nodes,"Scrap collection bin").GetComponent<Renderer>().bounds;
        Check(Mathf.Abs(sheet.position.x-bin.center.x)<=bin.extents.x && Mathf.Abs(sheet.position.z-bin.center.z)<=bin.extents.z && sheet.position.y<1,
            "Completed scrap is inside the actual collection bin footprint below conveyor height");
        Capture(nodes.Find("EQ-0010"),Path.Combine(dir,"scrap-collected-CV02.png"));
        frame=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(frame));
        frame.run_id="scrap-discharge-reset"; demo.Apply(frame);
        Check(demo.DischargingScrapCount==0 && demo.ScrapCount==0 && discharge.childCount==0,"New MES run clears pending and collected scrap");
        frame.coils=new[]{new CoilReading {coil_id="Offline pending scrap",equipment_id="EQ-0010",position=.7f}}; demo.Apply(frame);
        frame.coils=new CoilReading[0]; demo.Apply(frame);
        Check(demo.DischargingScrapCount==1,"Offline regression begins with a pending CV-02 discharge");
        demo.Disconnect("scrap offline check");
        Check(demo.DischargingScrapCount==0 && demo.ScrapCount==0 && discharge.childCount==0,"Disconnect clears all CV-02 discharge and bin loads");
    }
    static void Capture(Transform node,string path)
    {
        var camera=Camera.main; var pos=camera.transform.position; var rotation=camera.transform.rotation;
        var target=node.position+Vector3.up;
        camera.transform.position=target+new Vector3(4,3,-5); camera.transform.LookAt(target);
        var rt=new RenderTexture(1280,720,24); var previous=RenderTexture.active;
        camera.targetTexture=rt; camera.Render(); RenderTexture.active=rt;
        var pixels=new Texture2D(1280,720,TextureFormat.RGB24,false); pixels.ReadPixels(new Rect(0,0,1280,720),0,0); pixels.Apply();
        File.WriteAllBytes(path,pixels.EncodeToPNG()); camera.targetTexture=null; RenderTexture.active=previous;
        rt.Release(); UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(pixels);
        camera.transform.SetPositionAndRotation(pos,rotation);
    }
}
