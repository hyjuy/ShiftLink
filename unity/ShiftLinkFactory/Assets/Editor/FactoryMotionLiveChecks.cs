using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class FactoryMotionLiveChecks
{
    static Transform roller,load;
    static Quaternion firstRotation;
    static Vector3 firstPosition;
    static int firstSequence=-1;
    static float began;
    static FactoryMotionLiveChecks() { EditorApplication.update+=Check; }
    public static void Run()
    {
        FactoryAssetBuilder.Prepare();
        SessionState.SetBool("ShiftLink.MotionLive",true);
        SessionState.SetFloat("ShiftLink.MotionStart",(float)EditorApplication.timeSinceStartup);
        FactoryChecks.OpenDemo();
    }
    static void Check()
    {
        if(!SessionState.GetBool("ShiftLink.MotionLive",false)) return;
        try {
            if(EditorApplication.timeSinceStartup-SessionState.GetFloat("ShiftLink.MotionStart",0)>60) throw new Exception("Live motion timed out");
            var factory=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if(!Application.isPlaying || factory==null || !factory.Connected || factory.CoilCount==0 || factory.SelectedId==null) return;
            if(firstSequence<0) {
                roller=factory.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("Roller_") && t.childCount>0);
                load=factory.transform.Find("MES coils").GetChild(0);
                firstRotation=roller.localRotation; firstPosition=load.position;
                firstSequence=factory.CurrentSequence; began=Time.realtimeSinceStartup; return;
            }
            if(Time.realtimeSinceStartup-began<1 || factory.CurrentSequence<=firstSequence) return;
            if(load==null) { firstSequence=-1; return; }
            if(Quaternion.Angle(firstRotation,roller.localRotation)<.1f || Vector3.Distance(firstPosition,load.position)<.01f) return;
            var dir=Path.Combine(Application.dataPath,"../Checks"); Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir,"play-check-result.txt"),"PASS: live MES HTTP, advancing sequence, roller rotation, persistent moving load, PDA selection; run="+factory.CurrentRunId);
            SessionState.SetBool("ShiftLink.MotionLive",false); Debug.Log("SHIFTLINK LIVE MOTION CHECK PASS"); EditorApplication.Exit(0);
        } catch(Exception error) { SessionState.SetBool("ShiftLink.MotionLive",false); Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
