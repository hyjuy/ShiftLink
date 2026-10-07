using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryMotionChecks
{
    static void Check(bool value,string message) { if(!value) throw new Exception(message); }
    public static void Run()
    {
        try {
            var builder=typeof(FactoryMotionChecks).Assembly.GetType("FactoryAssetBuilder");
            if(builder!=null) builder.GetMethod("Prepare").Invoke(null,null);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Factory motion test").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state);
            var rollers=demo.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("Roller_") && t.childCount>0).ToArray();
            Check(rollers.Length>=36,"Imported RT roller pivots required, not primitive placeholders");
            var nodes=demo.transform.Find("MES equipment");
            CheckDetails(demo,nodes,state);
            foreach(var expected in new[]{Tuple.Create("EQ-0006",12),Tuple.Create("EQ-0007",16),Tuple.Create("EQ-0008",12)})
                Check(nodes.Find(expected.Item1).GetComponentsInChildren<Transform>().Count(t=>t.name.StartsWith("Roller_") && t.childCount>0)==expected.Item2,"catalog roller count "+expected.Item1);
            var rt=nodes.Find("EQ-0006");
            var input=rt.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("InputAnchor_"));
            var output=rt.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("OutputAnchor_"));
            Check(Mathf.Abs(output.position.x-input.position.x-4.8f)<.01f,"Unity metres and transport direction");
            Check(Mathf.Abs(input.position.y-1.22f)<.01f,"Unity upward axis and transport plane");
            var step=typeof(FactoryDemo).GetMethod("AdvanceVisuals",BindingFlags.Public|BindingFlags.Instance);
            Check(step!=null,"Deterministic visual motion step required");
            var first=rollers[0]; var rotation=first.localRotation;
            step.Invoke(demo,new object[]{.1f});
            Check(Quaternion.Angle(rotation,first.localRotation)>.1f,"running rollers must rotate");
            var coils=demo.transform.Find("MES coils");
            Check(coils.childCount==state.coils.Length && coils.childCount>0,"coils visible from MES");
            var coil=coils.GetChild(0); var identity=coil.GetInstanceID();
            demo.Apply(state);
            Check(coils.GetChild(0).GetInstanceID()==identity,"snapshot must preserve coil objects");
            var old=coil.position;
            state.coils[0].position=Mathf.Min(.95f,state.coils[0].position+.2f);
            demo.Apply(state); step.Invoke(demo,new object[]{.5f});
            Check(Vector3.Distance(old,coil.position)>.01f,"coil must advance towards MES target");
            Capture(Path.Combine(dir,"motion-running.png"));
            CaptureDetails(nodes,dir);
            foreach(var e in state.equipment) e.operating_state="waiting";
            demo.Apply(state); rotation=first.localRotation; old=coil.position;
            step.Invoke(demo,new object[]{.2f});
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"waiting must stop rollers");
            Check(Vector3.Distance(old,coil.position)<.001f,"waiting must stop transport");
            foreach(var e in state.equipment) { e.operating_state="running"; e.fault_level="critical"; }
            demo.Apply(state); rotation=first.localRotation; step.Invoke(demo,new object[]{.2f});
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"critical fault must stop motion");
            state.coils[0].equipment_id="EQ-0010"; demo.Apply(state);
            Check(coils.Find(state.coils[0].coil_id).Find("Rejected cut sheet")!=null,"scrap branch carries cut sheet, not whole coil");
            demo.Disconnect("test offline"); rotation=first.localRotation; step.Invoke(demo,new object[]{.2f});
            Check(coils.childCount==0,"offline must hide coils");
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"offline must stop mechanisms");
            foreach(string id in new[]{"EQ-0001","EQ-0003"}) {
                var fan=nodes.Find(id).Find(id=="EQ-0001" ? "Pump motor cooling fan" : "Compressor cooling fan");
                var before=fan.localRotation; demo.AdvanceVisuals(.2f);
                Check(Quaternion.Angle(before,fan.localRotation)<.001f,"offline must stop utility fans");
            }
            Capture(Path.Combine(dir,"motion-offline.png"));
            File.WriteAllText(Path.Combine(dir,"motion-result.txt"),"PASS: imported FBX, detailed rollers/lift cylinders, guarded pump/compressor fans, running/paused/stopped/waiting/critical/missing/offline, stable coils, MES movement");
            Debug.Log("SHIFTLINK MOTION CHECK PASS"); EditorApplication.Exit(0);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
    static void CaptureDetails(Transform nodes,string dir)
    {
        var camera=Camera.main; var pos=camera.transform.position; var rotation=camera.transform.rotation;
        foreach(string id in new[]{"EQ-0001","EQ-0002","EQ-0003","EQ-0004","EQ-0007","EQ-0010"}) {
            var target=nodes.Find(id).position+Vector3.up;
            camera.transform.position=target+new Vector3(4,3,-5);
            camera.transform.LookAt(target);
            Capture(Path.Combine(dir,"equipment-detail-"+id+".png"));
        }
        camera.transform.SetPositionAndRotation(pos,rotation);
    }
    static void CheckDetails(FactoryDemo demo,Transform nodes,MesSnapshot state)
    {
        var fans=new[]{nodes.Find("EQ-0001").Find("Pump motor cooling fan"),nodes.Find("EQ-0003").Find("Compressor cooling fan")};
        Check(fans.All(t=>t!=null && t.childCount>=5),"Pump and compressor require visible guarded fan rotors");
        Check(nodes.Find("EQ-0006").GetComponentsInChildren<Transform>().Any(t=>t.name=="Roller rotation stripe"),"Roller rotation must be visible on its surface");
        Check(nodes.Find("EQ-0007").GetComponentsInChildren<Transform>().Count(t=>t.name=="Lift cylinder barrel")==2,"RT-02 needs two lift cylinders");
        var rotations=fans.Select(t=>t.localRotation).ToArray();
        demo.AdvanceVisuals(.1f);
        for(int i=0;i<fans.Length;i++) Check(Quaternion.Angle(rotations[i],fans[i].localRotation)>1,"Running utility fans rotate");
        foreach(string mode in new[]{"paused","stopped"}) {
            state.line_mode=mode; demo.Apply(state); rotations=fans.Select(t=>t.localRotation).ToArray(); demo.AdvanceVisuals(.1f);
            for(int i=0;i<fans.Length;i++) Check(Quaternion.Angle(rotations[i],fans[i].localRotation)<.001f,"Line mode freezes utility fans: "+mode);
        }
        state.line_mode="running";
        foreach(string condition in new[]{"waiting","critical","missing"}) {
            var original=state.equipment;
            if(condition=="missing") state.equipment=original.Where(e=>e.equipment_id!="EQ-0001" && e.equipment_id!="EQ-0003").ToArray();
            else foreach(var e in state.equipment.Where(e=>e.equipment_id=="EQ-0001" || e.equipment_id=="EQ-0003")) {
                e.operating_state=condition=="waiting" ? "waiting" : "running"; e.fault_level=condition=="critical" ? "critical" : "normal";
            }
            demo.Apply(state); rotations=fans.Select(t=>t.localRotation).ToArray(); demo.AdvanceVisuals(.1f);
            for(int i=0;i<fans.Length;i++) Check(Quaternion.Angle(rotations[i],fans[i].localRotation)<.001f,"Unavailable utility fan stops: "+condition);
            state.equipment=original;
        }
        foreach(var e in state.equipment) { e.operating_state="running"; e.fault_level="normal"; }
        demo.Apply(state); rotations=fans.Select(t=>t.localRotation).ToArray();
        foreach(float dt in new[]{0,-1,float.NaN,float.PositiveInfinity}) demo.AdvanceVisuals(dt);
        for(int i=0;i<fans.Length;i++) Check(Quaternion.Angle(rotations[i],fans[i].localRotation)<.001f,"Invalid timestep cannot move utility fans");
    }
    static void Capture(string path)
    {
        var camera=Camera.main; var render=new RenderTexture(1600,900,24);
        var previous=RenderTexture.active; camera.targetTexture=render; camera.Render(); RenderTexture.active=render;
        var pixels=new Texture2D(1600,900,TextureFormat.RGB24,false); pixels.ReadPixels(new Rect(0,0,1600,900),0,0); pixels.Apply();
        File.WriteAllBytes(path,pixels.EncodeToPNG()); camera.targetTexture=null; RenderTexture.active=previous;
        render.Release(); UnityEngine.Object.DestroyImmediate(render); UnityEngine.Object.DestroyImmediate(pixels);
    }
}
