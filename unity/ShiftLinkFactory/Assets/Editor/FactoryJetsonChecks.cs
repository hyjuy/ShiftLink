using System;
using System.IO;
using UnityEditor;
using UnityEngine;

// Read-only integration check: no control commands or recognition data are sent to Jetson.
[InitializeOnLoad]
public static class FactoryJetsonChecks
{
    static FactoryJetsonChecks() { EditorApplication.update+=Check; }
    public static void Run()
    {
        SessionState.SetBool("ShiftLink.JetsonCheck",true);
        SessionState.SetFloat("ShiftLink.JetsonStart",(float)EditorApplication.timeSinceStartup);
        SessionState.SetInt("ShiftLink.JetsonSequence",-1);
        try {
            FactoryChecks.OpenDemo();
            if(PlayerSettings.insecureHttpOption==InsecureHttpOption.NotAllowed)
                throw new Exception("Jetson HTTP must be allowed in development");
        } catch(Exception error) { Fail(error); }
    }
    static void Check()
    {
        if(!SessionState.GetBool("ShiftLink.JetsonCheck",false)) return;
        try {
            if(EditorApplication.timeSinceStartup-SessionState.GetFloat("ShiftLink.JetsonStart",0)>60)
                throw new Exception("Jetson MES Unity connection timed out");
            var factory=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if(!Application.isPlaying || factory==null || !factory.Connected || factory.EquipmentCount==0) return;
            if(factory.mesUrl.Contains("127.0.0.1") || factory.mesUrl.Contains("localhost"))
                throw new Exception("Jetson check must use the external MES address");
            int first=SessionState.GetInt("ShiftLink.JetsonSequence",-1);
            if(first<0) { SessionState.SetInt("ShiftLink.JetsonSequence",factory.CurrentSequence); return; }
            if(factory.CurrentSequence<=first) return;
            var monitor=factory.GetComponent<FactoryMonitor>();
            if(monitor==null || !monitor.Content.Contains("MES 연결됨") || !monitor.Content.Contains("갱신 "+factory.CurrentSequence))
                throw new Exception("Jetson monitor must show the accepted live sequence");
            var dir=Path.Combine(Application.dataPath,"../Checks");
            FactoryChecks.Capture(Path.Combine(dir,"jetson-factory.png"));
            string result="PASS: Jetson MES "+factory.mesUrl+"; run="+factory.CurrentRunId+
                "; sequence="+factory.CurrentSequence+"; equipment="+factory.EquipmentCount+"; coils="+factory.CoilCount;
            File.WriteAllText(Path.Combine(dir,"jetson-check-result.txt"),result);
            SessionState.SetBool("ShiftLink.JetsonCheck",false);
            Debug.Log(result); EditorApplication.Exit(0);
        } catch(Exception error) { Fail(error); }
    }
    static void Fail(Exception error)
    {
        SessionState.SetBool("ShiftLink.JetsonCheck",false); Debug.LogException(error); EditorApplication.Exit(1);
    }
}
