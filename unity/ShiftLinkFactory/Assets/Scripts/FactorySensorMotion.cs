using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Sensor values are authoritative. Displacements and cyclic actuator motions are illustrative.
public class FactorySensorMotion : MonoBehaviour
{
    public static bool Usable(MeasurementReading reading,SignalSpec spec)
    {
        return reading!=null && spec!=null && reading.unit==spec.unit && reading.quality=="good" &&
            !float.IsNaN(reading.value) && !float.IsInfinity(reading.value) && reading.value>=0;
    }
    public static string State(MeasurementReading reading,SignalSpec spec,bool running,string scenario=null)
    {
        if(!Usable(reading,spec)) return "unavailable";
        if(scenario=="hpu_accumulator_precharge" && spec.unit=="bar") {
            if(spec.signal=="hpu_accumulator_gas_pressure") return reading.value<130 ? "low" : reading.value>140 ? "high" : "normal";
            if(spec.signal=="hpu_accumulator_fluid_pressure" || spec.signal=="hpu_pressure") return reading.value==0 ? "normal" : "high";
        }
        if(!running && spec.zero_when_stopped && reading.value==0) return "stopped";
        return reading.value<spec.normal_min ? "low" : reading.value>spec.normal_max ? "high" : "normal";
    }
    public static string Persona(string family,string signal)
    {
        if(family=="rt" || family=="cv" || family=="cau") return "V-12";
        if(family=="hpu" || signal=="gr_vib_rms" || signal=="gr_oil_leak") return "V-11";
        return "V-13";
    }
    class Channel {
        public EquipmentSpec equipment;
        public SignalSpec spec;
        public Transform indicator;
        public MeasurementReading reading;
        public string state;
    }
    class Part {
        public string id,ownerId,signal,kind;
        public Transform transform;
        public Vector3 position,scale;
        public Quaternion rotation;
        public Vector3 up,right,upAxis;
        public float travelSign,halfHeight,phase;
    }
    readonly List<Channel> channels=new List<Channel>();
    readonly List<Part> parts=new List<Part>();
    readonly List<Material> materials=new List<Material>();
    Dictionary<string,GameObject> nodes;
    Material green,amber,grey;
    MesSnapshot current;
    float elapsed;
    Vector2 scroll;
    Material Material(Color color) { var m=new Material(Shader.Find("Standard")); m.color=color; materials.Add(m); return m; }
    public void Build(FactoryConfig config,Dictionary<string,GameObject> equipment)
    {
        nodes=equipment; green=Material(FactoryRules.Green); amber=Material(FactoryRules.Amber); grey=Material(FactoryRules.Grey);
        foreach(var eq in config.equipment) {
            var node=nodes[eq.equipment_id].transform;
            var display=new GameObject("Factory status display").transform; display.SetParent(node,false);
            int i=0;
            foreach(var spec in eq.signals??new SignalSpec[0]) {
                var obj=GameObject.CreatePrimitive(PrimitiveType.Sphere); obj.name="Sensor indicator "+spec.signal;
                DestroyImmediate(obj.GetComponent<Collider>()); obj.transform.SetParent(display,false);
                obj.transform.localPosition=new Vector3((i%8-3.5f)*.09f,2.48f+(i/8)*.11f,-.65f);
                obj.transform.localScale=Vector3.one*.06f; obj.GetComponent<Renderer>().sharedMaterial=grey;
                channels.Add(new Channel {equipment=eq,spec=spec,indicator=obj.transform,state="unavailable"}); i++;
            }
            var transforms=node.GetComponentsInChildren<Transform>();
            void Add(string prefix,string signal,string kind) {
                foreach(var t in transforms.Where(t=>t.name.StartsWith(prefix)))
                    parts.Add(MovingPart(eq.equipment_id,eq.equipment_id,signal,kind,t,node));
            }
            if(eq.profile_id=="hpu") {
                Add("GaugeNeedle_hpu_pressure","hpu_pressure","gauge");
                Add("OilLevel","hpu_oil_level","level");
            }
            if(eq.profile_id=="gr") {
                Add("InputShaftPivot","gr_rpm","rpm");
                Add("GearHousing","gr_vib_rms","vibration");
                var drip=GameObject.CreatePrimitive(PrimitiveType.Sphere); drip.name="Illustrative oil leak";
                DestroyImmediate(drip.GetComponent<Collider>()); drip.transform.SetParent(node,false);
                drip.transform.localPosition=new Vector3(.7f,.18f,-.45f); drip.transform.localScale=new Vector3(.08f,.025f,.08f);
                drip.GetComponent<Renderer>().sharedMaterial=Material(new Color(.1f,.07f,.025f));
                transforms=node.GetComponentsInChildren<Transform>(); Add("Illustrative oil leak","gr_oil_leak","leak"); drip.SetActive(false);
            }
            if(eq.profile_id=="pdp") Add("MainBreakerHandle","breaker_trip","breaker");
            if(eq.profile_id=="cau") Add("GaugeNeedle_air_pressure","air_pressure","gauge");
            if(eq.profile_id=="rt") {
                Add("ClampSlide","rt_clamp_press","clamp");
                if(eq.code=="RT-02") Add("LiftPlatform","rt_lift_delay","lift");
                Add("BearingCover","rt_vib_rms","vibration");
            }
            if(eq.profile_id=="cv") {
                Add("TensionerSlide","cv_belt_tension","tension");
                Add("DrumBearingCover","cv_vib_rms","vibration");
                Add("HingedSlat_","cv_speed","slat");
                Add("SlatHinge","cv_speed","slat");
                Add("ScrapCleat","cv_speed","slat");
                // Diverter is an explicit demo cycle gated by its pneumatic supply, not a position measurement.
                string source=(config.relations??new RelationSpec[0]).FirstOrDefault(r=>r.to_id==eq.equipment_id && r.relation_type=="pneumatic_supply")?.from_id;
                if(source!=null) foreach(var t in transforms.Where(t=>t.name.StartsWith("DiverterArm")))
                    parts.Add(MovingPart(source,eq.equipment_id,"air_pressure","diverter",t,node));
            }
        }
    }
    Part MovingPart(string id,string ownerId,string signal,string kind,Transform t,Transform node) {
        return new Part {id=id,ownerId=ownerId,signal=signal,kind=kind,transform=t,position=t.localPosition,scale=t.localScale,rotation=t.localRotation,
            up=t.parent.InverseTransformVector(node.up),right=t.parent.InverseTransformVector(node.right),
            upAxis=t.InverseTransformDirection(node.up),travelSign=Mathf.Sign(t.parent.InverseTransformDirection(node.right).x),
            halfHeight=t.GetComponent<Renderer>()==null ? 0 : t.GetComponent<Renderer>().bounds.size.y*.5f};
    }
    Channel Find(string id,string signal) { return channels.FirstOrDefault(c=>c.equipment.equipment_id==id && c.spec.signal==signal); }
    public string SensorState(string id,string signal) { return Find(id,signal)?.state??"unavailable"; }
    public string SensorDescription(string id,string signal)
    {
        var c=Find(id,signal);
        if(c==null) return "계측 확인 불가 · 관측 시각 미확인";
        string acquisition=c.spec.semantics?.acquisition;
        string kind=acquisition=="continuous" ? "연속 계측" : acquisition=="manual_sample" ? "시료"
            : acquisition=="event" ? "완료 이벤트" : acquisition=="derived" ? "산출값" : "수집 방식 미확인";
        string value=c.state=="unavailable" ? "계측 확인 불가" : c.reading.value.ToString("0.###")+" "+c.spec.unit;
        string time=string.IsNullOrEmpty(c.reading?.observed_at) ? "관측 시각 미확인" : "관측 시각 "+c.reading.observed_at;
        return c.spec.name+": "+value+" ["+c.state+"] · "+kind+" · "+time;
    }
    public string Observation(string id)
    {
        var own=channels.Where(c=>c.equipment.equipment_id==id).ToArray();
        var anomalies=own.Where(c=>c.state=="low" || c.state=="high").ToArray();
        int stopped=own.Count(c=>c.state=="stopped"), unavailable=own.Count(c=>c.state=="unavailable");
        string summary="정상 범위 "+own.Count(c=>c.state=="normal")+"개 · 정지 영값 "+stopped+"개 · 미확인 "+unavailable+"개.";
        if(stopped>0) summary+=" 정지 영값은 가동 중 정상 범위 판정과 구분합니다.";
        var focus=anomalies.Length>0 ? anomalies : own.Where(c=>c.state=="unavailable").Take(2).ToArray();
        if(focus.Length==0) {
            string persona=Persona(own.FirstOrDefault()?.equipment.profile_id??"","");
            string name=persona=="V-11" ? "한 조장" : persona=="V-12" ? "오 기사" : "윤 주임";
            return name+"("+persona+"): "+summary+" 원인·복구 확인과는 별개입니다.";
        }
        return summary+"\n"+string.Join("\n",focus.Take(4).Select(c=> {
            string persona=Persona(c.equipment.profile_id,c.spec.signal);
            string name=persona=="V-11" ? "한 조장" : persona=="V-12" ? "오 기사" : "윤 주임";
            string value=c.state=="unavailable" ? "계측 확인 불가" : c.reading.value.ToString("0.###")+" "+c.spec.unit+" · "+(c.state=="low" ? "정상 범위 미만" : "정상 범위 초과");
            string record=c.equipment.code+" / "+c.spec.name+" / "+value;
            string wording=persona=="V-11" ? record+". 공급·구동 계통부터 대조 필요. 원인은 미확정이다."
                : persona=="V-12" ? "계측 대조: "+record+". 육안 위치·방향과 원인은 미확인. 다음 교대 확인 항목으로 남깁니다."
                : "상태감시 확인: "+record+". 정비 이력·센서 교정 및 차단·잠금·재가동 승인 기록은 별도 대조가 필요합니다.";
            return name+"("+persona+"): "+wording;
        }));
    }
    public void Apply(MesSnapshot snapshot)
    {
        if(current==null || snapshot==null || current.run_id!=snapshot.run_id) {
            elapsed=0;
            foreach(var part in parts) Reset(part);
        }
        current=snapshot;
        foreach(var c in channels) {
            c.reading=(snapshot?.measurements??new MeasurementReading[0]).FirstOrDefault(m=>m.equipment_id==c.equipment.equipment_id && m.signal==c.spec.signal);
            var eq=(snapshot?.equipment??new EquipmentReading[0]).FirstOrDefault(e=>e.equipment_id==c.equipment.equipment_id);
            bool running=FactoryRules.AllowsEquipmentMotion(snapshot) && eq!=null && eq.operating_state=="running";
            c.state=snapshot==null || eq==null ? "unavailable" : State(c.reading,c.spec,running,snapshot.scenario_id);
            c.indicator.GetComponent<Renderer>().sharedMaterial=c.state=="normal" ? green : c.state=="low" || c.state=="high" ? amber : grey;
            c.indicator.localScale=Vector3.one*.06f;
        }
        foreach(var p in parts) {
            var c=Find(p.id,p.signal);
            if(snapshot==null || c==null || c.state=="unavailable") { Reset(p); continue; }
            // With no position telemetry, an unloaded clamp/lift returns to the demo cycle's rest pose.
            var owner=(snapshot.equipment??new EquipmentReading[0]).FirstOrDefault(e=>e.equipment_id==p.ownerId);
            if((p.kind=="clamp" || p.kind=="lift") && FactoryRules.AllowsEquipmentMotion(snapshot) && owner!=null && owner.operating_state=="running" && owner.fault_level!="critical" && !(snapshot.coils??new CoilReading[0]).Any(coil=>coil.equipment_id==p.ownerId)) { Reset(p); continue; }
            float value=c.reading.value;
            if(p.kind=="gauge") p.transform.localRotation=p.rotation*Quaternion.Euler(0,Mathf.Lerp(-110,110,Mathf.Clamp01(value/Mathf.Max(c.spec.normal_max*1.3f,.001f))),0);
            if(p.kind=="level") {
                float fill=Mathf.Clamp01(value/100); var scale=p.scale; var axis=p.upAxis;
                if(Mathf.Abs(axis.z)>.9f) scale.z*=fill; else if(Mathf.Abs(axis.x)>.9f) scale.x*=fill; else scale.y*=fill;
                p.transform.localScale=scale; p.transform.localPosition=p.position+p.up*(fill-1)*p.halfHeight;
            }
            if(p.kind=="breaker") p.transform.localRotation=p.rotation*Quaternion.Euler(0,value>=.5f ? -45 : 0,0);
            if(p.kind=="leak") p.transform.gameObject.SetActive(value>=.5f);
            if(p.kind=="vibration" && c.state!="high") p.transform.localPosition=p.position;
        }
    }
    void Reset(Part p) {
        p.phase=0;
        p.transform.localPosition=p.position; p.transform.localScale=p.scale; p.transform.localRotation=p.rotation;
        if(p.kind=="leak") p.transform.gameObject.SetActive(false);
    }
    public void Advance(MesSnapshot snapshot,float dt)
    {
        if(!FactoryRules.AllowsEquipmentMotion(snapshot) || dt<=0 || float.IsNaN(dt) || float.IsInfinity(dt)) return;
        elapsed+=dt;
        foreach(var c in channels.Where(c=>c.state=="low" || c.state=="high"))
            c.indicator.localScale=Vector3.one*(.06f+.025f*(.5f+.5f*Mathf.Sin(elapsed*4)));
        foreach(var p in parts) {
            var c=Find(p.id,p.signal);
            var eq=(snapshot.equipment??new EquipmentReading[0]).FirstOrDefault(e=>e.equipment_id==p.id);
            var owner=(snapshot.equipment??new EquipmentReading[0]).FirstOrDefault(e=>e.equipment_id==p.ownerId);
            if(c==null || !Usable(c.reading,c.spec) || eq==null || eq.operating_state!="running" || eq.fault_level=="critical" || owner==null || owner.operating_state!="running" || owner.fault_level=="critical") continue;
            float value=c.reading.value;
            bool normal=c.state=="normal";
            bool loaded=(snapshot.coils??new CoilReading[0]).Any(coil=>coil.equipment_id==p.ownerId);
            p.phase+=dt*(p.kind=="lift" ? 1/Mathf.Max(1,value*60+1) : 1.5f);
            float cycle=.5f-.5f*Mathf.Cos(p.phase);
            if(p.kind=="rpm") p.transform.Rotate(Vector3.right,value*6*dt,Space.Self);
            if(p.kind=="vibration") p.transform.localPosition=p.position+(c.state=="high" ? p.right*Mathf.Sin(p.phase*12)*.012f : Vector3.zero);
            if(p.kind=="clamp" && loaded && normal) p.transform.localPosition=p.position-p.up*.06f*cycle;
            if(p.kind=="lift" && loaded) p.transform.localPosition=p.position+p.up*.025f*cycle;
            if(p.kind=="tension") p.transform.localPosition=p.position+p.right*(normal ? .01f : .045f)*cycle;
            if(p.kind=="diverter" && normal) p.transform.localRotation=p.rotation*Quaternion.AngleAxis(20*cycle,p.upAxis);
            if(p.kind=="slat") { var pos=p.transform.localPosition; pos.x=Mathf.Repeat(pos.x+2.4f+p.travelSign*value/60*dt,4.8f)-2.4f; p.transform.localPosition=pos; }
            if(p.kind=="leak" && value>=.5f) p.transform.localScale=p.scale*(1+.15f*Mathf.Sin(p.phase*2));
        }
    }
    Rect PanelRect() { float width=Mathf.Min(410,Screen.width-36); return new Rect(Screen.width-width-18,18,width,290); }
    public bool ContainsPointer(Vector2 pointer) { var demo=GetComponentInParent<FactoryDemo>(); return demo!=null && !string.IsNullOrEmpty(demo.SelectedId) && PanelRect().Contains(pointer); }
    void OnGUI()
    {
        var demo=GetComponentInParent<FactoryDemo>();
        if(demo==null || string.IsNullOrEmpty(demo.SelectedId)) return;
        var style=new GUIStyle(GUI.skin.label) {wordWrap=true};
        GUILayout.BeginArea(PanelRect(),GUI.skin.box);
        GUILayout.Label("장비 계측·합성 관찰 | "+demo.SelectedId);
        GUILayout.Label("시나리오: "+(current?.scenario_id??"연결 없음"));
        scroll=GUILayout.BeginScrollView(scroll);
        GUILayout.Label(Observation(demo.SelectedId),style);
        foreach(var c in channels.Where(c=>c.equipment.equipment_id==demo.SelectedId)) {
            GUILayout.Label(SensorDescription(c.equipment.equipment_id,c.spec.signal),style);
        }
        GUILayout.Label("변위·클램프·승강·디버터 모션은 시연 표현입니다. 정비 이력과 재가동 승인 여부는 별도 확인합니다.",style);
        GUILayout.EndScrollView();
        GUILayout.EndArea();
    }
    void OnDestroy() { foreach(var m in materials) { if(Application.isPlaying) Destroy(m); else DestroyImmediate(m); } }
}
