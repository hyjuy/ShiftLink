using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

// Schematic equipment geometry; MES remains the authority for process state.
public sealed class MesSceneBootstrap : MonoBehaviour
{
    [Serializable] public class Envelope { public string source_mode; public bool is_synthetic; public Config config; }
    [Serializable] public class Config {
        public string config_id, line_id;
        public Equipment[] equipment;
        public string[] route;
        public Relation[] relations, branches;
    }
    [Serializable] public class Equipment {
        public string equipment_id, asset_id, code, name, profile_id;
        public bool active = true;
    }
    [Serializable] public class Relation { public string relation_type, from_id, to_id; }
    [Serializable] public class State {
        public string config_id, line_mode;
        public int sequence;
        public EquipmentState[] equipment;
        public Coil[] coils;
    }
    [Serializable] public class EquipmentState {
        public string equipment_id, operating_state, fault_level, wait_reason;
    }
    [Serializable] public class Coil {
        public string coil_id, equipment_id, quality_status;
        public float position;
    }
    sealed class View {
        public Equipment data;
        public Transform root;
        public Renderer lamp;
        public TextMesh label;
        public EquipmentState state;
    }

    public string mesBaseUrl = "http://127.0.0.1:8000";
    public float pollSeconds = 1f;
    readonly Dictionary<string, View> views = new Dictionary<string, View>();
    readonly Dictionary<string, GameObject> coils = new Dictionary<string, GameObject>();
    readonly List<Material> materials = new List<Material>();
    readonly MaterialPropertyBlock colors = new MaterialPropertyBlock();
    Config config;
    Camera cameraView;
    View selected;
    string connection = "Not connected", sourceMode;
    float yaw, pitch = 15;
    Vector3 lastMouse;
    Material body, metal, dark;

    void Start()
    {
        try {
            var asset = Resources.Load<TextAsset>("mes-config");
            if (!asset) throw new Exception("Missing Resources/mes-config.json; run export_unity_mes.py");
            var envelope = JsonUtility.FromJson<Envelope>(asset.text);
            if (envelope == null || !envelope.is_synthetic) throw new Exception("Expected a synthetic MES export");
            config = envelope.config;
            sourceMode = envelope.source_mode;
            if (config == null || config.equipment == null || config.route == null)
                throw new Exception("Invalid MES configuration");
            var ids = new HashSet<string>();
            foreach (var e in config.equipment)
                if (e == null || String.IsNullOrEmpty(e.equipment_id) || !ids.Add(e.equipment_id))
                    throw new Exception("Missing or duplicate equipment ID");
            foreach (var id in config.route)
                if (!ids.Contains(id)) throw new Exception("Unknown route equipment: " + id);
            body = MaterialFor(new Color(.25f, .45f, .58f));
            metal = MaterialFor(new Color(.6f, .65f, .68f));
            dark = MaterialFor(new Color(.12f, .16f, .19f));
            Build();
            StartCoroutine(Poll());
        } catch (Exception ex) {
            connection = ex.Message;
            Debug.LogError(ex);
        }
    }

    Material MaterialFor(Color color)
    {
        var shader = Shader.Find("Standard");
        if (!shader) throw new Exception("Use the Built-in Render Pipeline for this scene");
        var material = new Material(shader);
        material.color = color;
        materials.Add(material);
        return material;
    }

    GameObject Part(Transform parent, string name, PrimitiveType type, Vector3 position,
                    Vector3 scale, Material material)
    {
        var o = GameObject.CreatePrimitive(type);
        o.name = name;
        o.transform.SetParent(parent, false);
        o.transform.localPosition = position;
        o.transform.localScale = scale;
        o.GetComponent<Renderer>().sharedMaterial = material;
        return o;
    }

