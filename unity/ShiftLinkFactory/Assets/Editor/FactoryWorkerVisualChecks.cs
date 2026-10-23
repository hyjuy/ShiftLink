using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Reflection keeps the pre-implementation RED runnable without a compile failure.
[InitializeOnLoad]
public static class FactoryWorkerVisualChecks
{
    static FactoryWorker playWorker;
    static Camera reviewCamera;
    static int stage, stageFrame, lastFrame;
    static readonly string[] stageNames={"idle","walking","running","jumping","photographing"};
    static FactoryWorkerVisualChecks()
    { if(SessionState.GetBool("ShiftLink.ChibiPlay",false))EditorApplication.update+=PlayTick; }
    static int checks;
    static string dir;
    static void Check(bool value, string label)
    { if (!value) throw new Exception(label); checks++; Debug.Log("PASS: " + label); }
    static object Get(object value, string name) { return value.GetType().GetProperty(name).GetValue(value); }
    static object Call(object value, string name, params object[] args)
    {
        try { return value.GetType().GetMethod(name).Invoke(value, args); }
        catch (TargetInvocationException error) { throw error.InnerException ?? error; }
    }
    static Transform Bone(Transform root, string name)
    { return root.GetComponentsInChildren<Transform>(true).Single(t => t.name == name); }
    static void Advance(Component visual, float dt, float speed, bool grounded, float vertical, bool photo)
    { Call(visual, "Advance", dt, speed, grounded, vertical, photo); }
    static void State(Component visual, string state)
    { Check(Get(visual, "CurrentState").ToString() == state, "visual state: " + state); }
    public static void Run()
    {
        dir = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../artifacts/unity-chibi-worker-20261023"));
        Directory.CreateDirectory(dir);
        try {
            var assembly = typeof(FactoryWorker).Assembly;
            var visualType = assembly.GetType("FactoryWorkerVisual");
            Check(visualType != null, "rigged worker visual component exists");
            var builder = typeof(FactoryWorkerVisualChecks).Assembly.GetType("FactoryWorkerAssetBuilder");
            Check(builder != null, "worker FBX prefab builder exists");
            builder.GetMethod("Prepare").Invoke(null, null);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.transform.position = new Vector3(0, -.5f, 0); floor.transform.localScale = new Vector3(100, 1, 100);
            floor.GetComponent<Renderer>().sharedMaterial=new Material(Shader.Find("Standard")){color=new Color(.18f,.21f,.25f)};
            var observation = new GameObject("Observation").AddComponent<Camera>(); observation.enabled = false;
            var host = new GameObject("Chibi integration checks");
            var worker = host.AddComponent<FactoryWorker>(); worker.Initialize(null, observation);
            var root = worker.WorkerRoot; var controller = root.GetComponent<CharacterController>();
            controller.enabled = false; root.position = new Vector3(0, .05f, 0); controller.enabled = true;
            var visual = root.GetComponentInChildren(visualType) as Component;
            Check(visual != null, "worker uses the male chibi prefab");
            var skin = root.GetComponentsInChildren<SkinnedMeshRenderer>(true).Single();
            Check(skin.name.Contains("Male") && skin.bones.Length >= 18, "male skinned mesh and actual FBX bones loaded");
            Check(root.GetComponentsInChildren<Renderer>(true).Length == 2, "one skinned body and one PDA replace primitive shapes");
            var toes = Bone(root, "LeftToes"); var foot = Bone(root, "LeftFoot");
            Check(Vector3.Dot((toes.position-foot.position).normalized, root.forward) > .6f, "imported worker faces controller forward");
            Check(skin.bounds.size.y > 1.6f && skin.bounds.size.y < 1.85f, "imported worker uses metre scale");
            Check(skin.sharedMaterials.All(m => m != null && m.shader.name == "ShiftLink/WorkerToon"), "worker palette and outline shader assigned");
            var tabletRoot=(Transform)Get(visual,"Pda");
            var tabletRenderer=tabletRoot.GetComponentInChildren<Renderer>();
            var tabletAsset=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/Models/Characters/ChibiWorkers_v2/ChibiWorker_PDA.fbx");
            Debug.Log("PDA imported root rotation="+tabletAsset.transform.localEulerAngles+" generated root rotation="+tabletRoot.GetChild(0).localEulerAngles+" size="+tabletRenderer.bounds.size);
            Check(tabletRenderer.bounds.size.y>.22f&&tabletRenderer.bounds.size.y<.26f&&tabletRenderer.bounds.size.x<.21f&&tabletRenderer.bounds.size.z<.10f,"PDA is upright, hand sized and thin");
            var leftArm = Bone(root, "LeftUpperArm"); var hand = Bone(root, "LeftHand");
            Advance(visual, 0, 0, true, 0, false); State(visual, "Idle");
            Check(hand.position.y < leftArm.position.y - .12f, "idle lowers arms from T pose");
            var bakedIdle = new Mesh(); skin.BakeMesh(bakedIdle);
            var idleArm = leftArm.localRotation;
            var idleKnee=Bone(root,"LeftLowerLeg").localRotation;
            Advance(visual, .15f, 2.2f, true, 0, false); State(visual, "Walking");
            var bakedWalk = new Mesh(); skin.BakeMesh(bakedWalk);
            var idleVertices=bakedIdle.vertices; var walkVertices=bakedWalk.vertices;
            Check(walkVertices.Where((v,i) => (v-idleVertices[i]).sqrMagnitude > .00001f).Count() > 100, "walking deforms the imported skin");
            Check(Quaternion.Angle(leftArm.localRotation, idleArm) > 2, "walking swings free arm");
            Shot(root, "walking.png");
            Advance(visual, .15f, 4.4f, true, 0, false); State(visual, "Running"); Shot(root, "running.png");
            Advance(visual, .15f, 0, false, 3, false); State(visual, "Jumping");
            Check(Quaternion.Angle(Bone(root,"LeftLowerLeg").localRotation, idleKnee) > 3, "jump bends knees"); Shot(root, "jumping.png");
            Advance(visual, .15f, 0, false, -3, false); State(visual, "Jumping");
            Advance(visual, .3f, 0, true, 0, false); State(visual, "Idle"); Shot(root, "idle.png");
            var beforeInvalid = leftArm.localRotation;
            Advance(visual, float.NaN, 2, true, 0, false);
            Check(Quaternion.Angle(beforeInvalid, leftArm.localRotation) < .001f, "invalid animation timestep rejected");
            worker.EnterWorker(); Physics.SyncTransforms();
            for (int i=0;i<60;i++) worker.Step(1f/60, Vector2.zero, Vector2.zero);
            Check(controller.isGrounded, "new model settles using existing character controller");
            var start = root.position;
            for (int i=0;i<30;i++) worker.Step(1f/60, Vector2.up, Vector2.zero);
            float walk = root.position.z-start.z; State(visual,"Walking");
            start = root.position;
            for (int i=0;i<30;i++) worker.StepMovement(1f/60, Vector2.up, Vector2.zero, true, false);
            Check(root.position.z-start.z > walk*1.5f, "running changes real controller speed"); State(visual,"Running");
            float ground=root.position.y; worker.StepMovement(1f/60,Vector2.zero,Vector2.zero,false,true);
            Check(root.position.y>ground+.02f,"jump moves the controller upward"); State(visual,"Jumping");
            for(int i=0;i<150;i++)worker.Step(1f/60,Vector2.zero,Vector2.zero);
            Check(controller.isGrounded,"jump lands on floor"); State(visual,"Idle");
            Check(!(bool)Call(worker,"TakePhoto"),"photo input requires PDA mode");
            worker.TogglePda(); Advance(visual,.3f,0,true,0,true); State(visual,"Photographing");
            Call(worker,"SetThirdPerson",true);
            Check(skin.enabled,"third person shows the photographing pose");
            var lens=(Transform)Get(visual,"PhotoLens");
            Check(Vector3.Distance(lens.position,worker.PdaCamera.transform.position)<.08f,"photo camera follows the PDA rear lens");
            Check(Vector3.Dot(worker.PdaCamera.transform.forward,root.forward)>.99f,"rear camera faces away from worker");
            start=root.position; worker.StepMovement(.2f,Vector2.up,Vector2.one,true,true);
            Check(Vector3.Distance(start,root.position)<.001f,"PDA still blocks movement and jump input");
            var capture=host.GetComponent<FactoryCapture>(); capture.width=320; capture.height=240; capture.outputDirectory=Path.Combine(dir,"captures");
            capture.Configure(worker.PdaCamera,null,null);
            Check((bool)Call(worker,"TakePhoto")&&capture.HasPreview,"photographing captures an actual image");
            Check((bool)Get(visual,"IsShutterActive"),"successful capture triggers shutter gesture");
            Check(capture.Save()&&File.Exists(capture.LastSavedPath),"new worker keeps PNG and metadata saving");
            Shot(root,"photographing.png");
            Advance(visual,.3f,0,true,0,true);
            Check(!(bool)Get(visual,"IsShutterActive"),"shutter gesture returns to holding pose");
            worker.TogglePda(); State(visual,"Idle");
            Call(worker,"SetThirdPerson",false); Check(!skin.enabled,"first person hides own face and helmet");
            worker.ExitWorker(); Check(skin.enabled&&observation.enabled,"exit restores observation and visible model");
            var remote=UnityEngine.Object.Instantiate(root.Find("Employee visual"));
            Check(remote.GetComponentsInChildren<SkinnedMeshRenderer>().Single().bones.All(b=>b.IsChildOf(remote)),"cloning remote visual keeps independent bones");
            UnityEngine.Object.DestroyImmediate(remote.gameObject);
            UnityEngine.Object.DestroyImmediate(bakedIdle); UnityEngine.Object.DestroyImmediate(bakedWalk);
            File.WriteAllText(Path.Combine(dir,"checks.txt"),"PASS: "+checks+" imported worker, pose, movement, camera and capture checks");
            Debug.Log("CHIBI_WORKER_CHECKS_PASS: "+checks);
            if(Array.IndexOf(Environment.GetCommandLineArgs(),"--chibi-play")>=0){RunPlay();return;}
            EditorApplication.Exit(0);
        }catch(Exception error){File.WriteAllText(Path.Combine(dir,"checks.txt"),"FAIL: "+error); Debug.LogException(error); EditorApplication.Exit(1);}
    }
    static void Shot(Transform root,string name)
    {
        var camera=new GameObject("Worker review camera").AddComponent<Camera>(); camera.enabled=false;
        camera.transform.position=root.position+new Vector3(2.5f,1.6f,3.3f); camera.transform.LookAt(root.position+Vector3.up*.9f);
        camera.orthographic=true; camera.orthographicSize=1.05f;
        camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=new Color(.12f,.15f,.19f);
        var light=new GameObject("Worker review light").AddComponent<Light>(); light.type=LightType.Directional; light.intensity=.8f; light.transform.rotation=Quaternion.Euler(40,-140,0);
        var renderers=root.GetComponentsInChildren<Renderer>(true); var enabled=renderers.Select(r=>r.enabled).ToArray();
        foreach(var renderer in renderers)renderer.enabled=true;
        // Bake each review pose because editor executeMethod has no intervening skinning frame.
        var temporary=new System.Collections.Generic.List<GameObject>();
        var meshes=new System.Collections.Generic.List<Mesh>();
        foreach(var skin in root.GetComponentsInChildren<SkinnedMeshRenderer>()){
            var baked=new Mesh(); skin.BakeMesh(baked); meshes.Add(baked);
            var review=new GameObject("Baked pose review"); review.transform.SetParent(skin.transform,false);
            review.AddComponent<MeshFilter>().sharedMesh=baked; review.AddComponent<MeshRenderer>().sharedMaterials=skin.sharedMaterials;
            temporary.Add(review); skin.enabled=false;
        }
        var target=new RenderTexture(900,900,24); camera.targetTexture=target; var previous=RenderTexture.active;
        camera.Render(); RenderTexture.active=target; var pixels=new Texture2D(900,900,TextureFormat.RGB24,false);
        pixels.ReadPixels(new Rect(0,0,900,900),0,0); pixels.Apply(); File.WriteAllBytes(Path.Combine(dir,name),pixels.EncodeToPNG());
        foreach(var item in temporary)UnityEngine.Object.DestroyImmediate(item);
        foreach(var item in meshes)UnityEngine.Object.DestroyImmediate(item);
        for(int i=0;i<renderers.Length;i++)renderers[i].enabled=enabled[i];
        RenderTexture.active=previous; camera.targetTexture=null; target.Release();
        UnityEngine.Object.DestroyImmediate(target); UnityEngine.Object.DestroyImmediate(pixels); UnityEngine.Object.DestroyImmediate(camera.gameObject); UnityEngine.Object.DestroyImmediate(light.gameObject);
    }

