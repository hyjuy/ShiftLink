using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Uses reflection so the missing feature produces a runnable RED before implementation.
public static class FactoryWorkerChecks
{
    static int assertions;
    static void Check(bool value, string label)
    {
        assertions++;
        if (!value) throw new Exception(label);
        Debug.Log("PASS: " + label);
    }
    static object Get(object target, string name)
    {
        var type = target.GetType();
        var property = type.GetProperty(name);
        return property != null ? property.GetValue(target) : type.GetField(name).GetValue(target);
    }
    static object Call(object target, string name, params object[] args)
    {
        try { return target.GetType().GetMethod(name).Invoke(target, args); }
        catch (TargetInvocationException error) { throw error.InnerException ?? error; }
    }
    static void Set(object target, string name, object value) { target.GetType().GetField(name).SetValue(target, value); }
    public static void Run()
    {
        string dir = Path.GetFullPath(Path.Combine(Application.dataPath, "../Checks"));
        Directory.CreateDirectory(dir);
        try {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var config = JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir, "config.json"))).config;
            var demo = new GameObject("Worker check factory").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config);
            var workerType = typeof(FactoryDemo).Assembly.GetType("FactoryWorker");
            var captureType = typeof(FactoryDemo).Assembly.GetType("FactoryCapture");
            Check(workerType != null && captureType != null, "employee and PDA capture components must exist");
            var worker = demo.GetComponent(workerType);
            var capture = demo.GetComponent(captureType);
            Check(worker != null && capture != null, "factory initializes employee and capture components");
            Check(Shader.Find("Unlit/Color") != null, "instance mask shader available");
            var observation = Camera.main;
            Vector3 previousPosition = observation.transform.position;
            Quaternion previousRotation = observation.transform.rotation;
            Call(worker, "EnterWorker");
            Check((bool)Get(worker, "IsWorkerMode"), "employee mode can be entered");
            var root = (Transform)Get(worker, "WorkerRoot");
            Check(root.GetComponent<CharacterController>() != null, "employee has a CharacterController");
            Check(root.GetComponentsInChildren<Renderer>(true).Length >= 6, "employee body and PDA are visible models");
            Vector3 before = root.position;
            Physics.SyncTransforms();
            Call(worker, "Step", .25f, new Vector2(0, 1), Vector2.zero);
            Check(Vector3.Distance(before, root.position) > .1f, "employee moves through shared movement path");
            demo.SetExteriorView(false);
            Physics.SyncTransforms();
            Check(Physics.Raycast(new Vector3(0, 1, 16), Vector3.forward, 2), "interior view retains physical rear wall");
            Call(worker, "ExitWorker");
            Check(!(bool)Get(worker, "IsWorkerMode") && observation.enabled, "observation camera restored on exit");
            // Capture actual imported factory geometry, excluding explanatory overlays.
            var node = demo.transform.Find("MES equipment").GetChild(0);
            var pda = (Camera)Get(worker, "PdaCamera");
            pda.transform.position = node.position + new Vector3(0, 2, -6);
            pda.transform.LookAt(node.position + Vector3.up);
            Set(capture, "width", 640); Set(capture, "height", 360);
            string output = Path.Combine(dir, "worker-captures-" + Guid.NewGuid().ToString("N"));
            Set(capture, "outputDirectory", output);
            Check((bool)Call(capture, "Capture"), "PDA captures actual factory geometry");
            Check(((Texture2D)Get(capture, "Preview")).width == 640, "preview uses configured dimensions");
            Check((bool)Call(capture, "Save"), "PNG and JSON save together");
            string saved = (string)Get(capture, "LastSavedPath");
            Check(File.Exists(saved) && File.Exists(Path.ChangeExtension(saved, ".json")), "saved pair exists on disk");
            Check((bool)Call(capture, "Save") && Directory.GetFiles(output, "*.png", SearchOption.AllDirectories).Length == 1,
                "repeated save does not duplicate the capture");
            File.Copy(saved, Path.Combine(dir, "worker-pda-capture.png"), true);
            // A separate, controlled scene tests occlusion and top-left pixel coordinates.
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var host = new GameObject("Capture geometry check");
            capture = host.AddComponent(captureType);
            var camera = new GameObject("PDA test camera").AddComponent<Camera>();
            camera.enabled = false; camera.transform.position = new Vector3(0, 0, -6);
            camera.transform.rotation = Quaternion.identity; camera.fieldOfView = 60;
            var front = GameObject.CreatePrimitive(PrimitiveType.Cube); front.name = "near HPU";
            var back = GameObject.CreatePrimitive(PrimitiveType.Cube); back.name = "hidden GR";
            back.transform.position = new Vector3(0, 0, 2);
            var miniConfig = new FactoryConfig { config_id = "mask-check", equipment = new[] {
                new EquipmentSpec { equipment_id = "near", profile_id = "hpu", code = "HPU-01", active = true },
                new EquipmentSpec { equipment_id = "far", profile_id = "gr", code = "GR-01", active = true }
            }, route = new[] { "near", "far" } };
            var nodes = new Dictionary<string, GameObject> { { "near", front }, { "far", back } };
            Set(capture, "width", 320); Set(capture, "height", 240); Set(capture, "outputDirectory", output);
            Call(capture, "Configure", camera, miniConfig, nodes, 0);
            var originalMaterial = front.GetComponent<Renderer>().sharedMaterial;
            Check((bool)Call(capture, "Capture"), "controlled scene capture succeeds");
            var metadata = Get(capture, "PreviewMetadata");
            var objects = (Array)Get(metadata, "objects");
            Check(objects.Length == 1 && (string)Get(objects.GetValue(0), "equipment_id") == "near", "fully occluded equipment has no visible GT box");
            Check((int)Get(objects.GetValue(0), "class_id") == 0, "HPU has fixed class index zero");
            Check(front.GetComponent<Renderer>().sharedMaterial == originalMaterial, "mask pass restores render materials");
            front.transform.position = new Vector3(-1, 1, 0);
            Check((bool)Call(capture, "Capture"), "changed scene capture succeeds");
            objects = (Array)Get(Get(capture, "PreviewMetadata"), "objects");
            Check(objects.Length == 2, "separate visible instances both receive GT");
            var near = objects.Cast<object>().First(o => (string)Get(o, "equipment_id") == "near");
            var box = (float[])Get(near, "bbox_xyxy");
            Check(box[0] >= 0 && box[1] >= 0 && box[2] <= 320 && box[3] <= 240 && box[0] < box[2] && box[1] < box[3], "GT box is finite and inside image bounds");
            Check((box[1] + box[3]) * .5f < 120, "positive world height maps to top-left image coordinates");
            string blocker = Path.Combine(dir, "capture-blocker-" + Guid.NewGuid().ToString("N"));
            File.WriteAllText(blocker, "file blocks directory"); Set(capture, "outputDirectory", blocker);
            Check(!(bool)Call(capture, "Save") && (bool)Get(capture, "HasPreview"), "failed save retains preview and reports failure");
            Set(capture, "outputDirectory", output);
            Check((bool)Call(capture, "Save"), "save can retry after directory error");
            front.SetActive(false); back.SetActive(false);
            Check((bool)Call(capture, "Capture") && ((Array)Get(Get(capture, "PreviewMetadata"), "objects")).Length == 0,
                "empty scenes produce valid negative training examples");
            Check((bool)Call(capture, "Save"), "empty scene can be saved");
            File.WriteAllText(Path.Combine(dir, "worker-check-result.txt"), "PASS: " + assertions + " employee/camera/save/occlusion assertions; captures=" + output);
            Debug.Log("SHIFTLINK WORKER CAPTURE CHECK PASS");
            EditorApplication.Exit(0);
        } catch (Exception error) {
            File.WriteAllText(Path.Combine(dir, "worker-check-result.txt"), "FAIL: " + error);
            Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
}
