using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryStairChecks
{
    static int assertions;
    static void Check(bool value,string message) { assertions++; if(!value) throw new Exception(message); }
    public static void Run()
    {
        string dir=Path.GetFullPath(Path.Combine(Application.dataPath,"../Checks"));
        Directory.CreateDirectory(dir);
        float previousSpacing=FactoryRig.LayoutSpacing;
        try {
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            foreach(float spacing in new[]{1f,1.5f}) foreach(float dt in new[]{1f/60,1f/30}) {
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                FactoryRig.LayoutSpacing=spacing;
                var demo=new GameObject("Stair check factory").AddComponent<FactoryDemo>();
                demo.enabled=false;
                demo.CreateEnvironment();
                // Photography expands the hall together with the equipment spacing.
                if(spacing>1) foreach(Transform child in demo.transform)
                    if(child.name=="Factory floor" || child.name=="Factory apron" || child.name=="Floor grid" ||
                        child.name=="Factory building" || child.name=="Employee building collisions" || child.name=="Virtual process campus")
                        child.localScale=Vector3.Scale(child.localScale,new Vector3(spacing,1,spacing));
                demo.Build(config);
                var nodes=demo.transform.Find("MES equipment");
                var stairs=nodes.Find("CAU access stairs");
                Check(stairs!=null && stairs.childCount==16,"Expected 16 stair treads");
                var treads=stairs.Cast<Transform>().OrderBy(t=>t.position.y).ToArray();
                foreach(var tread in treads)
                    Check(tread.GetComponent<BoxCollider>()!=null && !tread.GetComponent<BoxCollider>().isTrigger,
                        "Missing solid stair collider: "+tread.position);
                foreach(string name in new[]{"CAU utility platform","CAU stair landing"})
                    Check(nodes.Find(name).GetComponent<BoxCollider>()!=null,"Missing deck collider: "+name);
                Physics.SyncTransforms();
                foreach(string name in new[]{"CAU landing back rail","CAU landing front rail","CAU landing end rail","CAU access back rail"}) {
                    var barrier=nodes.Find(name+" collision")?.GetComponent<BoxCollider>();
                    Check(barrier!=null && barrier.Raycast(new Ray(barrier.transform.position+barrier.transform.forward*.3f,-barrier.transform.forward),out var railHit,1),
                        "Exposed access edge has no solid guardrail: "+name);
                }
                float deckHeight=nodes.Find("CAU stair landing").GetComponent<BoxCollider>().bounds.max.y;
                Check(!Physics.Raycast(new Vector3(treads[0].position.x,deckHeight+.5f,treads.Last().position.z+.2f),Vector3.back,.5f),
                    "Guardrail blocks the stair entrance");
                foreach(var tread in treads) {
                    var box=tread.GetComponent<BoxCollider>();
                    Check(box.Raycast(new Ray(box.bounds.center+Vector3.up,Vector3.down),out var hit,2),
                        "Stair surface is not physically hittable");
                }
                var worker=demo.GetComponent<FactoryWorker>();
                var controller=worker.WorkerRoot.GetComponent<CharacterController>();
                var landing=nodes.Find("CAU stair landing").GetComponent<BoxCollider>();
                var platform=nodes.Find("CAU utility platform").GetComponent<BoxCollider>();
                Check(Mathf.Abs(landing.bounds.min.z-platform.bounds.min.z)<.001f,
                    "Landing outer edge must align with the CAU deck");
                float bottomZ=treads[0].GetComponent<BoxCollider>().bounds.max.z+.8f;
                float topZ=treads.Last().GetComponent<BoxCollider>().bounds.min.z-.3f;
                controller.enabled=false;
                worker.WorkerRoot.position=new Vector3(treads[0].position.x,.05f,bottomZ);
                controller.enabled=true;
                worker.EnterWorker();
                typeof(FactoryWorker).GetField("yaw",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(worker,180f);
                Physics.SyncTransforms();
                for(int i=0;i<Mathf.CeilToInt(.5f/dt);i++) worker.Step(dt,Vector2.zero,Vector2.zero);
                int ticks=Mathf.CeilToInt((bottomZ-topZ)/(worker.speed*dt));
                for(int i=0;i<ticks;i++) worker.Step(dt,Vector2.up,Vector2.zero);
                var pos=worker.WorkerRoot.position;
                Debug.Log("STAIR ASCENT spacing="+spacing+" dt="+dt+" position="+pos);
                Check(pos.z<topZ+.2f && Mathf.Abs(pos.y-landing.bounds.max.y)<.12f,
                    "Employee blocked ascending stairs: spacing="+spacing+" dt="+dt+" position="+pos+" targetZ="+topZ);
                typeof(FactoryWorker).GetField("yaw",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(worker,270f);
                float targetX=platform.bounds.max.x-.35f;
                ticks=Mathf.CeilToInt((pos.x-targetX)/(worker.speed*dt));
                for(int i=0;i<ticks;i++) worker.Step(dt,Vector2.up,Vector2.zero);
                Check(worker.WorkerRoot.position.x<targetX+.15f && Mathf.Abs(worker.WorkerRoot.position.y-platform.bounds.max.y)<.12f,
                    "Employee cannot cross landing to utility platform");
                // Return to the top tread and walk down using the same employee movement.
                controller.enabled=false;
                worker.WorkerRoot.position=new Vector3(treads[0].position.x,landing.bounds.max.y+.04f,topZ);
                controller.enabled=true;
                typeof(FactoryWorker).GetField("yaw",BindingFlags.Instance|BindingFlags.NonPublic).SetValue(worker,0f);
                Physics.SyncTransforms();
                ticks=Mathf.CeilToInt((bottomZ-topZ)/(worker.speed*dt));
                for(int i=0;i<ticks;i++) worker.Step(dt,Vector2.up,Vector2.zero);
                for(int i=0;i<Mathf.CeilToInt(.5f/dt);i++) worker.Step(dt,Vector2.zero,Vector2.zero);
                Check(worker.WorkerRoot.position.z>bottomZ-.2f && worker.WorkerRoot.position.y<.12f,
                    "Employee cannot descend to factory floor: "+worker.WorkerRoot.position+" expectedZ="+bottomZ);
                worker.ExitWorker();
                if(spacing==1f && dt==1f/60) {
                    var camera=Camera.main;
                    camera.transform.position=landing.bounds.center+new Vector3(4,3.5f,6);
                    camera.transform.LookAt(landing.bounds.center+new Vector3(-1,-.6f,1.3f));
                    FactoryChecks.Capture(Path.Combine(dir,"cau-access-rails.png"));
                }
            }
            File.WriteAllText(Path.Combine(dir,"stair-check-result.txt"),"PASS: "+assertions+" assertions; solid treads/decks and access guardrails, open stair entrance, actual FactoryWorker.Step ascent, landing crossing and descent; spacing 1/1.5; 30/60 Hz.");
            Debug.Log("SHIFTLINK STAIR CHECK PASS: "+assertions);
        } catch(Exception error) {
            File.WriteAllText(Path.Combine(dir,"stair-check-result.txt"),"FAIL: "+error);
            Debug.LogException(error);
            EditorApplication.Exit(1);
        } finally { FactoryRig.LayoutSpacing=previousSpacing; }
    }
}
