using System;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

[InitializeOnLoad]
public static class FactoryChecks
{
    static FactoryChecks()
    {
        if (SessionState.GetBool("ShiftLink.PlayCheck", false)) EditorApplication.update += CheckPlay;
    }
    public static void OpenDemo()
    {
        PlayerSettings.insecureHttpOption=InsecureHttpOption.DevelopmentOnly;
        AssetDatabase.SaveAssets();
        if (!File.Exists("Assets/Scenes/Factory.unity")) {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("ShiftLink Factory").AddComponent<FactoryDemo>().CreateEnvironment();
            Directory.CreateDirectory("Assets/Scenes");
            EditorSceneManager.SaveScene(scene, "Assets/Scenes/Factory.unity");
            EditorBuildSettings.scenes = new[] {new EditorBuildSettingsScene("Assets/Scenes/Factory.unity", true)};
        } else EditorSceneManager.OpenScene("Assets/Scenes/Factory.unity");
        if(!Application.isBatchMode) EditorApplication.ExecuteMenuItem("Window/General/Game");
        EditorApplication.EnterPlaymode();
    }
    public static void PlayCheck()
    {
        SessionState.SetInt("ShiftLink.FirstSequence", -1);
        SessionState.SetBool("ShiftLink.PlayCheck", true);
        SessionState.SetFloat("ShiftLink.PlayStart", (float)EditorApplication.timeSinceStartup);
        EditorApplication.update += CheckPlay;
        OpenDemo();
    }
    static void CheckPlay()
    {
        if (!SessionState.GetBool("ShiftLink.PlayCheck", false)) return;
        try {
            if (EditorApplication.timeSinceStartup - SessionState.GetFloat("ShiftLink.PlayStart", 0) > 60)
                throw new Exception("Live MES/PDA Unity check timed out");
            var factory = UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if (Application.isPlaying && factory != null && factory.Connected &&
                factory.EquipmentCount == 10 && factory.CoilCount > 0 && factory.SelectedId != null) {
                int first = SessionState.GetInt("ShiftLink.FirstSequence", -1);
                if (first < 0) { SessionState.SetInt("ShiftLink.FirstSequence", factory.CurrentSequence); return; }
                if (factory.CurrentSequence <= first) return;
                var monitor=factory.GetComponent<FactoryMonitor>();
                Check(monitor!=null && monitor.Content.Contains("MES 연결됨") && monitor.Content.Contains("갱신 "+factory.CurrentSequence), "live monitor must reflect accepted MES sequence");
                Capture(Path.Combine(Application.dataPath, "../Checks/live-factory.png"));
                File.WriteAllText(Path.Combine(Application.dataPath, "../Checks/play-check-result.txt"),
                    "PASS: Unity Play Mode received live MES state, advancing MES sequence, coils and PDA recognition; run=" + factory.CurrentRunId);
                SessionState.SetBool("ShiftLink.PlayCheck", false);
                Debug.Log("SHIFTLINK LIVE PLAY CHECK PASS");
                EditorApplication.Exit(0);
            }

        } catch (Exception error) {
            SessionState.SetBool("ShiftLink.PlayCheck", false); Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
    public static void Capture(string path)
    {
        var camera = Camera.main;
        var render = new RenderTexture(1600, 900, 24);
        var previous = RenderTexture.active;
        var previousTarget = camera.targetTexture;
        camera.targetTexture = render; camera.Render(); RenderTexture.active = render;
        var pixels = new Texture2D(1600, 900, TextureFormat.RGB24, false);
        pixels.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0); pixels.Apply();
        File.WriteAllBytes(path, pixels.EncodeToPNG());
        camera.targetTexture = previousTarget; RenderTexture.active = previous;
        render.Release(); UnityEngine.Object.DestroyImmediate(render); UnityEngine.Object.DestroyImmediate(pixels);
    }

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
            var badConfig = JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir, "config.json"))).config;
            badConfig.route = new[] {config.route[0], config.route[0]};
            Check(!FactoryRules.Valid(badConfig), "duplicate route must be rejected");
            badConfig = JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir, "config.json"))).config;
            badConfig.branches = new[] {new BranchSpec {from_id=config.route[0], to_id=config.route[0]}};
            Check(!FactoryRules.Valid(badConfig), "self branch must be rejected");
            var badState = JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir, "state.json")));
            badState.coils = new[] {state.coils[0], state.coils[0]};
            Check(!FactoryRules.Matches(config, badState), "duplicate coil IDs must be rejected");

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
            factory.ApplyScans(new ScanEnvelope {scans=new ScanReading[] {null}});
            Check(factory.SelectedId == scans.scans[0].equipment_id, "null scan preserves valid selection");
            factory.ApplyScans(new ScanEnvelope {scans=new[] {new ScanReading {scan_id="bad",equipment_id=null}}});
            Check(factory.SelectedId == scans.scans[0].equipment_id, "null scan equipment ID preserves selection");

            Capture(Path.Combine(dir, "fixture-factory.png"));
            factory.Disconnect("check disconnect");
            Check(factory.CoilCount == 0, "stale coils hidden");
            // Store only the startup object; equipment and display are built from MES at runtime.
            scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("ShiftLink Factory").AddComponent<FactoryDemo>();
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