    public static void RunPlay()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        SessionState.SetBool("ShiftLink.ChibiPlay",true);
        SessionState.SetFloat("ShiftLink.ChibiPlayStart",(float)EditorApplication.timeSinceStartup);
        EditorApplication.update+=PlayTick; EditorApplication.EnterPlaymode();
    }
    static void SavePlayFrame(Camera camera,string path)
    {
        // Batch Mode has no Game View backbuffer; render the real play camera explicitly.
        var render=new RenderTexture(900,900,24);var previous=RenderTexture.active;var previousTarget=camera.targetTexture;
        camera.targetTexture=render;camera.Render();RenderTexture.active=render;
        var pixels=new Texture2D(900,900,TextureFormat.RGB24,false);pixels.ReadPixels(new Rect(0,0,900,900),0,0);pixels.Apply();
        File.WriteAllBytes(path,pixels.EncodeToPNG());camera.targetTexture=previousTarget;RenderTexture.active=previous;render.Release();
        UnityEngine.Object.Destroy(render);UnityEngine.Object.Destroy(pixels);
    }
    static void PlayTick()
    {
        if(!SessionState.GetBool("ShiftLink.ChibiPlay",false))return;
        try{
            if(EditorApplication.timeSinceStartup-SessionState.GetFloat("ShiftLink.ChibiPlayStart",0)>120)throw new Exception("Chibi Play Mode check timed out");
            if(!Application.isPlaying||lastFrame==Time.frameCount)return;
            lastFrame=Time.frameCount;
            if(playWorker==null){
                dir=Path.GetFullPath(Path.Combine(Application.dataPath,"../../../artifacts/unity-chibi-worker-20261023"));
                var floor=GameObject.CreatePrimitive(PrimitiveType.Cube);floor.transform.position=new Vector3(0,-.5f,0);floor.transform.localScale=new Vector3(100,1,100);
                floor.GetComponent<Renderer>().sharedMaterial=new Material(Shader.Find("Standard")){color=new Color(.18f,.21f,.25f)};
                var host=new GameObject("Chibi Play Mode check");playWorker=host.AddComponent<FactoryWorker>();playWorker.enabled=false;
                playWorker.Initialize(null,new GameObject("Observation").AddComponent<Camera>());
                var controller=playWorker.WorkerRoot.GetComponent<CharacterController>();controller.enabled=false;playWorker.WorkerRoot.position=new Vector3(0,.03f,0);controller.enabled=true;
                playWorker.EnterWorker();playWorker.SetThirdPerson(true);
                reviewCamera=new GameObject("Actual frame review camera").AddComponent<Camera>();reviewCamera.depth=100;reviewCamera.clearFlags=CameraClearFlags.SolidColor;reviewCamera.backgroundColor=new Color(.12f,.15f,.19f);
                reviewCamera.orthographic=true;reviewCamera.orthographicSize=1.08f;
                var light=new GameObject("Play review light").AddComponent<Light>();light.type=LightType.Directional;light.intensity=.8f;light.transform.rotation=Quaternion.Euler(40,-140,0);
                var capture=host.GetComponent<FactoryCapture>();capture.width=320;capture.height=240;capture.outputDirectory=Path.Combine(dir,"play-captures");capture.Configure(playWorker.PdaCamera,null,null);
                Physics.SyncTransforms();return;
            }
            stageFrame++;
            var root=playWorker.WorkerRoot;
            var visual=root.GetComponentInChildren<FactoryWorkerVisual>();
            if(stage==0)playWorker.Step(1f/60,Vector2.zero,Vector2.zero);
            if(stage==1)playWorker.Step(1f/60,Vector2.up,Vector2.zero);
            if(stage==2)playWorker.StepMovement(1f/60,Vector2.up,Vector2.zero,true,false);
            if(stage==3)playWorker.StepMovement(1f/60,Vector2.zero,Vector2.zero,false,stageFrame==1);
            if(stage==4){
                if(stageFrame==1)playWorker.TogglePda();
                visual.Advance(1f/60,0,true,0,true);playWorker.SetThirdPerson(true);
                if(stageFrame==10)Check(playWorker.TakePhoto()&&playWorker.GetComponent<FactoryCapture>().Save(),"Play Mode photograph and save");
            }
            reviewCamera.transform.position=root.position+new Vector3(2.1f,1.35f,3.5f);reviewCamera.transform.LookAt(root.position+Vector3.up*.86f);
            if(stageFrame==20){
                var states=new[]{"Idle","Walking","Running","Jumping","Photographing"};State(visual,states[stage]);
                SavePlayFrame(reviewCamera,Path.Combine(dir,"play-"+stageNames[stage]+".png"));
            }
            if(stageFrame<(stage==3?120:45))return;
            string path=Path.Combine(dir,"play-"+stageNames[stage]+".png");
            Check(File.Exists(path)&&new FileInfo(path).Length>10000,"actual frame saved: "+stageNames[stage]);
            if(++stage<5){stageFrame=0;return;}
            playWorker.TogglePda();playWorker.ExitWorker();
            SessionState.SetBool("ShiftLink.ChibiPlay",false);
            File.WriteAllText(Path.Combine(dir,"play-checks.txt"),"PASS: "+checks+" actual Play Mode states, rendered frames and photo/save checks");
            Debug.Log("CHIBI_WORKER_PLAY_PASS: "+checks);EditorApplication.Exit(0);
        }catch(Exception error){
            SessionState.SetBool("ShiftLink.ChibiPlay",false);Debug.LogException(error);
            if(dir!=null)File.WriteAllText(Path.Combine(dir,"play-checks.txt"),"FAIL: "+error);
            EditorApplication.Exit(1);
        }
    }
}
