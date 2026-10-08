using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Fault effects illustrate measured deviations; MES alone decides operation and severity.
public class FactoryFaults : MonoBehaviour
{
    class Effect {
        public string id,kind;
        public Transform marker,part;
        public Vector3 position,scale,partPosition;
    }
    readonly List<Effect> effects=new List<Effect>();
    readonly List<Material> materials=new List<Material>();
    FactoryConfig config;
    Dictionary<string,GameObject> nodes;
    MesSnapshot current;
    AudioSource audioSource;
    AudioClip warningClip,emergencyClip;
    string incident;
    bool online,muted;
    float elapsed,nextBeep;
    public string Severity { get; private set; }="normal";
    public string Notification { get; private set; }="";
    public int ActiveEffectCount { get { return effects.Count; } }
    public int UnknownEquipmentCount { get; private set; }
    public bool SoundMuted { get { return muted; } }
    public bool SoundPlaying { get { return audioSource!=null && audioSource.isPlaying; } }
    public bool EmergencyLoop { get { return audioSource!=null && audioSource.loop && audioSource.clip==emergencyClip; } }
    public bool HasEffect(string id,string kind) { return effects.Any(e=>e.id==id && e.kind==kind); }
    public void Initialize(FactoryConfig next,Dictionary<string,GameObject> equipment)
    {
        Clear(); config=next; nodes=equipment;
        if(!Application.isPlaying || audioSource!=null) return;
        audioSource=gameObject.AddComponent<AudioSource>(); audioSource.playOnAwake=false;
        audioSource.spatialBlend=0; audioSource.volume=.25f;
        warningClip=Tone(false); emergencyClip=Tone(true);
    }
    static AudioClip Tone(bool emergency)
    {
        int rate=22050; var samples=new float[emergency ? rate*2 : rate/3];
        double phase=0;
        for(int i=0;i<samples.Length;i++) {
            float t=(float)i/rate;
            float frequency=emergency ? 600+500*Mathf.PingPong(t*2,1) : 880;
            phase+=2*Math.PI*frequency/rate;
            float envelope=Mathf.Min(1,t*50)*Mathf.Min(1,(samples.Length-i)/(float)rate*50);
            samples[i]=(float)Math.Sin(phase)*.35f*envelope;
        }
        var clip=AudioClip.Create(emergency ? "MES emergency siren" : "MES warning beep",samples.Length,1,rate,false);
        clip.SetData(samples,0); return clip;
    }
    public static string Level(MesSnapshot snapshot)
    {
        if(snapshot==null) return "unavailable";
        var levels=(snapshot.equipment??new EquipmentReading[0]).Select(e=>e.fault_level)
            .Concat((snapshot.active_alarms??new AlarmReading[0]).Where(a=>string.IsNullOrEmpty(a.cleared_at)).Select(a=>a.severity));
        return levels.Contains("critical") ? "critical" : levels.Contains("warning") ? "warning" : "normal";
    }
    public void Apply(MesSnapshot snapshot)
    {
        ClearEffects(); current=snapshot; online=snapshot!=null;
        Severity=Level(snapshot); UnknownEquipmentCount=0;
        if(snapshot==null || config==null || nodes==null) { SetOnline(false); return; }
        var alarms=(snapshot.active_alarms??new AlarmReading[0]).Where(a=>string.IsNullOrEmpty(a.cleared_at)).ToArray();
        var affected=(snapshot.equipment??new EquipmentReading[0]).Where(e=>e.fault_level=="warning" || e.fault_level=="critical").Select(e=>e.equipment_id)
            .Concat(alarms.Select(a=>a.equipment_id)).Distinct().ToArray();
        string codes=string.Join(", ",affected.Select(id=>config.equipment.FirstOrDefault(e=>e.equipment_id==id)?.code??id));
        string title=(config.scenarios??new ScenarioSpec[0]).FirstOrDefault(s=>s.scenario_id==snapshot.scenario_id)?.title;
        Notification=(Severity=="critical" ? "비상" : Severity=="warning" ? "경고" : "정상")+" · "+codes+"\n"+(string.IsNullOrEmpty(title) ? snapshot.scenario_id : title);
        if(alarms.Length>0) Notification+="\n"+string.Join(" / ",alarms.Select(a=>string.IsNullOrEmpty(a.label) ? a.code : a.label));
        string key=snapshot.run_id+":"+snapshot.scenario_id+":"+Severity+":"+string.Join(",",affected.OrderBy(x=>x))+":"+string.Join(",",alarms.Select(a=>a.alarm_id).OrderBy(x=>x));
        if(key!=incident) { incident=key; muted=false; nextBeep=0; audioSource?.Stop(); }
        foreach(var eq in config.equipment.Where(e=>e.active)) {
            bool unknown=false;
            var owner=(snapshot.equipment??new EquipmentReading[0]).FirstOrDefault(e=>e.equipment_id==eq.equipment_id);
            foreach(var spec in eq.signals??new SignalSpec[0]) {
                var reading=(snapshot.measurements??new MeasurementReading[0]).FirstOrDefault(m=>m.equipment_id==eq.equipment_id && m.signal==spec.signal);
                if(!FactorySensorMotion.Usable(reading,spec)) { unknown=true; continue; }
                string state=FactorySensorMotion.State(reading,spec,FactoryRules.AllowsEquipmentMotion(snapshot) && owner?.operating_state=="running",snapshot.scenario_id);
                if(state!="low" && state!="high") continue;
                string kind=spec.signal.Contains("vib") && state=="high" ? "vibration" : spec.signal=="gr_oil_leak" ? "oil-leak" : spec.signal=="breaker_trip" ? "power-trip"
                    : spec.signal.Contains("temp") && state=="high" ? "heat" : spec.signal.Contains("pressure") && state=="low" ? "pressure-low"
                    : spec.signal=="cv_queue_len" && state=="high" ? "obstruction" : "sensor-"+state;
                if(!HasEffect(eq.equipment_id,kind)) AddEffect(eq,kind,spec.name);
            }
            if(unknown) UnknownEquipmentCount++;
        }
        UpdateSound();
    }
    void AddEffect(EquipmentSpec eq,string kind,string label)
    {
        var root=nodes[eq.equipment_id].transform;
        var marker=GameObject.CreatePrimitive(kind=="obstruction" || kind=="power-trip" ? PrimitiveType.Cube : PrimitiveType.Sphere);
        marker.name="Fault "+kind; Remove(marker.GetComponent<Collider>()); marker.transform.SetParent(root,false);
        int count=effects.Count(e=>e.id==eq.equipment_id);
        marker.transform.localPosition=kind=="oil-leak" ? new Vector3(.65f,.07f,-.45f) : kind=="obstruction" ? new Vector3(1.5f,1.25f,0) : new Vector3(-.5f+count*.22f,2.8f,0);
        marker.transform.localScale=kind=="oil-leak" ? new Vector3(.5f,.025f,.35f) : kind=="obstruction" ? new Vector3(.65f,.25f,.65f) : Vector3.one*.14f;
        var material=new Material(Shader.Find("Standard"));
        material.color=kind=="oil-leak" ? new Color(.12f,.075f,.025f) : Severity=="critical" ? FactoryRules.Red : FactoryRules.Amber;
        marker.GetComponent<Renderer>().sharedMaterial=material; materials.Add(material);
        var effect=new Effect {id=eq.equipment_id,kind=kind,marker=marker.transform,position=marker.transform.localPosition,scale=marker.transform.localScale};
        if(kind=="vibration") {
            string prefix=eq.profile_id=="gr" ? "GearHousing" : eq.profile_id=="rt" ? "BearingCover" : "DrumBearingCover";
            effect.part=root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t=>t.name.StartsWith(prefix));
            if(effect.part!=null) effect.partPosition=effect.part.localPosition;
        }
        var text=new GameObject("Fault annotation").AddComponent<TextMesh>(); text.transform.SetParent(marker.transform,false);
        text.transform.localScale=new Vector3(1/marker.transform.localScale.x,1/marker.transform.localScale.y,1/marker.transform.localScale.z);
        text.transform.localPosition=Vector3.up*2; text.text=label; text.characterSize=.065f; text.fontSize=32; text.anchor=TextAnchor.LowerCenter;
        effects.Add(effect);
    }
    public void SetOnline(bool value)
    {
        online=value;
        if(!value) audioSource?.Stop();
    }
    public void Mute() { muted=true; audioSource?.Stop(); }
    void Update() { if(online && Severity!="normal" && Input.GetKeyDown(KeyCode.M)) Mute(); }
    void UpdateSound()
    {
        if(audioSource==null) return;
        if(!online || muted || Severity=="normal" || Severity=="unavailable") { audioSource.Stop(); return; }
        if(Severity=="critical") {
            if(audioSource.clip!=emergencyClip || !audioSource.isPlaying) { audioSource.clip=emergencyClip; audioSource.loop=true; audioSource.Play(); }
        } else if(elapsed>=nextBeep) {
            audioSource.loop=false; audioSource.clip=warningClip; audioSource.Play(); nextBeep=elapsed+6;
        }
    }
    public void Advance(float dt)
    {
        if(!online || dt<=0 || float.IsNaN(dt) || float.IsInfinity(dt)) return;
        elapsed+=dt;
        foreach(var effect in effects) {
            if(effect.part!=null) effect.part.localPosition=effect.partPosition+Vector3.right*Mathf.Sin(elapsed*35)*.018f;
            effect.marker.localScale=effect.scale*(1+.15f*Mathf.Sin(elapsed*5));
            if(effect.kind=="heat") effect.marker.localPosition=effect.position+Vector3.up*Mathf.Repeat(elapsed*.4f,.4f);
            var text=effect.marker.GetComponentInChildren<TextMesh>();
            if(text!=null && Camera.main!=null) text.transform.rotation=Camera.main.transform.rotation;
        }
        UpdateSound();
    }
    void ClearEffects()
    {
        foreach(var effect in effects) {
            if(effect.part!=null) effect.part.localPosition=effect.partPosition;
            if(effect.marker!=null) { effect.marker.gameObject.SetActive(false); Remove(effect.marker.gameObject); }
        }
        effects.Clear(); foreach(var material in materials) Remove(material); materials.Clear();
    }
    public void Clear()
    {
        ClearEffects(); current=null; online=false; Severity="normal"; Notification=""; UnknownEquipmentCount=0;
        incident=null; muted=false; elapsed=nextBeep=0; audioSource?.Stop();
    }
    public bool ContainsPointer(Vector2 point) { return current!=null && Severity!="normal" && new Rect(18,Screen.height-285,Mathf.Min(640,Screen.width-36),130).Contains(point); }
    void OnGUI()
    {
        if(current==null || Severity=="normal") return;
        var previous=GUI.color; GUI.color=!online ? FactoryRules.Grey : Severity=="critical" ? FactoryRules.Red : FactoryRules.Amber;
        GUILayout.BeginArea(new Rect(18,Screen.height-285,Mathf.Min(640,Screen.width-36),130),GUI.skin.box);
        GUILayout.Label((online ? "" : "MES 연결 끊김 · 마지막 관측, 현재 상태 미확인\n")+Notification,new GUIStyle(GUI.skin.label) {wordWrap=true});
        if(online && GUILayout.Button(muted ? "알림음 꺼짐 (알림 유지)" : "이번 알림음 끄기")) Mute();
        GUILayout.EndArea(); GUI.color=previous;
    }
    static void Remove(UnityEngine.Object obj) { if(obj==null) return; if(Application.isPlaying) Destroy(obj); else DestroyImmediate(obj); }
    void OnDestroy() { Clear(); Remove(warningClip); Remove(emergencyClip); }
}
