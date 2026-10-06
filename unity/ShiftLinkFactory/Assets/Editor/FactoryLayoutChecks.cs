using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryLayoutChecks
{
    public static Bounds BoundsOf(Transform node)
    {
        var renderers=node.GetComponentsInChildren<MeshRenderer>().Where(r=>r.GetComponent<TextMesh>()==null).ToArray();
        var bounds=renderers[0].bounds;
        foreach(var r in renderers.Skip(1)) bounds.Encapsulate(r.bounds);
        return bounds;
    }
    public static void Run()
    {
        var failures=new List<string>();
        Action<bool,string> check=(ok,label)=>{ if(!ok) failures.Add(label); Debug.Log((ok ? "PASS: " : "FAIL: ")+label); };
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Layout review").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state);
            var nodes=demo.transform.Find("MES equipment");
            foreach(string id in new[]{"EQ-0001","EQ-0002","EQ-0003","EQ-0004","EQ-0005"}) {
                var model=nodes.Find(id).Find("Equipment_"+config.equipment.First(e=>e.equipment_id==id).profile_id.ToUpperInvariant()).Find("Model");
                check(Mathf.Abs(model.localScale.x-1)<.001f,"native metres "+id);
            }
            var specs=config.equipment.Where(e=>e.active).ToArray();
            for(int i=0;i<specs.Length;i++) for(int j=i+1;j<specs.Length;j++)
                check(!BoundsOf(nodes.Find(specs[i].equipment_id)).Intersects(BoundsOf(nodes.Find(specs[j].equipment_id))),"equipment clearance "+specs[i].code+" / "+specs[j].code);
            var platform=nodes.Find("CAU utility platform");
            var cau=BoundsOf(nodes.Find("EQ-0003")); var support=BoundsOf(platform);
            check(support.min.x<=cau.min.x && support.max.x>=cau.max.x && support.min.z<=cau.min.z && support.max.z>=cau.max.z,"CAU fully supported");
            check(nodes.Find("CAU access stairs")!=null && nodes.Find("CAU platform rail")!=null,"CAU stairs and rails");
            check(nodes.GetComponentsInChildren<Transform>().Any(t=>t.name=="Connection_ScrapChute"),"scrap branch chute rendered");
            check(nodes.Find("Pedestrian aisle")!=null && nodes.Find("Maintenance aisle")!=null && nodes.Find("Incoming staging")!=null && nodes.Find("Outgoing staging")!=null && nodes.Find("Scrap collection bin")!=null,"logistics and maintenance areas");
            var cables=nodes.GetComponentsInChildren<LineRenderer>().Where(l=>l.name.StartsWith("Power cable")).ToArray();
            check(cables.Length==3 && cables.All(l=>l.GetPosition(1).y>=2.8f),"power routed overhead");
            var coil=demo.transform.Find("MES coils").GetChild(0);
            var reading=state.coils.First(c=>c.coil_id==coil.name);
            var speed=state.measurements.First(m=>m.equipment_id==reading.equipment_id && m.signal=="rt_speed");
            speed.value=30; speed.quality="good"; reading.position=Mathf.Min(.9f,reading.position+.2f);
            demo.Apply(state); var old=coil.position; demo.AdvanceVisuals(.1f);
            check(Mathf.Abs(Vector3.Distance(old,coil.position)-.05f)<.002f,"coil follows 30 m/min");
            speed.quality="unavailable"; demo.Apply(state); old=coil.position; demo.AdvanceVisuals(.1f);
            check(Vector3.Distance(old,coil.position)<.001f,"missing speed stops coil");
            FactoryChecks.Capture(Path.Combine(dir,"layout-factory.png"));
            File.WriteAllText(Path.Combine(dir,"layout-result.txt"),failures.Count==0 ? "PASS: dimensions, clearance, platform, branch, utility routes, speed, logistics" : string.Join("\n",failures));
            EditorApplication.Exit(failures.Count==0 ? 0 : 1);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
