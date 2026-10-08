using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

[Serializable] public class FaultFixtures { public FactoryConfig config; public MesSnapshot[] states; }
public static class FactoryFaultChecks
{
    static int checks;
    static void Check(bool ok,string message) { checks++; if(!ok) throw new Exception(message); Debug.Log("PASS: "+message); }
    static object Get(object target,string name) {
        if(target==null) return null;
        var type=target.GetType(); var property=type.GetProperty(name);
        return property!=null ? property.GetValue(target) : type.GetField(name)?.GetValue(target);
    }
    static object Call(object target,string name,params object[] args) {
        try { return target.GetType().GetMethod(name).Invoke(target,args); }
        catch(TargetInvocationException error) { throw error.InnerException??error; }
    }
    static MesSnapshot Clone(MesSnapshot value,string run) {
        var copy=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(value)); copy.run_id=run; return copy;
    }
    static string ScenarioTitle(FactoryConfig config,string id) {
        var scenarios=Get(config,"scenarios") as Array;
        if(scenarios!=null) foreach(var item in scenarios) {
            if((string)Get(item,"scenario_id")!=id) continue;
            var title=Get(item,"title") as string; return string.IsNullOrEmpty(title) ? id : title;
        }
        return id;
    }
    static bool Has(object component,string id,string kind) { return (bool)Call(component,"HasEffect",id,kind); }
    static void Representative(FactoryDemo demo,object component,FaultFixtures fixture,string scenario,string signal,string kind) {
        var state=fixture.states.FirstOrDefault(s=>s.scenario_id==scenario);
        Check(state!=null,"representative scenario available: "+scenario);
        demo.Apply(Clone(state,"representative-"+scenario));
        var measurement=state.measurements.FirstOrDefault(m=>m.signal==signal && m.quality=="good");
        Check(measurement!=null,"representative signal available: "+signal);
        Check(Has(component,measurement.equipment_id,kind),scenario+" creates "+kind+" at actual measurement equipment ID");
    }
    public static void Run()
    {
        string dir=Path.GetFullPath(Path.Combine(Application.dataPath,"../Checks"));
        try {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var fixture=JsonUtility.FromJson<FaultFixtures>(File.ReadAllText(Path.Combine(dir,"fault-fixtures.json")));
            var demo=new GameObject("Fault test factory").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.LoadDefaultFactory();
            Check(demo.EquipmentCount==10 && !demo.Connected && demo.CoilCount==0,"offline startup displays ten devices without inventing live coils or connection");
            Check(demo.GetComponent<FactoryMonitor>().Content.Contains("확인 불가"),"offline baseline marks sensor state unknown");
            demo.Build(fixture.config);
            var type=typeof(FactoryDemo).Assembly.GetType("FactoryFaults");
            Check(type!=null,"MES physical fault visualizer exists");
            var component=demo.GetComponent(type);
            Check(component!=null,"factory initializes fault visualizer");
            var normal=fixture.states.First(s=>s.scenario_id=="normal");
            demo.Apply(normal);
            Check((int)Get(component,"ActiveEffectCount")==0,"normal baseline has no physical fault effects");
            var warning=Clone(normal,"warning-check"); warning.scenario_id="warning-check";
            warning.equipment[0].fault_level="warning";
            demo.Apply(warning);
            Check((string)Get(component,"Severity")=="warning","warning severity remains separate from emergency");
            Call(component,"Mute"); demo.Apply(warning);
            Check((bool)Get(component,"SoundMuted"),"repeated snapshot does not undo sound mute");
            warning.equipment[0].fault_level="critical"; demo.Apply(warning);
            Check((string)Get(component,"Severity")=="critical" && !(bool)Get(component,"SoundMuted"),"critical escalation resets mute for new emergency");
            demo.Apply(normal);
            var moving=Clone(normal,"warning-motion"); moving.line_mode="fault";
            string rollerId=fixture.config.equipment.First(e=>e.code=="RT-01").equipment_id;
            var rollerState=moving.equipment.First(e=>e.equipment_id==rollerId);
            rollerState.operating_state="running"; rollerState.fault_level="warning";
            moving.measurements.First(m=>m.equipment_id==rollerId && m.signal=="rt_speed").value=30;
            demo.Apply(moving);
            var roller=demo.transform.Find("MES equipment").Find(rollerId).GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("Roller_") && t.childCount>0);
            var before=roller.localRotation; demo.AdvanceVisuals(.2f);
            Check(Quaternion.Angle(before,roller.localRotation)>.1f,"running warning roller follows measured speed during fault mode");
            rollerState.operating_state="stopped"; rollerState.fault_level="critical"; demo.Apply(moving);
            before=roller.localRotation; demo.AdvanceVisuals(.2f);
            Check(Quaternion.Angle(before,roller.localRotation)<.001f,"critical stopped roller cannot rotate");
            demo.Apply(normal);
            foreach(var state in fixture.states) {
                demo.Apply(state);
                Check(demo.Connected && demo.CurrentRunId==state.run_id,"accept scenario "+state.scenario_id);
                Check((string)Get(component,"Severity")==FactoryFaults.Level(state),"alarm severity follows MES for "+state.scenario_id);
                var content=demo.GetComponent<FactoryMonitor>().Content;
                Check(content.Contains(ScenarioTitle(fixture.config,state.scenario_id)),"display scenario title "+state.scenario_id);
                var alarms=Get(state,"active_alarms") as Array;
                if(alarms!=null) foreach(var alarm in alarms) {
                    string label=Get(alarm,"label") as string;
                    if(string.IsNullOrEmpty(label)) label=Get(alarm,"code") as string;
                    Check(!string.IsNullOrEmpty(label) && content.Contains(label),"display actual alarm for "+state.scenario_id);
                }
            }
            Representative(demo,component,fixture,"drive_fault","gr_vib_rms","vibration");
            Representative(demo,component,fixture,"gearbox_leak","gr_oil_leak","oil-leak");
            Representative(demo,component,fixture,"gearbox_overheat","gr_brg_temp","heat");
            Representative(demo,component,fixture,"hydraulic_overheat","hpu_oil_temp","heat");
            Representative(demo,component,fixture,"hydraulic_fault","hpu_pressure","pressure-low");
            Representative(demo,component,fixture,"pdp_trip","breaker_trip","power-trip");
            Representative(demo,component,fixture,"downstream_block","cv_queue_len","obstruction");

            var drive=fixture.states.First(s=>s.scenario_id=="drive_fault");
            var vibration=drive.measurements.First(m=>m.signal=="gr_vib_rms" && m.value>2);
            demo.Apply(Clone(drive,"offline-effect"));
            int active=(int)Get(component,"ActiveEffectCount");
            Check(active>0,"fault effects exist before disconnect");
            demo.Disconnect("test lost MES connection");
            Check((int)Get(component,"ActiveEffectCount")==active,"disconnect retains last observed fault effects");
            Check(demo.GetComponent<FactoryMonitor>().Content.Contains("연결 끊"),"disconnect display marks stale connection");
            Call(component,"SetOnline",false);
            var transforms=demo.GetComponentsInChildren<Transform>(true);
            var positions=transforms.Select(t=>t.localPosition).ToArray();
            var rotations=transforms.Select(t=>t.localRotation).ToArray();
            Call(component,"Advance",.5f);
            Check(transforms.Select((t,i)=>t.localPosition==positions[i] && t.localRotation==rotations[i]).All(x=>x),
                "offline Advance freezes stale transform animations");
            demo.Apply(Clone(normal,"normal-after-disconnect"));
            Check(demo.Connected && (int)Get(component,"ActiveEffectCount")==0,"normal snapshot clears retained effects and reconnects");

            var badQuality=Clone(drive,"bad-quality");
            foreach(var measurement in badQuality.measurements.Where(m=>m.equipment_id==vibration.equipment_id && m.signal==vibration.signal)) measurement.quality="unavailable";
            demo.Apply(badQuality);
            Check(!Has(component,vibration.equipment_id,"vibration"),"unavailable vibration measurement cannot create physical vibration");
            Check((int)Get(component,"UnknownEquipmentCount")>0,"unavailable measurement is counted as unknown");
            var badUnit=Clone(drive,"bad-unit");
            foreach(var measurement in badUnit.measurements.Where(m=>m.equipment_id==vibration.equipment_id && m.signal==vibration.signal)) measurement.unit="wrong-unit";
            demo.Apply(badUnit);
            Check(!Has(component,vibration.equipment_id,"vibration"),"unit mismatch cannot create physical vibration");
            var badNumber=Clone(drive,"bad-number");
            foreach(var measurement in badNumber.measurements.Where(m=>m.equipment_id==vibration.equipment_id && m.signal==vibration.signal)) measurement.value=float.NaN;
            demo.Apply(badNumber);
            Check(!Has(component,vibration.equipment_id,"vibration"),"nonfinite measurement cannot create physical vibration");
            demo.Apply(Clone(drive,"clear-api")); Call(component,"Clear");
            Check((int)Get(component,"ActiveEffectCount")==0,"Clear removes all physical fault effects");
            demo.Apply(Clone(normal,"final-normal"));
            Check((int)Get(component,"ActiveEffectCount")==0,"final normal recovery leaves no stale fault effects");
            File.WriteAllText(Path.Combine(dir,"fault-result.txt"),"PASS "+checks);
            EditorApplication.Exit(0);
        } catch(Exception e) {
            Debug.LogException(e); File.WriteAllText(Path.Combine(dir,"fault-result.txt"),"FAIL "+e.Message);
            EditorApplication.Exit(1);
        }
    }
}
