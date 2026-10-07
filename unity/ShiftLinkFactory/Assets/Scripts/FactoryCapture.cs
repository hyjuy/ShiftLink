using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

[Serializable] public class FactoryCameraPose {
    public float[] position, rotation;
    public float field_of_view, near_clip, far_clip;
}
[Serializable] public class FactoryCaptureObject {
    public int class_id;
    public string equipment_type, equipment_id;
    public float[] bbox_xyxy;
}
[Serializable] public class FactoryCaptureMetadata {
    public int schema_version = 1, seed, image_width, image_height, sequence;
    public string capture_id, session_id, scene_id, captured_at, config_id, run_id;
    public string bbox_convention = "top-left xyxy exclusive", annotation_source = "visible-instance-mask";
    public FactoryCameraPose camera_pose;
    public FactoryCaptureObject[] objects;
}

// One synchronous capture holds scene transforms constant across RGB and instance-ID passes.
public class FactoryCapture : MonoBehaviour
{
    public string outputDirectory = "", sceneId = "factory-default", sessionId = "";
    public int width = 1280, height = 720;
    public Transform[] excludedRoots = new Transform[0];
    public Texture2D Preview { get; private set; }
    public FactoryCaptureMetadata PreviewMetadata { get; private set; }
    public bool HasPreview { get { return Preview != null && PreviewMetadata != null; } }
    public string LastSavedPath { get; private set; }
    public string Status { get; private set; } = "Ready to photograph";
    public bool PreviewSaved { get; private set; }
    public readonly List<string> Gallery = new List<string>();
    Camera cameraSource;
    FactoryConfig config;
    Dictionary<string, GameObject> equipment = new Dictionary<string, GameObject>();
    int seed, sequence = -1;
    string configId, runId;
    static readonly string[] Classes = { "HPU", "GR", "RT", "CV", "CAU", "PDP" };

    public void Configure(Camera camera, FactoryConfig next, IDictionary<string, GameObject> nodes, int captureSeed = 0)
    {
        cameraSource = camera; config = next; seed = captureSeed;
        configId = next == null ? null : next.config_id;
        equipment = nodes == null ? new Dictionary<string, GameObject>() : new Dictionary<string, GameObject>(nodes);
        if (string.IsNullOrEmpty(sessionId)) sessionId = Guid.NewGuid().ToString("N");
    }
    public void SetContext(string currentConfigId, string currentRunId, int currentSequence)
    { configId = currentConfigId; runId = currentRunId; sequence = currentSequence; }

    bool Excluded(Renderer renderer)
    {
        if (renderer.GetComponent<TextMesh>() != null) return true;
        if (excludedRoots != null && excludedRoots.Any(root => root != null && (renderer.transform == root || renderer.transform.IsChildOf(root)))) return true;
        // Factory explanatory display is not part of equipment appearance.
        for (var node = renderer.transform; node != null; node = node.parent)
            if (node.name == "Factory status display") return true;
        return false;
    }
    static void Remove(UnityEngine.Object value)
    { if (value == null) return; if (Application.isPlaying) Destroy(value); else DestroyImmediate(value); }
    Texture2D Read(RenderTexture target, bool linear)
    {
        cameraSource.targetTexture = target;
        cameraSource.Render();
        RenderTexture.active = target;
        var texture = new Texture2D(width, height, TextureFormat.RGB24, false, linear);
        texture.ReadPixels(new Rect(0, 0, width, height), 0, 0); texture.Apply();
        return texture;
    }