    void Build()
    {
        var positions = new Dictionary<string, Vector3>();
        for (int i = 0; i < config.route.Length; i++)
            positions[config.route[i]] = new Vector3(i * 6, 0, 0);
        // Resolve branch chains independently of their order in the API.
        int branch = 0;
        for (int pass = 0; pass < config.equipment.Length; pass++) {
            bool added = false;
            foreach (var r in config.branches ?? new Relation[0])
                if (!positions.ContainsKey(r.to_id) && positions.TryGetValue(r.from_id, out var p)) {
                    positions[r.to_id] = p + new Vector3(3, 0, 6 * (++branch));
                    added = true;
                }
            if (!added) break;
        }
        int utility = 0;
        foreach (var e in config.equipment) {
            if (!positions.TryGetValue(e.equipment_id, out var p))
                p = new Vector3((utility++) * 5, 0, -7);
            var root = new GameObject(e.code + " " + e.equipment_id).transform;
            root.SetParent(transform, false);
            root.localPosition = p;
            Geometry(root, e.code ?? e.profile_id ?? "");
            var lamp = Part(root, "MES status", PrimitiveType.Sphere,
                            new Vector3(0, 2.6f, 0), Vector3.one * .3f, metal).GetComponent<Renderer>();
            SetColor(lamp, Color.gray);
            var label = new GameObject("Label").AddComponent<TextMesh>();
            label.transform.SetParent(root, false);
            label.transform.localPosition = new Vector3(0, 3.15f, 0);
            label.anchor = TextAnchor.MiddleCenter;
            label.fontSize = 48;
            label.characterSize = .075f;
            label.text = e.code + "\n" + e.equipment_id + (e.active ? "" : " (inactive)");
            label.color = Color.white;
            views.Add(e.equipment_id, new View { data = e, root = root, lamp = lamp, label = label });
        }
        int index = 0;
        var relations = new List<Relation>(config.relations ?? new Relation[0]);
        relations.AddRange(config.branches ?? new Relation[0]);
        foreach (var r in relations) {
            if (!views.TryGetValue(r.from_id, out var a) || !views.TryGetValue(r.to_id, out var b)) continue;
            var o = new GameObject(r.relation_type + ": " + r.from_id + " -> " + r.to_id);
            o.transform.SetParent(transform, false);
            var line = o.AddComponent<LineRenderer>();
            Color color = r.relation_type == "material_flow" ? Color.cyan :
                          r.relation_type == "power_supply" ? Color.yellow : Color.magenta;
            line.sharedMaterial = MaterialFor(color);
            line.positionCount = 2;
            line.startWidth = line.endWidth = .10f;
            float height = .06f + (index++ % 4) * .06f;
            var start = a.root.position + Vector3.up * height;
            var end = b.root.position + Vector3.up * height;
            line.SetPositions(new[] { start, end });
            if (r.relation_type == "material_flow" && start != end) {
                var arrow = Part(transform, "Flow direction", PrimitiveType.Cube,
                    Vector3.Lerp(start, end, .7f), new Vector3(.35f, .12f, .8f), line.sharedMaterial);
                arrow.transform.rotation = Quaternion.LookRotation(end - start);
            }
        }
        float maxX = 24, maxZ = 10;
        foreach (var v in views.Values) { maxX = Mathf.Max(maxX, v.root.position.x); maxZ = Mathf.Max(maxZ, v.root.position.z); }
        Part(transform, "Factory floor", PrimitiveType.Cube, new Vector3(maxX / 2, -.2f, (maxZ - 10) / 2),
             new Vector3(maxX + 16, .3f, maxZ + 26), dark);
        var lightObject = new GameObject("Factory light");
        lightObject.transform.SetParent(transform, false);
        var light = lightObject.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.2f;
        light.transform.rotation = Quaternion.Euler(45, -30, 0);
        RenderSettings.ambientLight = new Color(.45f, .45f, .45f);
        cameraView = Camera.main;
        if (!cameraView) {
            var o = new GameObject("Main Camera");
            o.transform.SetParent(transform, false);
            o.tag = "MainCamera";
            cameraView = o.AddComponent<Camera>();
        }
        cameraView.transform.position = new Vector3(8, 8, -16);
        cameraView.transform.rotation = Quaternion.Euler(pitch, yaw, 0);
        cameraView.farClipPlane = 300;
        cameraView.backgroundColor = new Color(.08f, .11f, .15f);
    }

