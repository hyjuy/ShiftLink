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
    static string output;
    static int equipmentIndex, index, retries, perEquipment, saved;
    static int seed=20261007;
    static string Argument(string key,string fallback)
    {
        var args=Environment.GetCommandLineArgs(); int i=Array.IndexOf(args,key);
        return i>=0 && i+1<args.Length ? args[i+1] : fallback;
    }
    public static void Run()
    {
        try {
            perEquipment=int.Parse(Argument("--photos-per-equipment","600"));
            if(perEquipment<1 || (perEquipment!=1 && perEquipment%60!=0)) throw new Exception("Photo count must be 1 (smoke) or a multiple of 60");
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
            demo.CreateEnvironment(); demo.Build(config); demo.SetExteriorView(false); demo.Apply(state);
            nodes=demo.transform.Find("MES equipment"); camera=Camera.main;
            capture=demo.GetComponent<FactoryCapture>();
            capture.width=1280; capture.height=720; capture.outputDirectory=output;
            capture.Configure(camera,config,config.equipment.ToDictionary(e=>e.equipment_id,e=>nodes.Find(e.equipment_id).gameObject),seed);
            sun=UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None).First(l=>l.type==LightType.Directional);
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
            int sector=perEquipment==1 ? 0 : index/(perEquipment/60);
            string split=sector%10==8 ? "val" : sector%10==9 ? "test" : "train";
            string name=spec.equipment_id+"_"+index.ToString("0000");
            string directory=Path.Combine(output,spec.code,split); Directory.CreateDirectory(directory);
            string png=Path.Combine(directory,name+".png");
            if(File.Exists(png) && File.Exists(Path.ChangeExtension(png,".json"))) { Next(); return; }
            var random=new System.Random(seed+Array.IndexOf(config.equipment,spec)*100000+index*101+retries);
            Func<float,float,float> range=(a,b)=>a+(b-a)*(float)random.NextDouble();
            var target=nodes.Find(spec.equipment_id);
            var renderers=target.GetComponentsInChildren<Renderer>().Where(r=>!(r is MeshRenderer && r.GetComponent<TextMesh>()!=null)).ToArray();
            var bounds=renderers[0].bounds; foreach(var r in renderers.Skip(1)) bounds.Encapsulate(r.bounds);
            float azimuth=(sector*6+range(.4f,5.6f))*Mathf.Deg2Rad;
            // Entire azimuth sectors are held out; retries keep the same sector/split.
            float elevation=range(5,38)*Mathf.Deg2Rad;
            float distance=Mathf.Max(bounds.extents.magnitude*range(2.25f,3.2f),3.1f);
            camera.fieldOfView=range(43,57); camera.nearClipPlane=.08f; camera.aspect=1280f/720;
            Vector3 aim=bounds.center+new Vector3(range(-.12f,.12f),range(-.08f,.08f),range(-.12f,.12f));
            camera.transform.position=aim+distance*new Vector3(Mathf.Cos(azimuth)*Mathf.Cos(elevation),Mathf.Sin(elevation),Mathf.Sin(azimuth)*Mathf.Cos(elevation));
            camera.transform.LookAt(aim); camera.transform.Rotate(Vector3.forward,range(-3,3),Space.Self);
            sun.intensity=range(.85f,1.55f); sun.transform.rotation=Quaternion.Euler(range(35,65),range(-160,160),0);
            RenderSettings.ambientLight=Color.Lerp(new Color(.22f,.25f,.3f),new Color(.46f,.48f,.5f),range(0,1));
            bool running=index%5!=0;
            state.line_mode=running ? "running" : "paused";
            foreach(var e in state.equipment) { e.operating_state=running ? "running" : "waiting"; e.fault_level="normal"; }
            demo.Apply(state); demo.AdvanceVisuals(range(.05f,.6f));
            capture.sceneId="factory-"+spec.code+"-sector-"+sector.ToString("00");
            capture.sessionId=capture.sceneId; capture.outputDirectory=directory;
            if(!capture.Capture()) throw new Exception(capture.Status);
            var annotation=capture.PreviewMetadata.objects.FirstOrDefault(o=>o.equipment_id==spec.equipment_id);
            var box=annotation==null ? null : annotation.bbox_xyxy;
            // Reject tiny or clipped targets instead of saving empty shots.
            if(box==null || (box[2]-box[0])*(box[3]-box[1])<1280*720*.035f || box[0]<4 || box[1]<4 || box[2]>1276 || box[3]>716) {
                capture.Retake(); retries++; if(retries>80) throw new Exception("Cannot frame "+name); return;
            }
            capture.PreviewMetadata.capture_id=name; capture.PreviewMetadata.dataset_split=split;
            capture.PreviewMetadata.target_equipment_id=spec.equipment_id;
            if(!capture.Save()) throw new Exception(capture.Status);
            capture.Retake(); Next();
        } catch(Exception error) { Fail(error); }
    }
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