    public bool Capture()
    {
        if (cameraSource == null || width < 1 || height < 1 || width > 8192 || height > 8192) {
            Status = "Capture unavailable: check camera and image dimensions"; return false;
        }
        Shader shader = Resources.Load<Shader>("FactoryInstanceMask");
        if (shader == null) { Status = "Capture unavailable: instance mask shader missing"; return false; }
        var renderers = FindObjectsByType<Renderer>(FindObjectsSortMode.None).Where(r => r.enabled && r.gameObject.activeInHierarchy).ToArray();
        var hidden = renderers.Where(Excluded).ToArray();
        var materialsBefore = new Dictionary<Renderer, Material[]>();
        var maskMaterials = new List<Material>();
        var previousTarget = cameraSource.targetTexture;
        var previousActive = RenderTexture.active;
        var previousClear = cameraSource.clearFlags;
        var previousColor = cameraSource.backgroundColor;
        bool previousHdr = cameraSource.allowHDR, previousMsaa = cameraSource.allowMSAA;
        float previousAspect = cameraSource.aspect;
        RenderTexture rgbTarget = null, maskTarget = null;
        Texture2D rgb = null, mask = null;
        try {
            foreach (var renderer in hidden) renderer.enabled = false;
            cameraSource.aspect = (float)width / height;
            cameraSource.allowHDR = false; cameraSource.allowMSAA = false;
            rgbTarget = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rgbTarget.antiAliasing = 1; rgbTarget.Create(); rgb = Read(rgbTarget, false);
            var candidates = config == null || config.equipment == null ? new EquipmentSpec[0] :
                config.equipment.Where(e => e != null && e.active && equipment.ContainsKey(e.equipment_id) && equipment[e.equipment_id] != null && equipment[e.equipment_id].activeInHierarchy).ToArray();
            var rendererIds = new Dictionary<Renderer, int>();
            for (int index = 0; index < candidates.Length; index++) {
                string type = (candidates[index].profile_id ?? "").ToUpperInvariant();
                if (Array.IndexOf(Classes, type) < 0) throw new InvalidOperationException("Unknown equipment type: " + type);
                foreach (var renderer in equipment[candidates[index].equipment_id].GetComponentsInChildren<Renderer>()) rendererIds[renderer] = index + 1;
            }
            var palette = new Dictionary<int, Material>();
            foreach (var renderer in renderers.Where(r => r.enabled)) {
                int id; if (!rendererIds.TryGetValue(renderer, out id)) id = 0;
                Material material;
                if (!palette.TryGetValue(id, out material)) {
                    material = new Material(shader);
                    material.SetVector("_Color", new Vector4((id & 255) / 255f, ((id >> 8) & 255) / 255f, ((id >> 16) & 255) / 255f, 1));
                    palette[id] = material; maskMaterials.Add(material);
                }
                materialsBefore[renderer] = renderer.sharedMaterials;
                renderer.sharedMaterials = Enumerable.Repeat(material, renderer.sharedMaterials.Length).ToArray();
            }
            cameraSource.clearFlags = CameraClearFlags.SolidColor; cameraSource.backgroundColor = Color.black;
            maskTarget = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            maskTarget.antiAliasing = 1; maskTarget.Create(); mask = Read(maskTarget, true);
            var boxes = new Dictionary<int, int[]>();
            var pixels = mask.GetPixels32();
            for (int offset = 0; offset < pixels.Length; offset++) {
                var color = pixels[offset]; int id = color.r | color.g << 8 | color.b << 16;
                if (id < 1 || id > candidates.Length) continue;
                int x = offset % width, y = height - 1 - offset / width;
                int[] box;
                if (!boxes.TryGetValue(id, out box)) boxes[id] = new[] { x, y, x + 1, y + 1 };
                else { box[0] = Math.Min(box[0], x); box[1] = Math.Min(box[1], y); box[2] = Math.Max(box[2], x + 1); box[3] = Math.Max(box[3], y + 1); }
            }
            var annotations = boxes.OrderBy(pair => pair.Key).Select(pair => {
                var spec = candidates[pair.Key - 1]; string type = spec.profile_id.ToUpperInvariant();
                return new FactoryCaptureObject { class_id = Array.IndexOf(Classes, type), equipment_type = type, equipment_id = spec.equipment_id, bbox_xyxy = pair.Value.Select(value => (float)value).ToArray() };
            }).ToArray();
            Vector3 position = cameraSource.transform.position; Quaternion rotation = cameraSource.transform.rotation;
            var metadata = new FactoryCaptureMetadata {
                capture_id = Guid.NewGuid().ToString("N"), session_id = sessionId, scene_id = sceneId, seed = seed,
                captured_at = DateTime.UtcNow.ToString("o"), image_width = width, image_height = height,
                config_id = configId, run_id = runId, sequence = sequence, objects = annotations,
                camera_pose = new FactoryCameraPose { position = new[] { position.x, position.y, position.z }, rotation = new[] { rotation.x, rotation.y, rotation.z, rotation.w }, field_of_view = cameraSource.fieldOfView, near_clip = cameraSource.nearClipPlane, far_clip = cameraSource.farClipPlane }
            };
            if (string.IsNullOrEmpty(metadata.session_id)) metadata.session_id = sessionId = Guid.NewGuid().ToString("N");
            Remove(Preview); Preview = rgb; rgb = null; PreviewMetadata = metadata; PreviewSaved = false;
            Status = "Photo ready. Save or retake."; return true;
        } catch (Exception error) { Status = "Capture failed: " + error.Message; Debug.LogWarning(Status); return false; }
        finally {
            foreach (var pair in materialsBefore) if (pair.Key != null) pair.Key.sharedMaterials = pair.Value;
            foreach (var renderer in hidden) if (renderer != null) renderer.enabled = true;
            cameraSource.targetTexture = previousTarget; cameraSource.aspect = previousAspect;
            cameraSource.clearFlags = previousClear; cameraSource.backgroundColor = previousColor;
            cameraSource.allowHDR = previousHdr; cameraSource.allowMSAA = previousMsaa; RenderTexture.active = previousActive;
            Remove(rgb); Remove(mask); Remove(rgbTarget); Remove(maskTarget);
            foreach (var material in maskMaterials) Remove(material);
        }
    }

