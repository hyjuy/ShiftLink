using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Uses reflection so the missing feature produces a runnable RED before implementation.
[InitializeOnLoad]
public static class FactoryWorkerChecks
{
    static int assertions;
    static FactoryDemo playFactory;
    static Component playWorker, playCapture;
    static int playFrames;
    static string playDir;
    static bool screenshotRequested;
    static FactoryWorkerChecks()
    {
        if (SessionState.GetBool("ShiftLink.WorkerPlayCheck", false)) EditorApplication.update += CheckPlay;
    }
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
            Check(Resources.Load<Shader>("FactoryInstanceMask") != null, "instance mask shader available");
            var observation = Camera.main;
            Vector3 previousPosition = observation.transform.position;
            Quaternion previousRotation = observation.transform.rotation;
            Call(worker, "EnterWorker");
            Check((bool)Get(worker, "IsWorkerMode"), "employee mode can be entered");
            Check(demo.transform.Find("Factory building/Exterior envelope").gameObject.activeInHierarchy,
                "employee camera sees enclosed factory walls and roof");
            var root = (Transform)Get(worker, "WorkerRoot");
            Check(root.GetComponent<CharacterController>() != null, "employee has a CharacterController");
            Check(root.GetComponentsInChildren<Renderer>(true).Length >= 6, "employee body and PDA are visible models");
            Vector3 before = root.position;
            Physics.SyncTransforms();
            Call(worker, "Step", .25f, new Vector2(0, 1), Vector2.zero);
            Check(Vector3.Distance(before, root.position) > .1f, "employee moves through shared movement path");
            var controller = root.GetComponent<CharacterController>();
            controller.enabled = false; root.position = new Vector3(0, .05f, 16); controller.enabled = true;
            Physics.SyncTransforms();
            for (int step = 0; step < 4; step++) Call(worker, "Step", .25f, new Vector2(0, 1), Vector2.zero);
            Check(root.position.z < 16.7f, "employee cannot walk through rear wall");
            demo.SetExteriorView(false);
            Physics.SyncTransforms();
            Check(Physics.Raycast(new Vector3(0, 1, 16), Vector3.forward, 2), "interior view retains physical rear wall");
            Call(worker, "ExitWorker");
            Check(!(bool)Get(worker, "IsWorkerMode") && observation.enabled, "observation camera restored on exit");
            Physics.SyncTransforms();
            Check(Physics.Raycast(new Vector3(0, 1, 16), Vector3.forward, 2), "cutaway overview retains independent building collisions");
            // Capture actual imported factory geometry, excluding explanatory overlays.
            var node = demo.transform.Find("MES equipment").GetChild(0);
            var pda = (Camera)Get(worker, "PdaCamera");
            pda.transform.position = node.position + new Vector3(0, 2, -6);
            pda.transform.LookAt(node.position + Vector3.up);
            demo.SetExteriorView(true);
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
            var savedBytes = File.ReadAllBytes(saved);
            File.WriteAllBytes(saved, new byte[16]);
            Check(!(bool)Call(capture, "Save") && !(bool)Get(capture, "PreviewSaved"), "corrupt existing photo is not accepted as a successful save");
            File.WriteAllBytes(saved, savedBytes);
            Check((bool)Call(capture, "Save"), "restored saved photo validates successfully");
            ((System.Collections.IList)Get(capture, "Gallery")).Clear(); Call(capture, "RefreshGallery");
            Check(((System.Collections.IList)Get(capture, "Gallery")).Count == 1, "gallery reloads completed disk captures");
            File.Copy(saved, Path.Combine(dir, "worker-pda-capture.png"), true);
            observation.transform.position = root.position + new Vector3(2, 1.8f, -3);
            observation.transform.LookAt(root.position + Vector3.up);
            FactoryChecks.Capture(Path.Combine(dir, "worker-character.png"));
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
            Check((bool)Call(capture, "RenderLivePreview") && ((RenderTexture)Get(capture, "LivePreview")).width == 320,
                "PDA live preview renders using configured photo dimensions");
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
            SessionState.SetBool("ShiftLink.WorkerPlayCheck", true);
            SessionState.SetFloat("ShiftLink.WorkerPlayStart", (float)EditorApplication.timeSinceStartup);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            EditorApplication.update += CheckPlay;
            EditorApplication.EnterPlaymode();
        } catch (Exception error) {
            File.WriteAllText(Path.Combine(dir, "worker-check-result.txt"), "FAIL: " + error);
            Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
    static void CheckPlay()
    {
        if (!SessionState.GetBool("ShiftLink.WorkerPlayCheck", false)) return;
        try {
            if (EditorApplication.timeSinceStartup - SessionState.GetFloat("ShiftLink.WorkerPlayStart", 0) > 90)
                throw new Exception("Employee Play Mode check timed out");
            if (!Application.isPlaying) return;
            if (playFactory == null) {
                playDir = Path.GetFullPath(Path.Combine(Application.dataPath, "../Checks"));
                var config = JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(playDir, "config.json"))).config;
                playFactory = new GameObject("Employee Play Mode check").AddComponent<FactoryDemo>();
                playFactory.enabled = false; // Fixture-only check; no network or MES control.
                playFactory.CreateEnvironment(); playFactory.Build(config);
                playWorker = playFactory.GetComponent(typeof(FactoryDemo).Assembly.GetType("FactoryWorker"));
                playCapture = playFactory.GetComponent(typeof(FactoryDemo).Assembly.GetType("FactoryCapture"));
                Set(playCapture, "outputDirectory", Path.Combine(playDir, "worker-play-captures"));
                Set(playCapture, "width", 640); Set(playCapture, "height", 360);
                Call(playWorker, "EnterWorker");
                return;
            }
            if (++playFrames < 5) return;
            if (!screenshotRequested) {
                var workerRoot = (Transform)Get(playWorker, "WorkerRoot");
                Vector3 before = workerRoot.position;
                Call(playWorker, "TogglePda");
                Call(playWorker, "Step", .5f, Vector2.up, Vector2.one);
                Check(Vector3.Distance(before, workerRoot.position) < .0001f, "PDA freezes employee movement in Play Mode");
                Check((bool)Call(playCapture, "RenderLivePreview"), "PDA preview renders in Play Mode");
                var timer = System.Diagnostics.Stopwatch.StartNew();
                Check((bool)Call(playCapture, "Capture") && (bool)Call(playCapture, "Save"), "PDA capture/save works in actual Play Mode");
                timer.Stop();
                File.WriteAllText(Path.Combine(playDir, "worker-play-timing.json"), "{\"capture_save_ms\":" + timer.ElapsedMilliseconds + ",\"width\":640,\"height\":360,\"samples\":1}");
                ScreenCapture.CaptureScreenshot(Path.Combine(playDir, "worker-pda-ui.png"));
                screenshotRequested = true;
                return;
            }
            if (playFrames < 12) return;
            ((Behaviour)playWorker).enabled = false;
            Check(!(bool)Get(playWorker, "IsWorkerMode") && Camera.main.enabled, "disabling employee component restores observation mode");
            File.WriteAllText(Path.Combine(playDir, "worker-play-check-result.txt"), "PASS: actual Play Mode employee/PDA input isolation/live preview/capture/save/disable restoration");
            SessionState.SetBool("ShiftLink.WorkerPlayCheck", false);
            Debug.Log("SHIFTLINK WORKER PLAY CHECK PASS"); EditorApplication.Exit(0);
        } catch (Exception error) {
            SessionState.SetBool("ShiftLink.WorkerPlayCheck", false);
            Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
}
