using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

[Serializable] public class SignalSemantics { public string acquisition; }
[Serializable] public class SignalSpec { public string signal,name,unit; public float normal_min,normal_max; public bool zero_when_stopped; public SignalSemantics semantics; }
[Serializable] public class EquipmentSpec { public string equipment_id, code, name, profile_id; public bool active; public SignalSpec[] signals; }
[Serializable] public class BranchSpec { public string from_id, to_id; }
[Serializable] public class RelationSpec { public string from_id,to_id,relation_type; }
[Serializable] public class MeasurementReading { public string equipment_id,signal,unit,quality,observed_at; public float value; }
[Serializable] public class FactoryConfig { public string config_id, line_id; public EquipmentSpec[] equipment; public string[] route; public BranchSpec[] branches; public RelationSpec[] relations; }
[Serializable] public class ConfigEnvelope { public FactoryConfig config; }
[Serializable] public class EquipmentReading { public string equipment_id, operating_state, fault_level; }
[Serializable] public class CoilReading { public string coil_id, equipment_id,quality_status; public float position; }
[Serializable] public class MesSnapshot { public string config_id, run_id, line_mode, scenario_id; public int sequence; public EquipmentReading[] equipment; public CoilReading[] coils; public MeasurementReading[] measurements; }
[Serializable] public class ScanReading { public string scan_id, equipment_id, device_id; public float conf; }
[Serializable] public class ScanEnvelope { public ScanReading[] scans; }
[Serializable] public class EquipmentSelection { public string equipment_id, config_id; }

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
    bool exteriorView=true;
    Transform exteriorEnvelope;
    readonly List<Mesh> buildingMeshes=new List<Mesh>();
    float lastSuccess, yaw = -20, pitch = 48, distance = 44;
    Vector3 target;
    Camera viewCamera;
    FactoryRig rig;
    FactoryLogistics logistics;
    FactoryWorker worker;
    FactoryCapture capture;
    readonly Dictionary<string,Transform> coilObjects=new Dictionary<string,Transform>();
    readonly Dictionary<string,Vector3> coilTargets=new Dictionary<string,Vector3>();
    readonly Dictionary<string,string> coilEquipment=new Dictionary<string,string>();
    class LineWaypoint { public Vector3 position; public string from,to; }
    class ScrapExit { public Transform load; public string equipmentId; public Queue<Vector3> path; public Queue<LineWaypoint> transfer; public float fallSpeed; }
    readonly Dictionary<string,Queue<LineWaypoint>> coilWaypoints=new Dictionary<string,Queue<LineWaypoint>>();
    readonly Dictionary<string,ScrapExit> scrapExits=new Dictionary<string,ScrapExit>();
    readonly Dictionary<string,int> scrapSlots=new Dictionary<string,int>();
    Transform scrapRoot;
    int scrapCount;
    public int EquipmentCount { get { return equipment.Count; } }
    public int CoilCount { get { return coilRoot == null ? 0 : coilRoot.childCount; } }
    public int ScrapCount { get { return scrapCount; } }
    public int DischargingScrapCount { get { return scrapExits.Count; } }
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
        RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(.32f, .36f, .42f);
        QualitySettings.pixelLightCount=8;
        Shape(PrimitiveType.Cube, "Factory apron", transform, new Vector3(0,-.42f,0),
            new Vector3(58,.3f,46), new Color(.24f,.27f,.3f));
        Shape(PrimitiveType.Cube, "Factory floor", transform, new Vector3(0,-.22f,0),
            new Vector3(44,.35f,34), new Color(.24f,.29f,.34f));
        for (int x = -20; x <= 20; x += 4)
            Shape(PrimitiveType.Cube, "Floor grid", transform, new Vector3(x,-.02f,0),
                new Vector3(.025f,.01f,33), new Color(.32f,.36f,.4f));
        InstallBuilding();
        logistics=GetComponent<FactoryLogistics>()??gameObject.AddComponent<FactoryLogistics>();
        logistics.Build();
        UpdateCamera();
        FactoryMonitor.RefreshFor(this,null,null,false);
        SetExteriorView(exteriorView);
        FactoryWalkGeometry.Prepare(transform);
        capture=GetComponent<FactoryCapture>()??gameObject.AddComponent<FactoryCapture>();
        worker=GetComponent<FactoryWorker>()??gameObject.AddComponent<FactoryWorker>();
        worker.Initialize(this,viewCamera);
    }
    void InstallBuilding()
    {
        var building=new GameObject("Factory building").transform; building.SetParent(transform,false);
        exteriorEnvelope=new GameObject("Exterior envelope").transform; exteriorEnvelope.SetParent(building,false);
        Color wall=new Color(.64f,.69f,.72f), steel=new Color(.24f,.32f,.4f), roof=new Color(.15f,.23f,.3f);
        // 44 x 34m synthetic hall: eaves 8m, ridge 10m. Openings remain usable in exterior view.
        foreach(var panel in new[]{new Vector3(-19.95f,4,-17),new Vector3(-9.35f,4,-17),new Vector3(12.5f,4,-17)}) {
            float width=panel.x<-18 ? 4.1f : panel.x<0 ? 12.7f : 19;
            Shape(PrimitiveType.Cube,"Front wall",exteriorEnvelope,panel,new Vector3(width,8,.25f),wall);
        }
        Shape(PrimitiveType.Cube,"Loading door lintel",exteriorEnvelope,new Vector3(0,6.5f,-17),new Vector3(6,3,.25f),wall);
        Shape(PrimitiveType.Cube,"Personnel door lintel",exteriorEnvelope,new Vector3(-16.8f,5.2f,-17),new Vector3(2.2f,5.6f,.25f),wall);
        Shape(PrimitiveType.Cube,"Rear wall",exteriorEnvelope,new Vector3(0,4,17),new Vector3(44,8,.25f),wall);
        // The finishing hall shares the east side; keep this connection open.
        foreach(float x in new[]{-22f}) {
            foreach(float z in new[]{-10f,10f}) Shape(PrimitiveType.Cube,"Side wall",exteriorEnvelope,new Vector3(x,4,z),new Vector3(.25f,8,14),wall);
            Shape(PrimitiveType.Cube,"Side loading door lintel",exteriorEnvelope,new Vector3(x,6.5f,0),new Vector3(.25f,3,6),wall);
        }
        foreach(float x in new[]{-21.6f,21.6f}) foreach(float z in new[]{-15.5f,-7.5f,-3.3f,3.3f,8.5f,15.5f})
            Shape(PrimitiveType.Cube,"Steel column",building,new Vector3(x,4,z),new Vector3(.3f,8,.3f),steel);
        float slope=Mathf.Atan2(2,17)*Mathf.Rad2Deg;
        foreach(float z in new[]{-8.5f,8.5f}) {
            var skin=Shape(PrimitiveType.Cube,"Pitched roof",exteriorEnvelope,new Vector3(0,9,z),new Vector3(44.8f,.2f,17.6f),roof);
            skin.transform.localRotation=Quaternion.Euler(z<0 ? -slope : slope,0,0);
            for(float x=-21;x<=21;x+=7) {
                var beam=Shape(PrimitiveType.Cube,"Roof rafter",exteriorEnvelope,new Vector3(x,8.75f,z),new Vector3(.18f,.25f,17.2f),steel);
                beam.transform.localRotation=skin.transform.localRotation;
            }
            for(float x=-22;x<=22;x+=2) {
                var rib=Shape(PrimitiveType.Cube,"Roof seam",exteriorEnvelope,new Vector3(x,9.13f,z),new Vector3(.055f,.08f,17.6f),steel);
                rib.transform.localRotation=skin.transform.localRotation;
            }
        }
        foreach(float z in new[]{-16.8f,0,16.8f}) Shape(PrimitiveType.Cube,"Roof purlin",exteriorEnvelope,new Vector3(0,z==0 ? 9.6f : 7.7f,z),new Vector3(43.6f,.18f,.18f),steel);
        // The finishing hall shares the east side; keep this connection open.
        foreach(float x in new[]{-22f}) {
            var gable=new GameObject("Gable end"); gable.transform.SetParent(exteriorEnvelope,false); gable.transform.localPosition=Vector3.right*x;
            var mesh=new Mesh(); mesh.vertices=new[]{new Vector3(0,8,-17),new Vector3(0,8,17),new Vector3(0,10,0)};
            mesh.triangles=x<0 ? new[]{0,1,2} : new[]{0,2,1}; mesh.RecalculateNormals(); mesh.RecalculateBounds(); buildingMeshes.Add(mesh);
            gable.AddComponent<MeshFilter>().sharedMesh=mesh; gable.AddComponent<MeshRenderer>().sharedMaterial=MaterialFor(wall);
        }
        foreach(float z in new[]{-17.4f,17.4f}) {
            Shape(PrimitiveType.Cube,"Roof gutter",exteriorEnvelope,new Vector3(0,7.9f,z),new Vector3(44.6f,.18f,.2f),steel);
            foreach(float x in new[]{-22.3f,22.3f}) Shape(PrimitiveType.Cylinder,"Rainwater downpipe",exteriorEnvelope,new Vector3(x,3.95f,z),new Vector3(.13f,3.95f,.13f),steel);
        }
        foreach(float x in new[]{-18f,-12f,-6f,6f,12f,18f}) {
            Shape(PrimitiveType.Cube,"Window frame",exteriorEnvelope,new Vector3(x,5.9f,-17.16f),new Vector3(3.2f,1.6f,.12f),steel);
            Shape(PrimitiveType.Cube,"Window glazing",exteriorEnvelope,new Vector3(x,5.9f,-17.24f),new Vector3(2.95f,1.35f,.04f),new Color(.18f,.37f,.48f));
        }
        foreach(float x in new[]{-3.1f,3.1f}) Shape(PrimitiveType.Cube,"Loading door jamb",exteriorEnvelope,new Vector3(x,2.5f,-17.2f),new Vector3(.15f,5,.18f),steel);
        Shape(PrimitiveType.Cube,"Entry canopy",exteriorEnvelope,new Vector3(-16.8f,2.7f,-17.7f),new Vector3(2.6f,.15f,1.6f),steel);
        Shape(PrimitiveType.Cube,"Personnel entry route",building,new Vector3(-16.8f,-.035f,-13.25f),new Vector3(1.5f,.012f,7.5f),new Color(.12f,.4f,.3f));
        var sign=new GameObject("Factory facade sign").AddComponent<TextMesh>(); sign.transform.SetParent(exteriorEnvelope,false);
        sign.transform.localPosition=new Vector3(0,7.1f,-17.3f); sign.text="SHIFTLINK FACTORY"; sign.anchor=TextAnchor.MiddleCenter; sign.fontSize=64; sign.characterSize=.2f; sign.color=Color.white;
        var fixtures=new GameObject("Factory lighting").transform; fixtures.SetParent(building,false);
        foreach(float x in new[]{-15f,-5f,5f,15f}) foreach(float z in new[]{-9f,0,9f})
            InstallLight(fixtures,new Vector3(x,7.1f,z),false);
        foreach(float x in new[]{-18f,-8f,8f,18f}) InstallLight(fixtures,new Vector3(x,5.4f,-17.6f),true);
    }
    void InstallLight(Transform parent,Vector3 position,bool outside)
    {
        if(!outside) {
            float ceiling=10-2*Mathf.Abs(position.z)/17, length=ceiling-position.y-.2f;
            Shape(PrimitiveType.Cylinder,"Light suspension",parent,position+Vector3.up*(.2f+length*.5f),new Vector3(.025f,length*.5f,.025f),FactoryRules.Grey);
        }
        Shape(PrimitiveType.Cube,"LED fixture housing",parent,position+Vector3.up*.15f,new Vector3(1.4f,.15f,.45f),new Color(.2f,.24f,.28f));
        var diffuser=Shape(PrimitiveType.Cube,"LED diffuser",parent,position+Vector3.up*.055f,new Vector3(1.25f,.04f,.32f),new Color(.9f,.95f,1));
        var emission=MaterialFor(new Color(.9f,.95f,1)); emission.EnableKeyword("_EMISSION"); emission.SetColor("_EmissionColor",new Color(.8f,.9f,1)*1.5f);
        diffuser.GetComponent<Renderer>().sharedMaterial=emission;
        var light=new GameObject(outside ? "Exterior LED light" : "Interior LED light").AddComponent<Light>(); light.transform.SetParent(parent,false); light.transform.localPosition=position;
        light.type=LightType.Spot; light.color=new Color(.88f,.94f,1); light.intensity=outside ? 1.5f : 2; light.range=outside ? 12 : 16; light.spotAngle=outside ? 100 : 110;
        light.transform.localRotation=Quaternion.Euler(outside ? 55 : 90,180,0);
        light.renderMode=LightRenderMode.ForcePixel; light.shadows=LightShadows.None;
    }
    public void SetExteriorView(bool exterior)
    {
        exteriorView=exterior;
        bool enclosed=exterior || (worker!=null && worker.IsWorkerMode);
        if(exteriorEnvelope!=null) exteriorEnvelope.gameObject.SetActive(enclosed);
        if(logistics!=null) logistics.SetExterior(enclosed);
        var display=transform.Find("Factory status display"); if(display!=null) display.gameObject.SetActive(!enclosed);
        if(equipmentRoot!=null) foreach(var label in equipmentRoot.GetComponentsInChildren<TextMesh>(true)) label.gameObject.SetActive(!enclosed);
        target=exterior ? new Vector3(7,3,0) : new Vector3(8,2,3);
        distance=exterior ? 105 : 94; pitch=exterior ? 38 : 52; yaw=-20;
        UpdateCamera();
    }
    public void Build(FactoryConfig next)
    {
        if (!FactoryRules.Valid(next)) throw new ArgumentException("Invalid MES configuration");
        ClearCoils();
        if (equipmentRoot != null) Remove(equipmentRoot.gameObject);
        if (coilRoot != null) Remove(coilRoot.gameObject);
        if (scrapRoot != null) Remove(scrapRoot.gameObject);
        equipment.Clear(); lamps.Clear(); positions.Clear(); readings.Clear();
        equipmentRoot = new GameObject("MES equipment").transform; equipmentRoot.SetParent(transform);
        coilRoot = new GameObject("MES coils").transform; coilRoot.SetParent(transform);
        scrapRoot = new GameObject("MES scrap discharge").transform; scrapRoot.SetParent(transform);
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
            text.transform.SetParent(root.transform); text.transform.localPosition = new Vector3(0,EquipmentLabelHeight(root.transform),0);
            text.text = e.code; text.anchor = TextAnchor.MiddleCenter; text.alignment = TextAlignment.Center;
            text.fontSize = 48; text.characterSize = .12f; text.color = Color.white; text.transform.rotation = viewCamera.transform.rotation;
            root.SetActive(e.active);
        }
        rig=equipmentRoot.gameObject.AddComponent<FactoryRig>();
        rig.Build(next,equipment);
        target = new Vector3(0,2,3);
        distance = Mathf.Max(36, next.route.Length*6);
        selectedId = null; lastScanId = null; SetExteriorView(exteriorView);
        FactoryMonitor.RefreshFor(this,config,null,false);
        capture.Configure(worker.PdaCamera,config,equipment,0);
        capture.SetContext(config.config_id,null,-1);
    }
    void Model(EquipmentSpec e, Transform root)
    {
        FactoryRig.InstantiateEquipment(e,root);
    }
    static float EquipmentLabelHeight(Transform root)
    {
        return root.GetComponentsInChildren<Renderer>().Max(r=>r.bounds.max.y)-root.position.y+.45f;
    }
    public void Apply(MesSnapshot next)
    {
        if (!FactoryRules.Matches(config,next)) { Disconnect("MES configuration changed; reconnecting"); return; }
        if(snapshot!=null && snapshot.run_id==next.run_id && next.sequence<snapshot.sequence) return;
        if(snapshot!=null && snapshot.run_id!=next.run_id) ClearCoils();
        snapshot=next; readings.Clear();
        rig.ApplySensors(next);
        foreach (var e in next.equipment) {
            readings[e.equipment_id]=e;
            lamps[e.equipment_id].sharedMaterial=MaterialFor(FactoryRules.StateColor(e.operating_state,e.fault_level));
        }
        var keep=new HashSet<string>();
        foreach(var c in next.coils) {
            keep.Add(c.coil_id);
            var destination=rig.MaterialPosition(c.equipment_id,c.position);
            Transform coil;
            Vector3? previousPosition=null;
            string previousEquipment;
            if(coilEquipment.TryGetValue(c.coil_id,out previousEquipment) && previousEquipment!=c.equipment_id) {
                Queue<LineWaypoint> path;
                if(!coilWaypoints.TryGetValue(c.coil_id,out path)) coilWaypoints[c.coil_id]=path=new Queue<LineWaypoint>();
                foreach(var point in rig.TransferWaypoints(previousEquipment,c.equipment_id)) path.Enqueue(new LineWaypoint {position=point,from=previousEquipment,to=c.equipment_id});
            }
            bool scrap=IsScrapEquipment(c.equipment_id);
            if(coilObjects.TryGetValue(c.coil_id,out coil) && (coil.Find("Rejected cut sheet")!=null)!=scrap) {
                previousPosition=coil.position;
                coil.SetParent(null); Remove(coil.gameObject); coilObjects.Remove(c.coil_id);
            }
            if(!coilObjects.TryGetValue(c.coil_id,out coil)) {
                ScrapExit oldExit;
                if(scrapExits.TryGetValue(c.coil_id,out oldExit)) { oldExit.load.SetParent(null); Remove(oldExit.load.gameObject); scrapExits.Remove(c.coil_id); }
                coil=rig.CreateLineLoad(c.coil_id,coilRoot,scrap);
                coil.position=previousPosition??destination; coilObjects[c.coil_id]=coil;
            }
            coil.rotation=equipment[c.equipment_id].transform.rotation;
            coilTargets[c.coil_id]=destination; coilEquipment[c.coil_id]=c.equipment_id;
        }
        foreach(var id in coilObjects.Keys.Where(id=>!keep.Contains(id)).ToArray()) {
            var stale=coilObjects[id];
            if(IsScrapEquipment(coilEquipment[id])) {
                string exitEquipment=coilEquipment[id]; var path=rig.ScrapDischargeWaypoints(exitEquipment);
                int slot; scrapSlots.TryGetValue(exitEquipment,out slot); scrapSlots[exitEquipment]=slot+1;
                // Keep at most 20 visible layers; ScrapCount remains the cumulative MES discharge count.
                path[path.Length-1]+=Vector3.up*((slot%20)*.025f);
                stale.SetParent(scrapRoot,true);
                // MES placement on its configured scrap branch is authoritative; no defect diagnosis or cutting is inferred here.
                Queue<LineWaypoint> transfer; coilWaypoints.TryGetValue(id,out transfer);
                scrapExits[id]=new ScrapExit {load=stale,equipmentId=exitEquipment,path=new Queue<Vector3>(path),transfer=transfer};
            }
            else if(next.line_mode=="running" && config.route.Length>0 && coilEquipment[id]==config.route[config.route.Length-1] && logistics!=null) logistics.Accept(stale);
            else { stale.SetParent(null); Remove(stale.gameObject); }
            coilObjects.Remove(id); coilTargets.Remove(id); coilEquipment.Remove(id); coilWaypoints.Remove(id);
        }
        online=true; lastSuccess=Time.realtimeSinceStartup;
        status=next.line_mode+" | "+next.scenario_id+" | tick "+next.sequence;
        FactoryMonitor.RefreshFor(this,config,next,true);
        if(capture!=null) capture.SetContext(next.config_id,next.run_id,next.sequence);
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
        if(rig!=null) rig.ApplySensors(null);
        foreach(var lamp in lamps.Values) lamp.sharedMaterial=MaterialFor(FactoryRules.Grey);
        ClearCoils();
        FactoryMonitor.RefreshFor(this,config,null,false);
        if(capture!=null) capture.SetContext(config==null ? null : config.config_id,null,-1);
    }
    void ClearCoils()
    {
        if(logistics!=null) logistics.ResetLoads();
        scrapExits.Clear(); scrapSlots.Clear(); scrapCount=0;
        if(scrapRoot!=null) for(int i=scrapRoot.childCount-1;i>=0;i--) { var child=scrapRoot.GetChild(i); child.SetParent(null); Remove(child.gameObject); }
        coilObjects.Clear(); coilTargets.Clear(); coilEquipment.Clear(); coilWaypoints.Clear();
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
    bool selectionBusy;
    string pendingSelectionId;
    public void SelectEquipment(string id)
    {
        if(!online || config==null || !equipment.ContainsKey(id) || !equipment[id].activeSelf) return;
        selectedId=id; pendingSelectionId=id;
        if(!selectionBusy) StartCoroutine(SendSelection());
    }
    IEnumerator SendSelection()
    {
        selectionBusy=true;
        while(pendingSelectionId!=null && online) {
            string id=pendingSelectionId; pendingSelectionId=null;
            string json=JsonUtility.ToJson(new EquipmentSelection {equipment_id=id, config_id=config.config_id});
            using(var req=new UnityWebRequest(mesUrl+"/api/equipment/select","POST")) {
                req.uploadHandler=new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
                req.downloadHandler=new DownloadHandlerBuffer(); req.SetRequestHeader("Content-Type","application/json");
                req.timeout=5; yield return req.SendWebRequest();
                if(req.result!=UnityWebRequest.Result.Success) status="PDA selection failed (HTTP "+req.responseCode+")";
            }
        }
        pendingSelectionId=null; selectionBusy=false;
    }
    void Update()
    {
        if(online && Time.realtimeSinceStartup-lastSuccess>8) Disconnect("MES updates timed out");
        AdvanceVisuals(Time.deltaTime);
        if(worker!=null && worker.IsWorkerMode) return;
        if(viewCamera==null) return;
        if(Input.GetMouseButton(1)) { yaw+=Input.GetAxis("Mouse X")*3; pitch=Mathf.Clamp(pitch-Input.GetAxis("Mouse Y")*2,20,80); }
        distance=Mathf.Clamp(distance-Input.mouseScrollDelta.y*2,15,130);
        UpdateCamera();
        var guiPointer = new Vector2(Input.mousePosition.x, Screen.height-Input.mousePosition.y);
        bool overPanel = (GetComponent<FactoryMonitor>()?.ContainsPointer(guiPointer) == true) || (GetComponentInChildren<FactorySensorMotion>()?.ContainsPointer(guiPointer)==true) || new Rect(18,18,Mathf.Min(700,Screen.width-36),270).Contains(guiPointer) ||
            new Rect(Screen.width-460,Screen.height-150,442,132).Contains(guiPointer) ||
            (!string.IsNullOrEmpty(selectedId) && new Rect(18,Screen.height-145,Mathf.Min(560,Screen.width-36),125).Contains(guiPointer));
        if(Input.GetMouseButtonDown(0) && !overPanel) {
            RaycastHit hit;
            if(Physics.Raycast(viewCamera.ScreenPointToRay(Input.mousePosition),out hit)) {
                var node=hit.transform;
                while(node!=null) { if(equipment.ContainsKey(node.name)) { SelectEquipment(node.name); break; } node=node.parent; }
            }
        }
        if(equipmentRoot!=null) foreach(var label in equipmentRoot.GetComponentsInChildren<TextMesh>())
            label.transform.rotation=viewCamera.transform.rotation;
    }
    public void AdvanceVisuals(float seconds)
    {
        if(!online || rig==null || seconds<=0 || float.IsNaN(seconds) || float.IsInfinity(seconds)) return;
        rig.Advance(snapshot,seconds);
        if(logistics!=null) logistics.Advance(seconds,snapshot.line_mode=="running" && readings.Values.All(e=>e.fault_level!="critical"));
        foreach(var pair in coilObjects) {
            EquipmentReading state;
            if(readings.TryGetValue(coilEquipment[pair.Key],out state) && state.operating_state=="running" && state.fault_level!="critical" && snapshot.line_mode=="running") {
                if((snapshot.coils??new CoilReading[0]).Any(c=>c.coil_id==pair.Key && c.quality_status=="hold")) continue;
                Queue<LineWaypoint> path; coilWaypoints.TryGetValue(pair.Key,out path);
                AdvanceLineLoad(pair.Value,coilEquipment[pair.Key],path,coilTargets[pair.Key],seconds);
            }
        }
        foreach(var pair in scrapExits.ToArray()) {
            var exit=pair.Value; float speed;
            if(snapshot.line_mode!="running" || !CanTransport(exit.equipmentId,out speed)) continue;
            float remaining=seconds;
            while(exit.path.Count>1 && remaining>0) {
                var target=exit.path.Peek();
                remaining=AdvanceLineLoad(exit.load,exit.equipmentId,exit.transfer,target,remaining);
                if(Vector3.Distance(exit.load.position,target)>.001f) break;
                exit.path.Dequeue();
            }
            if(exit.path.Count!=1 || remaining<=0) continue;
            // The sheet/chute representation and gravity drop illustrate MES scrap discharge; no cutting operation is simulated.
            var landing=exit.path.Peek(); var before=exit.load.position;
            float drop=exit.fallSpeed*remaining+.5f*9.81f*remaining*remaining; exit.fallSpeed+=9.81f*remaining;
            float height=Mathf.Max(0,before.y-landing.y);
            exit.load.position=height<=drop ? landing : Vector3.Lerp(before,landing,drop/height);
            if(Vector3.Distance(exit.load.position,landing)<.001f) {
                foreach(var old in scrapRoot.Cast<Transform>().Where(t=>t!=exit.load && !scrapExits.Values.Any(active=>active.load==t) && Vector3.Distance(t.position,landing)<.001f).ToArray()) { old.SetParent(null); Remove(old.gameObject); }
                scrapCount++; scrapExits.Remove(pair.Key);
            }
        }
    }
    bool IsScrapEquipment(string id)
    {
        return config.equipment.Any(e=>e.equipment_id==id && e.code=="CV-02") && (config.branches??new BranchSpec[0]).Any(b=>b.to_id==id);
    }
    bool CanTransport(string id,out float speed)
    {
        speed=FactoryRig.TransportSpeed(snapshot,id); EquipmentReading state;
        return speed>0 && readings.TryGetValue(id,out state) && state.operating_state=="running" && state.fault_level!="critical";
    }
    float AdvanceLineLoad(Transform load,string owner,Queue<LineWaypoint> path,Vector3 target,float seconds)
    {
        float ownerSpeed;
        if(!CanTransport(owner,out ownerSpeed)) return seconds;
        while(seconds>0) {
            var point=path!=null && path.Count>0 ? path.Peek() : null;
            var destination=point==null ? target : point.position;
            float speed=ownerSpeed;
            if(point!=null) { float sourceSpeed,arrivalSpeed; if(!CanTransport(point.from,out sourceSpeed) || !CanTransport(point.to,out arrivalSpeed)) return seconds; speed=Mathf.Min(speed,Mathf.Min(sourceSpeed,arrivalSpeed)); }
            float distance=Vector3.Distance(load.position,destination);
            if(distance>speed*seconds) { load.position=Vector3.MoveTowards(load.position,destination,speed*seconds); return 0; }
            load.position=destination; seconds-=distance/speed;
            if(point==null) return seconds;
            path.Dequeue();
        }
        return 0;
    }
    void UpdateCamera()
    {
        if(worker!=null && worker.IsWorkerMode) return;
        if(viewCamera==null) return;
        viewCamera.transform.position=target+Quaternion.Euler(pitch,yaw,0)*new Vector3(0,0,-distance);
        viewCamera.transform.LookAt(target);
    }
    void OnGUI()
    {
        if(worker!=null && worker.IsWorkerMode) return;
        GUI.backgroundColor=new Color(.07f,.12f,.19f,.96f);
        GUILayout.BeginArea(new Rect(18,18,Mathf.Min(700,Screen.width-36),270),GUI.skin.box);
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
        if(GUILayout.Button(exteriorView ? "View factory interior" : "View factory exterior")) SetExteriorView(!exteriorView);
        if(worker!=null && GUILayout.Button("Walk as employee / PDA camera [F]")) worker.EnterWorker();
        if (GUILayout.Button("Open MES dashboard / fault scenarios")) Application.OpenURL(mesUrl.TrimEnd('/')+"/");
        GUILayout.EndArea();
        if(logistics!=null) {
            GUILayout.BeginArea(new Rect(Screen.width-460,Screen.height-150,442,132),GUI.skin.box);
            GUILayout.Label(logistics.Summary);
            GUI.enabled=online;
            logistics.SendToTruck=GUILayout.Toggle(logistics.SendToTruck,"Send next finished coils to truck (otherwise warehouse)");
            GUILayout.BeginHorizontal();
            if(GUILayout.Button("Load stored coils")) logistics.DispatchStored();
            if(GUILayout.Button("Dispatch loaded truck")) logistics.DepartTruck();
            GUILayout.EndHorizontal(); GUI.enabled=true;
            GUILayout.Label("Virtual finishing speed 2 m/s / session inventory");
            GUILayout.EndArea();
        }
        if(!string.IsNullOrEmpty(selectedId) && equipment.ContainsKey(selectedId)) {
            GUILayout.BeginArea(new Rect(18,Screen.height-145,Mathf.Min(560,Screen.width-36),125),GUI.skin.box);
            GUILayout.Label("Selected: "+selectedId+" | Latest PDA scan: "+(lastScanId ?? "none"));
            EquipmentReading reading; if(readings.TryGetValue(selectedId,out reading)) GUILayout.Label(reading.operating_state+" / "+reading.fault_level);
            if(IsScrapEquipment(selectedId)) GUILayout.Label("스크랩 배출 중 "+DischargingScrapCount+"개 / 누적 "+ScrapCount+"개 · 적치 형상은 최대 20층 시연입니다. 판재는 실제 절단을 재현하지 않습니다.",new GUIStyle(GUI.skin.label) {wordWrap=true});
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
    void OnDestroy() { foreach(var mat in materials.Values) Remove(mat); foreach(var mesh in buildingMeshes) Remove(mesh); }
}
