using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

[InitializeOnLoad]
public static class FactoryAlertPlayChecks
{
    static FactoryAlertPlayChecks() { EditorApplication.update+=Check; }
    public static void Run()
    {
        SessionState.SetBool("ShiftLink.AlertPlayCheck",true);
        SessionState.SetFloat("ShiftLink.AlertPlayStart",(float)EditorApplication.timeSinceStartup);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
        var demo=new GameObject("Offline alert test").AddComponent<FactoryDemo>();
        demo.mesUrl="http://127.0.0.1:1";
        EditorApplication.EnterPlaymode();
    }
    static void Assert(bool ok,string message) { if(!ok) throw new Exception(message); }
    static void Check()
    {
        if(!SessionState.GetBool("ShiftLink.AlertPlayCheck",false)) return;
        try {
            if(EditorApplication.timeSinceStartup-SessionState.GetFloat("ShiftLink.AlertPlayStart",0)>60) throw new Exception("Alert play check timed out");
            var demo=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if(!Application.isPlaying || demo==null || demo.EquipmentCount!=10) return;
            demo.StopAllCoroutines();
            Assert(!demo.Connected && demo.CoilCount==0,"Real offline Start must display ten devices without coils");
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var fixture=JsonUtility.FromJson<FaultFixtures>(File.ReadAllText(Path.Combine(dir,"fault-fixtures.json")));
            demo.Build(fixture.config);
            var normal=fixture.states.First(s=>s.scenario_id=="normal");
            var warning=JsonUtility.FromJson<MesSnapshot>(JsonUtility.ToJson(normal));
            warning.equipment[0].fault_level="warning"; warning.run_id="sound-warning";
            var alerts=demo.GetComponent<FactoryFaults>(); demo.Apply(warning);
            Assert(alerts.SoundPlaying && !alerts.EmergencyLoop,"Warning must play a non-looping beep");
            alerts.Mute(); demo.Apply(warning);
            Assert(!alerts.SoundPlaying && alerts.SoundMuted,"Same incident must retain mute");
            warning.equipment[0].fault_level="critical"; demo.Apply(warning);
            Assert(alerts.SoundPlaying && alerts.EmergencyLoop && !alerts.SoundMuted,"Escalation must start emergency loop");
            demo.Disconnect("offline sound check");
            Assert(!alerts.SoundPlaying,"Disconnect must silence stale alarm");
            demo.Apply(normal);
            Assert(!alerts.SoundPlaying && alerts.ActiveEffectCount==0,"Normal recovery must clear sound and effects");
            FactoryChecks.Capture(Path.Combine(dir,"offline-alert-play.png"));
            File.WriteAllText(Path.Combine(dir,"alert-play-result.txt"),"PASS: real offline Start, warning beep, emergency loop, mute, disconnect, normal recovery");
            SessionState.SetBool("ShiftLink.AlertPlayCheck",false); EditorApplication.Exit(0);
        } catch(Exception error) {
            SessionState.SetBool("ShiftLink.AlertPlayCheck",false); Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
}