    public bool Save()
    {
        if (!HasPreview) { Status = "Take a photo first."; return false; }
        string png = null, json = null, pngTemp = null, jsonTemp = null;
        bool movedPng = false;
        try {
            string directory = string.IsNullOrWhiteSpace(outputDirectory) ? Path.Combine(Application.persistentDataPath, "ShiftLinkCaptures") : Path.GetFullPath(outputDirectory);
            Directory.CreateDirectory(directory);
            png = Path.Combine(directory, PreviewMetadata.capture_id + ".png"); json = Path.ChangeExtension(png, ".json");
            if (File.Exists(png) || File.Exists(json)) {
                if (!File.Exists(png) || !File.Exists(json)) throw new IOException("Incomplete capture exists; choose another output directory.");
                var existing = JsonUtility.FromJson<FactoryCaptureMetadata>(File.ReadAllText(json));
                if (existing == null || existing.capture_id != PreviewMetadata.capture_id || new FileInfo(png).Length < 8) throw new IOException("Capture ID collision.");
            } else {
                pngTemp = png + ".tmp"; jsonTemp = json + ".tmp";
                File.WriteAllBytes(pngTemp, Preview.EncodeToPNG());
                File.WriteAllText(jsonTemp, JsonUtility.ToJson(PreviewMetadata, true), new System.Text.UTF8Encoding(false));
                File.Move(pngTemp, png); movedPng = true; File.Move(jsonTemp, json); movedPng = false;
            }
            LastSavedPath = png; PreviewSaved = true;
            if (!Gallery.Contains(png)) Gallery.Add(png);
            Status = "Photo saved: " + png; return true;
        } catch (Exception error) {
            if (movedPng && png != null) TryDelete(png);
            Status = "Save failed. Photo kept for retry: " + error.Message; Debug.LogWarning(Status); return false;
        } finally { TryDelete(pngTemp); TryDelete(jsonTemp); }
    }
    static void TryDelete(string path)
    { if (path == null) return; try { if (File.Exists(path)) File.Delete(path); } catch (IOException) { } catch (UnauthorizedAccessException) { } }
    public void Retake() { Remove(Preview); Preview = null; PreviewMetadata = null; PreviewSaved = false; Status = "Ready to photograph"; }
    void OnDestroy() { Remove(Preview); }
}
