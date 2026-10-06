using System;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

public static class FactoryChecks
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    public static void Run()
    {
        try {
            var dir = Path.Combine(Application.dataPath, "../Checks");
            var config = JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir, "config.json"))).config;
            var state = JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir, "state.json")));
            var scans = JsonUtility.FromJson<ScanEnvelope>(File.ReadAllText(Path.Combine(dir, "scans.json")));
            Check(FactoryRules.Matches(config, state), "MES configuration must match snapshot");
            state.config_id = "stale";
            Check(!FactoryRules.Matches(config, state), "stale snapshot must be rejected");
            state.config_id = config.config_id;
            Check(FactoryRules.StateColor("running", "normal") == FactoryRules.Green, "running green");
            Check(FactoryRules.StateColor("waiting", "normal") == FactoryRules.Amber, "waiting amber");
            Check(FactoryRules.StateColor("running", "warning") == FactoryRules.Amber, "warning amber");
            Check(FactoryRules.StateColor("stopped", "critical") == FactoryRules.Red, "fault red");
            Check(FactoryRules.StateColor("stopped", "normal") == FactoryRules.Grey, "stopped grey");
            Check(FactoryRules.StateColor("unexpected", "normal") == FactoryRules.Grey, "unknown grey");
            Check(!FactoryRules.Matches(null, state), "missing config rejected");
            Check(!FactoryRules.Matches(config, null), "missing snapshot rejected");
            Check(scans.scans.Length == 1, "PDA recognition transported");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var factory = new GameObject("ShiftLink Factory").AddComponent<FactoryDemo>();
            factory.CreateEnvironment();
            factory.Build(config);
            factory.Apply(state);
            factory.ApplyScans(scans);
            Check(factory.EquipmentCount == config.equipment.Length, "all equipment rendered");
            Check(factory.CoilCount == state.coils.Length, "all coils rendered");
            Check(factory.SelectedId == scans.scans[0].equipment_id, "PDA selection highlighted");
            factory.Disconnect("check disconnect");
            Check(factory.CoilCount == 0, "stale coils hidden");
            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/Factory.unity");
            EditorBuildSettings.scenes = new[] {new EditorBuildSettingsScene("Assets/Scenes/Factory.unity", true)};
            AssetDatabase.SaveAssets();
            File.WriteAllText(Path.Combine(dir, "unity-check-result.txt"), "PASS: config, colors, equipment, coils, PDA scan, disconnect, scene");
            Debug.Log("SHIFTLink FACTORY CHECKS PASS");
            EditorApplication.Exit(0);
        } catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
