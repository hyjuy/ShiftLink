using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Uses the same RGB/visible-instance-mask capture path as the employee PDA.
public static class FactoryDatasetCapture
{
    static FactoryDemo demo;
    static FactoryCapture capture;
    static FactoryConfig config;
    static EquipmentSpec[] targets;
    static MesSnapshot state;
    static Transform nodes;
    static Camera camera;
    static Light sun;
    static Light[] interiorLights;
    static Bounds[] obstacles;
    static float groundFloor;
    static string output;
    static int equipmentIndex, index, retries, perEquipment, saved;
    static int seed=20261008;
    static string Argument(string key,string fallback)
    {
        var args=Environment.GetCommandLineArgs(); int i=Array.IndexOf(args,key);
        return i>=0 && i+1<args.Length ? args[i+1] : fallback;
    }
    public static void Run()
    {
        try {
            perEquipment=int.Parse(Argument("--photos-per-equipment","360"));
            if(perEquipment!=24 && perEquipment!=360) throw new Exception("Photo count must be 24 (direction/detail smoke) or 360 (additional photographs)");
            output=Path.GetFullPath(Argument("--capture-output",Path.Combine(Application.dataPath,"../Captures")));
            Directory.CreateDirectory(output);
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string checks=Path.Combine(Application.dataPath,"../Checks");
            config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(checks,"config.json"))).config;
            state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(checks,"state.json")));
            config.equipment=config.equipment.Where(e=>e.active).ToArray();
            var codes=Argument("--equipment-codes","").Split(new[]{','},StringSplitOptions.RemoveEmptyEntries);
            targets=config.equipment.Where(e=>codes.Length==0 || codes.Contains(e.code)).ToArray();
            if(targets.Length==0 || (codes.Length>0 && targets.Length!=codes.Length)) throw new Exception("Unknown or repeated equipment code");
            demo=new GameObject("Dataset factory").AddComponent<FactoryDemo>();
            demo.CreateEnvironment();
            // Enlarge the photography hall and walking gaps, preserving equipment dimensions.
            FactoryRig.LayoutSpacing=1.5f;
            foreach(Transform child in demo.transform)
                if(child.name=="Factory floor" || child.name=="Factory apron" || child.name=="Floor grid" || child.name=="Factory building" || child.name=="Employee building collisions" || child.name=="Virtual process campus")
                    child.localScale=Vector3.Scale(child.localScale,new Vector3(1.5f,1,1.5f));
            demo.Build(config); demo.SetExteriorView(true); demo.Apply(state);
            groundFloor=demo.transform.Find("Factory floor").GetComponent<Renderer>().bounds.max.y;
            nodes=demo.transform.Find("MES equipment"); camera=Camera.main;
            foreach(var name in new[]{"CAU utility platform","CAU stair landing"}) {
                var deck=nodes.Find(name);
                if(deck!=null) deck.gameObject.AddComponent<BoxCollider>();
            }
            // Imported connections also occupy walking space, beyond equipment root colliders.
            foreach(var renderer in nodes.GetComponentsInChildren<MeshRenderer>()) {
                if(renderer.GetComponent<TextMesh>()!=null || renderer.GetComponentInParent<Collider>()!=null || renderer.bounds.size.y<.1f) continue;
                var mesh=renderer.GetComponent<MeshFilter>();
                if(mesh==null || mesh.sharedMesh==null) continue;
                var collider=renderer.gameObject.AddComponent<BoxCollider>();
                collider.center=mesh.sharedMesh.bounds.center; collider.size=mesh.sharedMesh.bounds.size;
            }
            capture=demo.GetComponent<FactoryCapture>();
            capture.width=1280; capture.height=720; capture.outputDirectory=output;
            capture.Configure(camera,config,config.equipment.ToDictionary(e=>e.equipment_id,e=>nodes.Find(e.equipment_id).gameObject),seed);
            sun=UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).First(l=>l.type==LightType.Directional);
            interiorLights=UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).Where(l=>l.name=="Interior LED light").ToArray();
            obstacles=config.equipment.Select(e=>EquipmentBounds(nodes.Find(e.equipment_id))).ToArray();
            Physics.SyncTransforms();
            EditorApplication.update+=Step;
        } catch(Exception error) { Fail(error); }
    }
    static void Step()
    {
        try {
            if(equipmentIndex>=targets.Length) {
                File.WriteAllText(Path.Combine(output,"../capture-result.txt"),"PASS: "+saved+" photos; "+perEquipment+" per equipment; RGB and visible-instance-mask labels");
                EditorApplication.update-=Step; EditorApplication.Exit(0); return;
            }
            var spec=targets[equipmentIndex];
            int slots=perEquipment/12, sector=index/slots, slot=index%slots;
            string split=perEquipment==24 || slot<24 ? "train" : slot<27 ? "val" : "test";
            bool detail=perEquipment==24 ? slot==1 : !(slot<4 || slot==(sector%2==0 ? 24 : 27));
            string name=spec.equipment_id+"_extra_"+index.ToString("0000");
            string directory=Path.Combine(output,spec.code,split); Directory.CreateDirectory(directory);
            string png=Path.Combine(directory,name+".png");
            if(File.Exists(png) && File.Exists(Path.ChangeExtension(png,".json"))) { Next(); return; }
            var random=new System.Random(seed+Array.IndexOf(config.equipment,spec)*100000+index*101+retries);
            Func<float,float,float> range=(a,b)=>a+(b-a)*(float)random.NextDouble();
            var target=nodes.Find(spec.equipment_id);
            var bounds=EquipmentBounds(target);
            float floor=spec.code=="CAU-01" ? target.position.y : groundFloor;
            float degrees=sector*30+(split=="val" ? range(18.2f,21.8f) : split=="test" ? range(24.2f,27.8f) : range(1,18));
            // Narrow held-out angles can face a physical connection; stay in the direction sector,
            // but prioritize an accessible, identifiable photograph over forcing a blocked pose.
            if(retries>=250) degrees=sector*30+range(1,29);
            float azimuth=degrees*Mathf.Deg2Rad;
            float edge=Mathf.Min(bounds.extents.x/Mathf.Max(.001f,Mathf.Abs(Mathf.Cos(azimuth))),bounds.extents.z/Mathf.Max(.001f,Mathf.Abs(Mathf.Sin(azimuth))));
            float distance=detail ? edge+range(.8f,3.5f) : Mathf.Max(new Vector2(bounds.extents.x,bounds.extents.z).magnitude*range(1.6f,3.1f),2.4f);
            camera.fieldOfView=detail ? range(30,55) : range(48,65); camera.nearClipPlane=.08f; camera.aspect=1280f/720;
            Vector3 aim=bounds.center+new Vector3(range(-.25f,.25f),range(-.15f,.15f),range(-.25f,.25f));
            // Lens height is independent of equipment size: chest to eye level, never an orbit above it.
            camera.transform.position=new Vector3(bounds.center.x+distance*Mathf.Cos(azimuth),floor+range(1.2f,1.8f),bounds.center.z+distance*Mathf.Sin(azimuth));
            Renderer feature=null;
            if(detail) {
                string[] names=spec.code.StartsWith("CAU") ? new[]{"ControlDisplay","IntakeLouvre","SideServicePanel","ExhaustDuct","CabinetDoor","Fan"} :
                    spec.code.StartsWith("HPU") ? new[]{"Accumulator","ValveManifold","TankInspectionFlange","PumpPressureHose","Motor"} :
                    spec.code.StartsWith("PDP") ? new[]{"MainIncomerPanel","FeederPanel","CableOutlet","CabinetSidePanel","DoorHandle"} :
                    spec.code.StartsWith("GR") ? new[]{"GearInspectionCover","OutputShaft","Motor","SplitHousingSeam"} :
                    spec.code.StartsWith("RT") ? new[]{"Roller","BearingCover","ChainGuard","ChannelFlange","Clamp"} :
                    new[]{"BeltTop","SteelBelt","HingedSlat","DischargeChute","ChuteSideCheek","ReturnIdler","HeadDrum","TakeupAdjuster","ScrapBearingCap","ScrapBearingBlock","ScrapChainGuard","DrumBearingCover"};
                feature=target.GetComponentsInChildren<Renderer>().Where(r=>names.Any(n=>r.name.StartsWith(n)))
                    .OrderBy(r=>Vector3.Distance(camera.transform.position,r.bounds.center))
                    .FirstOrDefault(r=>FeatureUnblocked(r,target));
                if(feature==null) { Retry(name); return; }
                aim=feature.bounds.center;
            }
            if(!ClearStandpoint(camera.transform.position,floor)) {
                if(index==0 && retries==0) {
                    var lens=camera.transform.position;
                    Debug.Log("Rejected standpoint "+spec.code+" at "+lens+"; colliders "+string.Join(",",Physics.OverlapCapsule(new Vector3(lens.x,floor+.35f,lens.z),new Vector3(lens.x,floor+1.65f,lens.z),.28f).Select(c=>c.name)));
                }
                Retry(name); return;
            }
            camera.transform.LookAt(aim); camera.transform.Rotate(Vector3.forward,range(-3,3),Space.Self);
            int lighting=(index+equipmentIndex+sector)%5;
            string profile=new[]{"dim","normal","bright","warm","cool"}[lighting];
            float level=new[]{.35f,1f,1.6f,.8f,.8f}[lighting]*range(.85f,1.15f);
            Color tint=lighting==3 ? new Color(1,.77f,.53f) : lighting==4 ? new Color(.65f,.82f,1) : new Color(.9f,.94f,1);
            sun.intensity=level; sun.color=tint;
            sun.transform.rotation=Quaternion.Euler(range(25,70),range(-180,180),0);
            foreach(var light in interiorLights) { light.intensity=2*level; light.color=tint; }
            RenderSettings.ambientLight=tint*(.28f*level);
            bool running=index%7!=0;
            state.line_mode=running ? "running" : "paused";
            foreach(var e in state.equipment) { e.operating_state=running ? "running" : "waiting"; e.fault_level="normal"; }
            demo.Apply(state); demo.AdvanceVisuals(range(.05f,.6f));
            capture.sceneId="factory-extra-"+spec.code+"-sector-"+sector.ToString("00")+"-"+split;
            capture.sessionId=capture.sceneId; capture.outputDirectory=directory;
            if(!capture.Capture()) throw new Exception(capture.Status);
            var annotation=capture.PreviewMetadata.objects.FirstOrDefault(o=>o.equipment_id==spec.equipment_id);
            var box=annotation==null ? null : annotation.bbox_xyxy;
            // Reject tiny or clipped targets instead of saving empty shots.
            bool featureVisible=!detail || FeatureVisible(feature,target);
            if(box==null || (box[2]-box[0])*(box[3]-box[1])<1280*720*(detail ? .12f : .035f) ||
                (!detail && (box[0]<4 || box[1]<4 || box[2]>1276 || box[3]>716)) || !featureVisible) {
                if(retries==0) {
                    string rejected=Path.Combine(output,"../rejected-"+spec.code);
                    File.WriteAllBytes(rejected+".png",capture.Preview.EncodeToPNG());
                    File.WriteAllText(rejected+".json",JsonUtility.ToJson(capture.PreviewMetadata,true));
                    Debug.Log("Rejected framing "+spec.code+" bounds "+bounds+"; box "+(box==null ? "absent" : string.Join(",",box)));
                }
                capture.Retake(); Retry(name); return;
            }
            capture.PreviewMetadata.capture_id=name; capture.PreviewMetadata.dataset_split=split;
            capture.PreviewMetadata.target_equipment_id=spec.equipment_id;
            capture.PreviewMetadata.viewpoint="handheld-first-person";
            capture.PreviewMetadata.standpoint_clear=true;
            capture.PreviewMetadata.standing_floor_y=floor;
            capture.PreviewMetadata.lighting_profile=profile;
            capture.PreviewMetadata.sun_intensity=sun.intensity;
            capture.PreviewMetadata.interior_light_intensity=2*level;
            var ambient=RenderSettings.ambientLight;
            capture.PreviewMetadata.ambient_rgb=new[]{ambient.r,ambient.g,ambient.b};
            capture.PreviewMetadata.shot_kind=detail ? "detail" : "whole";
            capture.PreviewMetadata.direction_sector=sector;
            capture.PreviewMetadata.azimuth_degrees=degrees;
            capture.PreviewMetadata.target_center=new[]{bounds.center.x,bounds.center.y,bounds.center.z};
            capture.PreviewMetadata.feature_name=detail ? feature.name : "";
            capture.PreviewMetadata.feature_visible=detail && featureVisible;
            capture.PreviewMetadata.angle_range_relaxed=retries>=250;
            capture.PreviewMetadata.feature_aim=new[]{aim.x,aim.y,aim.z};
            if(!capture.Save()) throw new Exception(capture.Status);
            capture.Retake(); Next();
        } catch(Exception error) { Fail(error); }
    }
    static Bounds EquipmentBounds(Transform root)
    {
        var renderers=root.GetComponentsInChildren<Renderer>().Where(r=>r.GetComponent<TextMesh>()==null).ToArray();
        var bounds=renderers[0].bounds; foreach(var renderer in renderers.Skip(1)) bounds.Encapsulate(renderer.bounds);
        return bounds;
    }
    static bool FeatureVisible(Renderer feature,Transform target)
    {
        var point=feature.bounds.center;
        var viewport=camera.WorldToViewportPoint(point);
        if(viewport.z<=0 || viewport.x<.1f || viewport.x>.9f || viewport.y<.1f || viewport.y>.9f) return false;
        return FeatureUnblocked(feature,target);
    }
    static bool FeatureUnblocked(Renderer feature,Transform target)
    {
        var point=feature.bounds.center;
        // Raycast component meshes directly: equipment root boxes enclose hollow details.
        var ray=new Ray(camera.transform.position,(point-camera.transform.position).normalized);
        float distance=Vector3.Distance(camera.transform.position,point);
        foreach(var renderer in target.GetComponentsInChildren<MeshRenderer>()) {
            if(renderer==feature) continue;
            var mesh=renderer.GetComponent<MeshFilter>();
            if(mesh==null || mesh.sharedMesh==null) continue;
            if(!renderer.bounds.IntersectRay(ray,out float enter) || enter>=distance-.12f) continue;
            var collider=renderer.GetComponent<MeshCollider>();
            if(collider==null) { collider=renderer.gameObject.AddComponent<MeshCollider>(); collider.sharedMesh=mesh.sharedMesh; }
            if(collider.Raycast(ray,out RaycastHit hit,distance-.12f)) return false;
        }
        return true;
    }
    static bool ClearStandpoint(Vector3 lens,float floor)
    {
        if(Mathf.Abs(lens.x)>32 || Mathf.Abs(lens.z)>24.5f) return false;
        if(!Physics.Raycast(new Vector3(lens.x,floor+.2f,lens.z),Vector3.down,.5f,~0,QueryTriggerInteraction.Ignore)) return false;
        var body=new Bounds(new Vector3(lens.x,floor+.95f,lens.z),new Vector3(.6f,1.8f,.6f));
        if(obstacles.Any(bounds=>bounds.Intersects(body))) return false;
        return !Physics.CheckCapsule(new Vector3(lens.x,floor+.35f,lens.z),new Vector3(lens.x,floor+1.65f,lens.z),.28f,~0,QueryTriggerInteraction.Ignore);
    }
    static void Retry(string name)
    { retries++; if(retries>500) throw new Exception("Cannot frame accessible handheld photo "+name); }
    static void Next()
    {
        saved++; index++; retries=0;
        if(index==perEquipment) { index=0; equipmentIndex++; }
        if(saved%20==0 || index==0) {
            string progress=saved+" / "+(targets.Length*perEquipment);
            File.WriteAllText(Path.Combine(output,"../capture-progress.txt"),progress);
            Debug.Log("DATASET CAPTURE "+progress);
        }
    }
    static void Fail(Exception error) { EditorApplication.update-=Step; Debug.LogException(error); EditorApplication.Exit(1); }
}
