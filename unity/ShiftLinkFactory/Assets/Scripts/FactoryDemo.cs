using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

[Serializable] public class EquipmentSpec { public string equipment_id, code, name, profile_id; public bool active; }
[Serializable] public class BranchSpec { public string from_id, to_id; }
[Serializable] public class RelationSpec { public string from_id,to_id,relation_type; }
[Serializable] public class MeasurementReading { public string equipment_id,signal,unit,quality; public float value; }
[Serializable] public class FactoryConfig { public string config_id, line_id; public EquipmentSpec[] equipment; public string[] route; public BranchSpec[] branches; public RelationSpec[] relations; }
[Serializable] public class ConfigEnvelope { public FactoryConfig config; }
[Serializable] public class EquipmentReading { public string equipment_id, operating_state, fault_level; }
[Serializable] public class CoilReading { public string coil_id, equipment_id; public float position; }
[Serializable] public class MesSnapshot { public string config_id, run_id, line_mode, scenario_id; public int sequence; public EquipmentReading[] equipment; public CoilReading[] coils; public MeasurementReading[] measurements; }
[Serializable] public class ScanReading { public string scan_id, equipment_id, device_id; public float conf; }
[Serializable] public class ScanEnvelope { public ScanReading[] scans; }

public static class FactoryRules
{
    public static readonly Color Green = new Color(.12f, .85f, .52f);
    public static readonly Color Amber = new Color(1f, .66f, .16f);
    public static readonly Color Red = new Color(1f, .22f, .25f);
    public static readonly Color Grey = new Color(.43f, .49f, .56f);
    public static Color StateColor(string state, string fault)
    {
        if (fault == "critical") return Red;
        if (fault == "warning" || state == "waiting") return Amber;
        return state == "running" ? Green : Grey;
    }
    public static bool Valid(FactoryConfig config)
    {
        if (config == null || string.IsNullOrEmpty(config.config_id) || config.equipment == null ||
            config.equipment.Length == 0 || config.route == null) return false;
        var ids = new HashSet<string>();
        foreach (var e in config.equipment)
            if (e == null || string.IsNullOrEmpty(e.equipment_id) || !ids.Add(e.equipment_id)) return false;
        var active = new HashSet<string>();
        foreach (var e in config.equipment) if (e.active) active.Add(e.equipment_id);
        var routeIds = new HashSet<string>();
        foreach (var id in config.route)
            if (string.IsNullOrEmpty(id) || !active.Contains(id) || !routeIds.Add(id)) return false;
        if (config.branches != null)
            foreach (var branch in config.branches)
                if (branch == null || !ids.Contains(branch.from_id) || !ids.Contains(branch.to_id) || branch.from_id == branch.to_id) return false;
        return true;
    }
    public static bool Matches(FactoryConfig config, MesSnapshot snapshot)
    {
        if (!Valid(config) || snapshot == null || snapshot.config_id != config.config_id ||
            snapshot.equipment == null || snapshot.coils == null || string.IsNullOrEmpty(snapshot.run_id)) return false;
        var ids = new HashSet<string>();
        foreach (var e in config.equipment) if (e.active) ids.Add(e.equipment_id);
        var seen = new HashSet<string>();
        foreach (var e in snapshot.equipment)
            if (e == null || !ids.Contains(e.equipment_id) || !seen.Add(e.equipment_id)) return false;
        if (!ids.SetEquals(seen)) return false;
        var coilIds = new HashSet<string>();
        foreach (var coil in snapshot.coils)
            if (coil == null || string.IsNullOrEmpty(coil.coil_id) || !coilIds.Add(coil.coil_id) || !ids.Contains(coil.equipment_id) ||
                float.IsNaN(coil.position) || float.IsInfinity(coil.position) || coil.position < 0 || coil.position > 1) return false;
        return true;
    }
}

