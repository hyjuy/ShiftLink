using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

// Sends two real selections to the configured MES; the latest must win.
[InitializeOnLoad]
public static class FactorySelectionChecks
{
    [Serializable] class Selection { public string equipment_id; }
    [Serializable] class Snapshot { public Selection unity_selection; }
    static UnityWebRequest request;
    static FactorySelectionChecks() { EditorApplication.update += Check; }
    public static void Run()
    {
        SessionState.SetBool("ShiftLink.SelectionCheck", true);
        SessionState.SetBool("ShiftLink.SelectionSent", false);
        SessionState.SetFloat("ShiftLink.SelectionStart", (float)EditorApplication.timeSinceStartup);
        FactoryChecks.OpenDemo();
    }
    static void Check()
    {
        if(!SessionState.GetBool("ShiftLink.SelectionCheck", false)) return;
        try {
            if(EditorApplication.timeSinceStartup - SessionState.GetFloat("ShiftLink.SelectionStart", 0) > 60)
                throw new Exception("Unity selection synchronization timed out");
            var factory = UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if(!Application.isPlaying || factory == null || !factory.Connected) return;
            if(!SessionState.GetBool("ShiftLink.SelectionSent", false)) {
                factory.SelectEquipment("EQ-0004"); factory.SelectEquipment("EQ-0005");
                SessionState.SetBool("ShiftLink.SelectionSent", true);
            }
            if(request == null) {
                request = UnityWebRequest.Get(factory.mesUrl + "/api/state");
                request.timeout = 5; request.SendWebRequest(); return;
            }
            if(!request.isDone) return;
            var snapshot = request.result == UnityWebRequest.Result.Success
                ? JsonUtility.FromJson<Snapshot>(request.downloadHandler.text) : null;
            request.Dispose(); request = null;
            if(snapshot?.unity_selection?.equipment_id != "EQ-0005" || factory.SelectedId != "EQ-0005") return;
            string result = "PASS: real Unity selection POST reached MES; latest equipment=EQ-0005; MES=" + factory.mesUrl;
            string dir = Path.Combine(Application.dataPath, "../Checks");
            Directory.CreateDirectory(dir);
            FactoryChecks.Capture(Path.Combine(dir, "selection-factory.png"));
            File.WriteAllText(Path.Combine(dir, "selection-check-result.txt"), result);
            SessionState.SetBool("ShiftLink.SelectionCheck", false);
            Debug.Log(result); EditorApplication.Exit(0);
        } catch(Exception error) {
            request?.Dispose(); request = null;
            SessionState.SetBool("ShiftLink.SelectionCheck", false);
            Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
}
