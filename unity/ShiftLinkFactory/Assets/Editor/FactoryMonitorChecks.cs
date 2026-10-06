using System;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

public static class FactoryMonitorChecks
{
    static void Check(bool value,string message) { if(!value) throw new Exception(message); }
    public static void Run()
    {
        try {
            var dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var factory=new GameObject("Monitor check factory").AddComponent<FactoryDemo>();
            factory.CreateEnvironment(); factory.Build(config); factory.Apply(state);
            var display=factory.transform.Find("Factory status display");
            Check(display!=null,"factory must contain an in-world status display");
            var text=display.GetComponentInChildren<TextMesh>();
            Check(text!=null && text.text.Contains("MES 연결됨"),"display must show live connection");
            Check(text.text.Contains(config.equipment[0].code),"display must show equipment codes");
            Check(text.text.Contains("코일 "+state.coils.Length),"display must show current coil count");
            Check(text.text.Contains("RT-01 → RT-02 → RT-03 → CV-01"),"display must show configured route");
            Check(text.text.Contains("RT-03 → CV-02"),"display must show configured branch");
            state.line_mode="paused"; state.sequence++;
            state.equipment[0].operating_state="waiting"; state.equipment[0].fault_level="warning";
            factory.Apply(state);
            Check(text.text.Contains("일시정지") && text.text.Contains("대기 / 경고"),"display must follow pause and warning updates");
            factory.Disconnect("monitor test");
            Check(text.text.Contains("연결 끊김") && !text.text.Contains("코일 "+state.coils.Length),"offline display must hide stale live values");
            File.WriteAllText(Path.Combine(dir,"monitor-check-result.txt"),"PASS: world display, route, branch, equipment, coil count, pause, warning, disconnect");
            Debug.Log("SHIFTLINK MONITOR CHECK PASS"); EditorApplication.Exit(0);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