    void Geometry(Transform root, string code)
    {
        string type = code.Split('-')[0].ToUpperInvariant();
        Part(root, "Base", PrimitiveType.Cube, new Vector3(0, .15f, 0), new Vector3(3, .3f, 2), metal);
        if (type == "RT") {
            for (int i = 0; i < 7; i++) {
                var roller = Part(root, "Roller", PrimitiveType.Cylinder,
                    new Vector3(-1.35f + i * .45f, .8f, 0), new Vector3(.32f, 1, .32f), metal);
                roller.transform.localRotation = Quaternion.Euler(90, 0, 0);
            }
            Part(root, "Drive", PrimitiveType.Cube, new Vector3(1.35f, .6f, 1.2f), new Vector3(.65f, .7f, .6f), body);
        } else if (type == "CV") {
            Part(root, "Belt", PrimitiveType.Cube, new Vector3(0, .8f, 0), new Vector3(2.8f, .25f, 1.8f), dark);
            Part(root, "Left rail", PrimitiveType.Cube, new Vector3(0, 1, -1), new Vector3(3, .2f, .1f), metal);
            Part(root, "Right rail", PrimitiveType.Cube, new Vector3(0, 1, 1), new Vector3(3, .2f, .1f), metal);
        } else if (type == "HPU") {
            Part(root, "Reservoir", PrimitiveType.Cube, new Vector3(0, .7f, 0), new Vector3(2.5f, 1.1f, 1.6f), body);
            Part(root, "Motor", PrimitiveType.Cylinder, new Vector3(.7f, 1.6f, 0), new Vector3(.6f, .4f, .6f), metal);
            Part(root, "Pump", PrimitiveType.Cube, new Vector3(-.6f, 1.45f, 0), new Vector3(.6f, .5f, .6f), dark);
        } else if (type == "PDP") {
            Part(root, "Cabinet", PrimitiveType.Cube, new Vector3(0, 1.2f, 0), new Vector3(2, 2.1f, .7f), body);
            Part(root, "Panel", PrimitiveType.Cube, new Vector3(0, 1.5f, -.38f), new Vector3(.8f, .5f, .05f), dark);
        } else if (type == "CAU") {
            var tank = Part(root, "Air tank", PrimitiveType.Cylinder, new Vector3(0, .75f, 0),
                            new Vector3(1.1f, 1.3f, 1.1f), body);
            tank.transform.localRotation = Quaternion.Euler(0, 0, 90);
            Part(root, "Compressor", PrimitiveType.Cube, new Vector3(0, 1.5f, 0), new Vector3(1.3f, .65f, .8f), metal);
        } else if (type == "GR") {
            Part(root, "Gearbox", PrimitiveType.Cube, new Vector3(0, .85f, 0), new Vector3(1.4f, 1.4f, 1.1f), body);
            var shaft = Part(root, "Shaft", PrimitiveType.Cylinder, new Vector3(0, .9f, 0),
                             new Vector3(.3f, 1.5f, .3f), metal);
            shaft.transform.localRotation = Quaternion.Euler(90, 0, 0);
        } else {
            Part(root, "Generic equipment", PrimitiveType.Cube, new Vector3(0, 1.05f, 0),
                 new Vector3(2, 1.8f, 1.5f), body);
        }
    }

    void Update()
    {
        if (!cameraView) return;
        var t = cameraView.transform;
        if (Input.GetMouseButtonDown(1)) lastMouse = Input.mousePosition;
        if (Input.GetMouseButton(1)) {
            var delta = Input.mousePosition - lastMouse;
            lastMouse = Input.mousePosition;
            yaw += delta.x * .15f;
            pitch = Mathf.Clamp(pitch - delta.y * .15f, -80, 80);
            t.rotation = Quaternion.Euler(pitch, yaw, 0);
        }
        Vector3 movement = Vector3.zero;
        if (Input.GetKey(KeyCode.W)) movement += t.forward;
        if (Input.GetKey(KeyCode.S)) movement -= t.forward;
        if (Input.GetKey(KeyCode.D)) movement += t.right;
        if (Input.GetKey(KeyCode.A)) movement -= t.right;
        if (Input.GetKey(KeyCode.E)) movement += Vector3.up;
        if (Input.GetKey(KeyCode.Q)) movement -= Vector3.up;
        t.position += Vector3.ClampMagnitude(movement, 1) * Time.deltaTime * (Input.GetKey(KeyCode.LeftShift) ? 12 : 5);
        if (Input.GetMouseButtonDown(0) && !(Input.mousePosition.x < 720 && Input.mousePosition.y > Screen.height - 160))
            if (Physics.Raycast(cameraView.ScreenPointToRay(Input.mousePosition), out var hit, 200))
                foreach (var v in views.Values)
                    if (hit.transform.IsChildOf(v.root)) { selected = v; break; }
        foreach (var v in views.Values)
            v.label.transform.rotation = Quaternion.LookRotation(v.label.transform.position - t.position);
    }