public class FactoryDemo : MonoBehaviour
{
    public string mesUrl = "http://127.0.0.1:8000";
    public string pdaUrl = "http://127.0.0.1:8000";
    public float pollSeconds = .5f;
    FactoryConfig config;
    MesSnapshot snapshot;
    Transform equipmentRoot, coilRoot;
    readonly Dictionary<string, GameObject> equipment = new Dictionary<string, GameObject>();
    readonly Dictionary<string, Renderer> lamps = new Dictionary<string, Renderer>();
    readonly Dictionary<string, Vector3> positions = new Dictionary<string, Vector3>();
    readonly Dictionary<Color, Material> materials = new Dictionary<Color, Material>();
    readonly Dictionary<string, EquipmentReading> readings = new Dictionary<string, EquipmentReading>();
    string selectedId, lastScanId, status = "Connecting to MES...";
    bool online, controlBusy, environmentCreated;
    float lastSuccess, yaw = -20, pitch = 48, distance = 44;
    Vector3 target;
    Camera viewCamera;
    FactoryRig rig;
    readonly Dictionary<string,Transform> coilObjects=new Dictionary<string,Transform>();
    readonly Dictionary<string,Vector3> coilTargets=new Dictionary<string,Vector3>();
    readonly Dictionary<string,string> coilEquipment=new Dictionary<string,string>();
    public int EquipmentCount { get { return equipment.Count; } }
    public int CoilCount { get { return coilRoot == null ? 0 : coilRoot.childCount; } }
    public string SelectedId { get { return selectedId; } }
    public bool Connected { get { return online; } }
    public string CurrentRunId { get { return snapshot == null ? null : snapshot.run_id; } }
    public int CurrentSequence { get { return snapshot == null ? -1 : snapshot.sequence; } }

