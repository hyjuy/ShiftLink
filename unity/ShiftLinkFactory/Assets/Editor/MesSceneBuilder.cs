using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class MesSceneBuilder
{
    [MenuItem("ShiftLink/Create Manufacturing Scene")]
    public static void CreateScene()
    {
        if (!Application.isBatchMode && !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
        var asset = Resources.Load<TextAsset>("mes-config");
        if (!asset) throw new System.Exception("Run scripts/export_unity_mes.py first");
        var envelope = JsonUtility.FromJson<MesSceneBootstrap.Envelope>(asset.text);
        if (envelope == null || envelope.config == null || envelope.config.equipment == null)
            throw new System.Exception("Invalid MES export");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        new GameObject("MES manufacturing scene").AddComponent<MesSceneBootstrap>();
        Directory.CreateDirectory("Assets/Scenes");
        if (!EditorSceneManager.SaveScene(scene, "Assets/Scenes/Manufacturing.unity"))
            throw new System.Exception("Could not save manufacturing scene");
        EditorBuildSettings.scenes = new[] {
            new EditorBuildSettingsScene("Assets/Scenes/Manufacturing.unity", true)
        };
        AssetDatabase.SaveAssets();
        Debug.Log("ShiftLink scene saved; press Play to generate " + envelope.config.equipment.Length + " equipment.");
    }
}

