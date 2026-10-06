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
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Factory motion test").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state);
            var rollers=demo.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("Roller_") && t.childCount>0).ToArray();
            Check(rollers.Length>=36,"Imported RT roller pivots required, not primitive placeholders");
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
            foreach(var e in state.equipment) e.operating_state="waiting";
            demo.Apply(state); rotation=first.localRotation; old=coil.position;
            step.Invoke(demo,new object[]{.2f});
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"waiting must stop rollers");
            Check(Vector3.Distance(old,coil.position)<.001f,"waiting must stop transport");
            foreach(var e in state.equipment) { e.operating_state="running"; e.fault_level="critical"; }
            demo.Apply(state); rotation=first.localRotation; step.Invoke(demo,new object[]{.2f});
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"critical fault must stop motion");
            demo.Disconnect("test offline"); rotation=first.localRotation; step.Invoke(demo,new object[]{.2f});
            Check(coils.childCount==0,"offline must hide coils");
            Check(Quaternion.Angle(rotation,first.localRotation)<.001f,"offline must stop mechanisms");
            File.WriteAllText(Path.Combine(dir,"motion-result.txt"),"PASS: imported FBX, running/waiting/critical/offline, stable coils, MES movement");
            Debug.Log("SHIFTLINK MOTION CHECK PASS"); EditorApplication.Exit(0);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