    void Start()
    {
        for (int i = transform.childCount - 1; i >= 0; i--) Remove(transform.GetChild(i).gameObject);
        var args = Environment.GetCommandLineArgs();
        for (int i = 0; i + 1 < args.Length; i++) {
            if (args[i] == "--mes-url") mesUrl = args[++i];
            else if (args[i] == "--pda-url") pdaUrl = args[++i];
        }
        mesUrl = mesUrl.TrimEnd('/'); pdaUrl = pdaUrl.TrimEnd('/');
        CreateEnvironment();
        // The saved editor scene is a preview; live state is required before showing coils.
        Disconnect("Connecting to MES...");
        StartCoroutine(Poll());
    }
    public void CreateEnvironment()
    {
        if (environmentCreated) return;
        environmentCreated = true;
        viewCamera = Camera.main;
        if (viewCamera == null) {
            viewCamera = new GameObject("Factory Camera").AddComponent<Camera>();
            viewCamera.tag = "MainCamera";
        }
        viewCamera.clearFlags = CameraClearFlags.SolidColor;
        viewCamera.backgroundColor = new Color(.045f, .065f, .10f);
        viewCamera.farClipPlane = 300;
        if (FindFirstObjectByType<Light>() == null) {
            var light = new GameObject("Factory Sun").AddComponent<Light>();
            light.type = LightType.Directional; light.intensity = 1.3f;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);
        }
        RenderSettings.ambientLight = new Color(.52f, .58f, .68f);
        Shape(PrimitiveType.Cube, "Factory floor", transform, new Vector3(0,-.22f,0),
            new Vector3(90,.35f,32), new Color(.09f,.13f,.18f));
        for (int x = -40; x <= 40; x += 4)
            Shape(PrimitiveType.Cube, "Floor grid", transform, new Vector3(x,-.02f,0),
                new Vector3(.025f,.01f,30), new Color(.17f,.22f,.28f));
        UpdateCamera();
    }
    public void Build(FactoryConfig next)
    {
        if (!FactoryRules.Valid(next)) throw new ArgumentException("Invalid MES configuration");
        ClearCoils();
        if (equipmentRoot != null) Remove(equipmentRoot.gameObject);
        if (coilRoot != null) Remove(coilRoot.gameObject);
        equipment.Clear(); lamps.Clear(); positions.Clear(); readings.Clear();
        equipmentRoot = new GameObject("MES equipment").transform; equipmentRoot.SetParent(transform);
        coilRoot = new GameObject("MES coils").transform; coilRoot.SetParent(transform);
        config = next;
        var route = new List<string>(next.route);
        int auxiliary = 0;
        foreach (var e in next.equipment) {
            int index = route.IndexOf(e.equipment_id);
            var pos = FactoryRig.Layout(e.code,index,route.Count,auxiliary++);
            positions[e.equipment_id] = pos;
            var root = new GameObject(e.equipment_id);
            root.transform.SetParent(equipmentRoot); root.transform.localPosition = pos;
            equipment[e.equipment_id] = root;
            Model(e, root.transform);
            lamps[e.equipment_id] = root.GetComponentsInChildren<Renderer>().First(r=>r.name.StartsWith("StatusLens_"));
            var text = new GameObject("Equipment code").AddComponent<TextMesh>();
            text.transform.SetParent(root.transform); text.transform.localPosition = new Vector3(0,4,0);
            text.text = e.code; text.anchor = TextAnchor.MiddleCenter; text.alignment = TextAlignment.Center;
            text.fontSize = 48; text.characterSize = .12f; text.color = Color.white; text.transform.rotation = viewCamera.transform.rotation;
            root.SetActive(e.active);
        }
        rig=equipmentRoot.gameObject.AddComponent<FactoryRig>();
        rig.Build(next,equipment);
        target = new Vector3(0,1,2);
        distance = Mathf.Max(25, next.route.Length*6);
        selectedId = null; lastScanId = null; UpdateCamera();
    }
    void Model(EquipmentSpec e, Transform root)
    {
        FactoryRig.InstantiateEquipment(e,root);
    }
    public void Apply(MesSnapshot next)
    {
        if (!FactoryRules.Matches(config,next)) { Disconnect("MES configuration changed; reconnecting"); return; }
        if(snapshot!=null && snapshot.run_id==next.run_id && next.sequence<snapshot.sequence) return;
        if(snapshot!=null && snapshot.run_id!=next.run_id) ClearCoils();
        snapshot=next; readings.Clear();
        foreach (var e in next.equipment) {
            readings[e.equipment_id]=e;
            lamps[e.equipment_id].sharedMaterial=MaterialFor(FactoryRules.StateColor(e.operating_state,e.fault_level));
        }
        var keep=new HashSet<string>();
        foreach(var c in next.coils) {
            keep.Add(c.coil_id);
            var destination=rig.MaterialPosition(c.equipment_id,c.position);
            Transform coil;
            bool scrap=config.equipment.First(e=>e.equipment_id==c.equipment_id).code=="CV-02";
            if(coilObjects.TryGetValue(c.coil_id,out coil) && (coil.Find("Rejected cut sheet")!=null)!=scrap) {
                coil.SetParent(null); Remove(coil.gameObject); coilObjects.Remove(c.coil_id);
            }
            if(!coilObjects.TryGetValue(c.coil_id,out coil)) {
                coil=FactoryRig.CreateLoad(c.coil_id,coilRoot,scrap);
                coil.position=destination; coilObjects[c.coil_id]=coil;
            }
            coilTargets[c.coil_id]=destination; coilEquipment[c.coil_id]=c.equipment_id;
        }
        foreach(var id in coilObjects.Keys.Where(id=>!keep.Contains(id)).ToArray()) {
            var stale=coilObjects[id]; stale.SetParent(null); Remove(stale.gameObject);
            coilObjects.Remove(id); coilTargets.Remove(id); coilEquipment.Remove(id);
        }
        online=true; lastSuccess=Time.realtimeSinceStartup;
        status=next.line_mode+" | "+next.scenario_id+" | tick "+next.sequence;
    }
    public void ApplyScans(ScanEnvelope scans)
    {
        if(scans==null || scans.scans==null) return;
        if(scans.scans.Length==0) { lastScanId=null; return; }
        var scan=scans.scans[0];
        if(scan==null || string.IsNullOrEmpty(scan.scan_id) || string.IsNullOrEmpty(scan.equipment_id)) return;
        if(scan.scan_id!=lastScanId && equipment.ContainsKey(scan.equipment_id) && equipment[scan.equipment_id].activeSelf) {
            selectedId=scan.equipment_id; lastScanId=scan.scan_id;
        }
    }
    public void Disconnect(string reason)
    {
        online=false; snapshot=null; readings.Clear(); status=reason;
        foreach(var lamp in lamps.Values) lamp.sharedMaterial=MaterialFor(FactoryRules.Grey);
        ClearCoils();
    }
    void ClearCoils()
    {
        coilObjects.Clear(); coilTargets.Clear(); coilEquipment.Clear();
        if(coilRoot==null) return;
        for(int i=coilRoot.childCount-1;i>=0;i--) {
            var child=coilRoot.GetChild(i); child.SetParent(null); Remove(child.gameObject);
        }
    }
    IEnumerator Get(string path, Action<string> completed)
    {
        using(var req=UnityWebRequest.Get(mesUrl+path)) {
            req.timeout=5; yield return req.SendWebRequest();
            if(req.result!=UnityWebRequest.Result.Success) { Disconnect("MES unavailable ("+req.responseCode+")"); completed(null); }
            else completed(req.downloadHandler.text);
        }
    }
    T Parse<T>(string json) where T:class
    {
        try { return JsonUtility.FromJson<T>(json); }
        catch(Exception) { Disconnect("Invalid MES response"); return null; }
    }
    IEnumerator Poll()
    {
        while(true) {
            string body=null;
            yield return Get("/api/state",value=>body=value);
            var state=body==null ? null : Parse<MesSnapshot>(body);
            if(state!=null) {
                if(config==null || state.config_id!=config.config_id) {
                    Disconnect("Loading MES configuration...");
                    body=null; yield return Get("/api/config",value=>body=value);
                    var envelope=body==null ? null : Parse<ConfigEnvelope>(body);
                    if(envelope!=null && FactoryRules.Valid(envelope.config)) Build(envelope.config);
                    else Disconnect("Invalid MES configuration");
                }
                Apply(state);
                if(online) {
                    body=null; yield return Get("/api/equipment/scan/recent?limit=1",value=>body=value);
                    if(body!=null) ApplyScans(Parse<ScanEnvelope>(body));
                }
            } else if(body!=null) Disconnect("Invalid MES snapshot");
            yield return new WaitForSecondsRealtime(Mathf.Max(.2f,pollSeconds));
        }
    }
    IEnumerator Control(string command, string scenarioId=null)
    {
        if(controlBusy || !online) yield break;
        controlBusy=true;
        string json="{\"command\":\""+command+"\""+(scenarioId==null ? "" : ",\"scenario_id\":\""+scenarioId+"\"")+"}";
        using(var req=new UnityWebRequest(mesUrl+"/api/control","POST")) {
            req.uploadHandler=new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
            req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json");
            req.timeout=5; yield return req.SendWebRequest();
            if(req.result==UnityWebRequest.Result.Success) {
                var next=Parse<MesSnapshot>(req.downloadHandler.text);
                if(next!=null) Apply(next);
            } else status="Control rejected (HTTP "+req.responseCode+")";
        }
        controlBusy=false;
    }
    void Update()
    {
        if(online && Time.realtimeSinceStartup-lastSuccess>8) Disconnect("MES updates timed out");
        AdvanceVisuals(Time.deltaTime);
        if(viewCamera==null) return;
        if(Input.GetMouseButton(1)) { yaw+=Input.GetAxis("Mouse X")*3; pitch=Mathf.Clamp(pitch-Input.GetAxis("Mouse Y")*2,20,80); }
        distance=Mathf.Clamp(distance-Input.mouseScrollDelta.y*2,15,130);
        UpdateCamera();
        var guiPointer = new Vector2(Input.mousePosition.x, Screen.height-Input.mousePosition.y);
        bool overPanel = new Rect(18,18,Mathf.Min(700,Screen.width-36),200).Contains(guiPointer) ||
            (!string.IsNullOrEmpty(selectedId) && new Rect(18,Screen.height-145,Mathf.Min(560,Screen.width-36),125).Contains(guiPointer));
        if(Input.GetMouseButtonDown(0) && !overPanel) {
            RaycastHit hit;
            if(Physics.Raycast(viewCamera.ScreenPointToRay(Input.mousePosition),out hit)) {
                var node=hit.transform;
                while(node!=null) { if(equipment.ContainsKey(node.name)) { selectedId=node.name; break; } node=node.parent; }
            }
        }
        if(equipmentRoot!=null) foreach(var label in equipmentRoot.GetComponentsInChildren<TextMesh>())
            label.transform.rotation=viewCamera.transform.rotation;
    }
    public void AdvanceVisuals(float seconds)
    {
        if(!online || rig==null || seconds<=0 || float.IsNaN(seconds) || float.IsInfinity(seconds)) return;
        rig.Advance(snapshot,seconds);
        foreach(var pair in coilObjects) {
            EquipmentReading state;
            if(readings.TryGetValue(coilEquipment[pair.Key],out state) && state.operating_state=="running" && state.fault_level!="critical" && snapshot.line_mode=="running")
                pair.Value.position=Vector3.MoveTowards(pair.Value.position,coilTargets[pair.Key],10*seconds);
        }
    }
    void UpdateCamera()
    {
        if(viewCamera==null) return;
        viewCamera.transform.position=target+Quaternion.Euler(pitch,yaw,0)*new Vector3(0,0,-distance);
        viewCamera.transform.LookAt(target);
    }
    void OnGUI()
    {
        GUI.backgroundColor=new Color(.07f,.12f,.19f,.96f);
        GUILayout.BeginArea(new Rect(18,18,Mathf.Min(700,Screen.width-36),200),GUI.skin.box);
        GUILayout.Label("SHIFTLINK / FACTORY + MES + PDA");
        GUI.color=online ? FactoryRules.Green : FactoryRules.Amber; GUILayout.Label(status); GUI.color=Color.white;
        GUILayout.BeginHorizontal(); GUILayout.Label("MES",GUILayout.Width(40)); GUILayout.Label(mesUrl); GUILayout.EndHorizontal();
        GUILayout.BeginHorizontal(); GUILayout.Label("PDA",GUILayout.Width(40)); GUILayout.Label(pdaUrl); GUILayout.EndHorizontal();
        GUILayout.BeginHorizontal(); GUI.enabled=online && !controlBusy;
        if(GUILayout.Button("Start")) StartCoroutine(Control("start"));
        if(GUILayout.Button("Pause")) StartCoroutine(Control("pause"));
        if(GUILayout.Button("Resume")) StartCoroutine(Control("resume"));
        GUI.enabled=true; GUILayout.EndHorizontal();
        GUILayout.Label("Right drag: orbit | Wheel: zoom | Click equipment: select");
        if (GUILayout.Button("Open MES dashboard / fault scenarios")) Application.OpenURL(mesUrl.TrimEnd('/')+"/");
        GUILayout.EndArea();
        if(!string.IsNullOrEmpty(selectedId) && equipment.ContainsKey(selectedId)) {
            GUILayout.BeginArea(new Rect(18,Screen.height-145,Mathf.Min(560,Screen.width-36),125),GUI.skin.box);
            GUILayout.Label("Selected: "+selectedId+" | Latest PDA scan: "+(lastScanId ?? "none"));
            EquipmentReading reading; if(readings.TryGetValue(selectedId,out reading)) GUILayout.Label(reading.operating_state+" / "+reading.fault_level);
            if(GUILayout.Button("Open this equipment on PDA"))
                Application.OpenURL(pdaUrl.TrimEnd('/')+"/pda.html?equipment_id="+UnityWebRequest.EscapeURL(selectedId)+"&source=unity");
            GUILayout.EndArea();
            Vector3 pos=viewCamera.WorldToScreenPoint(positions[selectedId]+Vector3.up*5);
            if(pos.z>0) { GUI.color=FactoryRules.Amber; GUI.Label(new Rect(pos.x-60,Screen.height-pos.y,160,30),"SELECTED / PDA"); GUI.color=Color.white; }
        }
    }
    Material MaterialFor(Color color)
    {
        Material result;
        if(!materials.TryGetValue(color,out result)) {
            result=new Material(Shader.Find("Standard")); result.color=color; materials[color]=result;
        }
        return result;
    }
    GameObject Shape(PrimitiveType type,string name,Transform parent,Vector3 pos,Vector3 size,Color color)
    {
        var shape=GameObject.CreatePrimitive(type); shape.name=name; shape.transform.SetParent(parent);
        shape.transform.localPosition=pos; shape.transform.localScale=size;
        shape.GetComponent<Renderer>().sharedMaterial=MaterialFor(color); return shape;
    }
    static void Remove(UnityEngine.Object obj) { if(Application.isPlaying) Destroy(obj); else DestroyImmediate(obj); }
    void OnDestroy() { foreach(var mat in materials.Values) Remove(mat); }
}