    IEnumerator Poll()
    {
        while (true) {
            using (var request = UnityWebRequest.Get(mesBaseUrl.TrimEnd('/') + "/api/state")) {
                request.timeout = 5;
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success) {
                    connection = "MES disconnected: " + request.error;
                    ClearState();
                } else {
                    try { Apply(JsonUtility.FromJson<State>(request.downloadHandler.text)); }
                    catch (Exception ex) {
                        connection = "MES data error: " + ex.Message;
                        ClearState();
                        Debug.LogWarning(connection);
                    }
                }
            }
            yield return new WaitForSeconds(Mathf.Max(.2f, pollSeconds));
        }
    }

    void ClearState()
    {
        foreach (var v in views.Values) { v.state = null; SetColor(v.lamp, Color.gray); }
        foreach (var o in coils.Values) o.SetActive(false);
    }

    void Apply(State state)
    {
        ClearState();
        if (state == null || state.equipment == null || state.coils == null)
            throw new Exception("Missing equipment/coils");
        if (state.config_id != config.config_id) {
            connection = "MES config changed; stop Play, re-export --mes-url, restart";
            return;
        }
        connection = "MES sequence " + state.sequence + " | " + state.line_mode;
        foreach (var s in state.equipment)
            if (views.TryGetValue(s.equipment_id, out var v) && v.data.active) {
                v.state = s;
                SetColor(v.lamp, s.fault_level != "normal" ? Color.red :
                         s.operating_state == "running" ? Color.green :
                         s.operating_state == "waiting" ? Color.yellow : Color.gray);
            }
        var present = new HashSet<string>();
        foreach (var c in state.coils) {
            if (!views.TryGetValue(c.equipment_id, out var v) || !v.data.active) continue;
            present.Add(c.coil_id);
            if (!coils.TryGetValue(c.coil_id, out var o)) {
                o = Part(transform, c.coil_id, PrimitiveType.Cylinder, Vector3.zero,
                         new Vector3(1.2f, .55f, 1.2f), metal);
                coils.Add(c.coil_id, o);
            }
            // position is MES progress within the current station, not toward the next station.
            o.SetActive(true);
            o.transform.position = v.root.position + new Vector3((Mathf.Clamp01(c.position) - .5f) * 2.5f, 1.3f, 0);
            o.transform.rotation = Quaternion.Euler(90, 0, 0);
            SetColor(o.GetComponent<Renderer>(), c.quality_status == "hold" ? Color.red : Color.white);
        }
        var removed = new List<string>();
        foreach (var pair in coils)
            if (!present.Contains(pair.Key)) { Destroy(pair.Value); removed.Add(pair.Key); }
        foreach (var id in removed) coils.Remove(id);
    }

    void SetColor(Renderer renderer, Color color)
    {
        renderer.GetPropertyBlock(colors);
        colors.SetColor("_Color", color);
        renderer.SetPropertyBlock(colors);
    }

    void OnGUI()
    {
        GUI.Box(new Rect(10, 10, 700, 140), "ShiftLink | Synthetic manufacturing scene | Schematic geometry");
        GUI.Label(new Rect(25, 35, 670, 25), connection + " | source: " + sourceMode);
        GUI.Label(new Rect(25, 60, 670, 25), "WASD move | Q/E height | RMB look | Shift speed | Click: scene metadata");
        if (selected != null) {
            var s = selected.state;
            GUI.Label(new Rect(25, 85, 670, 25), selected.data.code + " / " + selected.data.equipment_id +
                      " / " + selected.data.asset_id);
            GUI.Label(new Rect(25, 110, 670, 25), s == null ? "Unknown (no live state)" :
                      s.operating_state + " / " + s.fault_level + " / " + s.wait_reason);
        }
    }

    void OnDestroy()
    {
        StopAllCoroutines();
        foreach (var material in materials) if (material) Destroy(material);
    }
}

