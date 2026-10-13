using System;
using System.Collections.Generic;
using UnityEngine;

// Small built-in employee controller: no external character or camera packages.
public class FactoryWorker : MonoBehaviour
{
    public float speed = 2.2f, lookSensitivity = 2f;
    public bool IsWorkerMode { get; private set; }
    public bool PdaRaised { get; private set; }
    public Transform WorkerRoot { get; private set; }
    public Camera PdaCamera { get; private set; }
    public bool ThirdPerson { get; private set; }
    CharacterController controller;
    Camera observation, employeeView;
    FactoryDemo demo;
    FactoryCapture capture;
    FactoryCameraStream cameraStream;
    Renderer[] bodyRenderers = new Renderer[0];
    Transform body, leftLeg, rightLeg, pda, rightArm;
    float yaw, pitch, verticalSpeed, walkCycle;
    bool galleryOpen;
    Texture2D galleryImage;
    string galleryPath;
    Vector2 pdaScroll;
    string galleryStatus = "";
    CursorLockMode previousLock;
    bool previousCursor;
    readonly List<Material> materials = new List<Material>();
    Rect panel;
    Vector2 galleryScroll;

    static void Remove(UnityEngine.Object value)
    { if (value == null) return; if (Application.isPlaying) Destroy(value); else DestroyImmediate(value); }
    Transform Shape(string name, PrimitiveType type, Transform parent, Vector3 position, Vector3 scale, Color color)
    {
        var obj = GameObject.CreatePrimitive(type); obj.name = name; obj.transform.SetParent(parent, false);
        obj.transform.localPosition = position; obj.transform.localScale = scale;
        Remove(obj.GetComponent<Collider>());
        var material = new Material(Shader.Find("Standard")); material.color = color; materials.Add(material);
        obj.GetComponent<Renderer>().sharedMaterial = material; return obj.transform;
    }
    public void Initialize(FactoryDemo factory, Camera observationCamera)
    {
        if (WorkerRoot != null) return;
        demo = factory; observation = observationCamera;
        capture = GetComponent<FactoryCapture>() ?? gameObject.AddComponent<FactoryCapture>();
        WorkerRoot = new GameObject("Factory employee").transform; WorkerRoot.SetParent(transform, false);
        WorkerRoot.position = new Vector3(-16.8f, .05f, -12);
        controller = WorkerRoot.gameObject.AddComponent<CharacterController>();
        controller.height = 1.8f; controller.radius = .28f; controller.center = new Vector3(0, .9f, 0);
        controller.stepOffset = .25f; controller.skinWidth = .035f;
        body = new GameObject("Employee visual").transform; body.SetParent(WorkerRoot, false);
        Color uniform = new Color(.07f, .22f, .44f), skin = new Color(.7f, .48f, .32f), dark = new Color(.06f, .07f, .09f);
        Shape("Work jacket", PrimitiveType.Cube, body, new Vector3(0, 1.12f, 0), new Vector3(.48f, .62f, .28f), uniform);
        Shape("Reflective vest", PrimitiveType.Cube, body, new Vector3(0, 1.15f, -.153f), new Vector3(.42f, .12f, .014f), new Color(.9f, .95f, .4f));
        Shape("Head", PrimitiveType.Sphere, body, new Vector3(0, 1.59f, 0), new Vector3(.27f, .31f, .27f), skin);
        Shape("Safety helmet", PrimitiveType.Sphere, body, new Vector3(0, 1.75f, 0), new Vector3(.33f, .18f, .33f), Color.yellow);
        Shape("Helmet brim", PrimitiveType.Cylinder, body, new Vector3(0, 1.72f, 0), new Vector3(.38f, .022f, .38f), Color.yellow);
        leftLeg = new GameObject("Left leg pivot").transform; leftLeg.SetParent(body, false); leftLeg.localPosition = new Vector3(-.13f, .83f, 0);
        rightLeg = new GameObject("Right leg pivot").transform; rightLeg.SetParent(body, false); rightLeg.localPosition = new Vector3(.13f, .83f, 0);
        foreach (var leg in new[] { leftLeg, rightLeg }) {
            Shape("Work trousers", PrimitiveType.Cube, leg, new Vector3(0, -.33f, 0), new Vector3(.18f, .65f, .22f), uniform);
            Shape("Safety boot", PrimitiveType.Cube, leg, new Vector3(0, -.73f, .035f), new Vector3(.2f, .16f, .32f), dark);
        }
        Shape("Left sleeve", PrimitiveType.Cube, body, new Vector3(-.32f, 1.08f, 0), new Vector3(.16f, .53f, .2f), uniform);
        Shape("Left hand", PrimitiveType.Sphere, body, new Vector3(-.32f, .78f, 0), new Vector3(.15f, .17f, .14f), skin);
        rightArm = new GameObject("PDA arm").transform; rightArm.SetParent(body, false); rightArm.localPosition = new Vector3(.31f, 1.26f, 0);
        Shape("Right sleeve", PrimitiveType.Cube, rightArm, new Vector3(0, -.19f, .12f), new Vector3(.17f, .18f, .4f), uniform);
        Shape("Right hand", PrimitiveType.Sphere, rightArm, new Vector3(0, -.19f, .35f), new Vector3(.15f, .15f, .15f), skin);
        pda = Shape("Handheld PDA", PrimitiveType.Cube, rightArm, new Vector3(0, -.13f, .42f), new Vector3(.16f, .24f, .025f), dark);
        Shape("PDA screen", PrimitiveType.Cube, pda, new Vector3(0, 0, -.55f), new Vector3(.83f, .8f, .07f), new Color(.2f, .55f, .65f));
        employeeView = new GameObject("Employee view camera").AddComponent<Camera>(); employeeView.transform.SetParent(WorkerRoot, false);
        employeeView.nearClipPlane = .05f; employeeView.farClipPlane = 300; employeeView.fieldOfView = 60; employeeView.enabled = false;
        PdaCamera = new GameObject("PDA photo camera").AddComponent<Camera>(); PdaCamera.transform.SetParent(WorkerRoot, false);
        PdaCamera.nearClipPlane = .05f; PdaCamera.farClipPlane = 300; PdaCamera.fieldOfView = 60; PdaCamera.enabled = false;
        bodyRenderers = body.GetComponentsInChildren<Renderer>(true);
        capture.excludedRoots = new[] { WorkerRoot };
        UpdateCameras();
        cameraStream=GetComponent<FactoryCameraStream>()??gameObject.AddComponent<FactoryCameraStream>();
        cameraStream.Initialize(this,capture);
    }
    public void EnterWorker()
    {
        if (WorkerRoot == null || IsWorkerMode) return;
        previousLock = Cursor.lockState; previousCursor = Cursor.visible;
        IsWorkerMode = true; PdaRaised = false;
        if (demo != null) demo.SetExteriorView(false);
        if (observation != null) observation.enabled = false;
        employeeView.enabled = true; UpdateCameras(); UpdateCursor();
    }
    public void ExitWorker()
    {
        if (!IsWorkerMode) return;
        IsWorkerMode = false; PdaRaised = false;
        if (employeeView != null) employeeView.enabled = false;
        if (body != null) foreach (var renderer in bodyRenderers) renderer.enabled = true;
        if (observation != null) observation.enabled = true;
        if (demo != null) demo.SetExteriorView(false);
        Cursor.lockState = previousLock; Cursor.visible = previousCursor;
    }
    public void Step(float seconds, Vector2 movement, Vector2 look)
    {
        if (!IsWorkerMode || PdaRaised || controller == null || seconds <= 0 || float.IsNaN(seconds) || float.IsInfinity(seconds)) return;
        yaw += look.x * lookSensitivity; pitch = Mathf.Clamp(pitch - look.y * lookSensitivity, -75, 75);
        WorkerRoot.rotation = Quaternion.Euler(0, yaw, 0);
        Vector3 direction = WorkerRoot.TransformDirection(new Vector3(movement.x, 0, movement.y).normalized);
        if (controller.isGrounded && verticalSpeed < 0) verticalSpeed = -2;
        verticalSpeed += Physics.gravity.y * seconds;
        controller.Move((direction * speed + Vector3.up * verticalSpeed) * seconds);
        walkCycle += movement.sqrMagnitude > .001f ? seconds * 8 : 0;
        float swing = movement.sqrMagnitude > .001f ? Mathf.Sin(walkCycle) * 22 : 0;
        leftLeg.localRotation = Quaternion.Euler(swing, 0, 0); rightLeg.localRotation = Quaternion.Euler(-swing, 0, 0);
        UpdateCameras();
    }
    void UpdateCameras()
    {
        if (employeeView == null) return;
        rightArm.localPosition = new Vector3(.31f, PdaRaised ? 1.69f : 1.26f, 0);
        // The rear lens faces away from the employee, opposite the visible PDA screen.
        PdaCamera.transform.position = pda.TransformPoint(new Vector3(0, 0, .6f));
        PdaCamera.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
        employeeView.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
        employeeView.transform.localPosition = ThirdPerson ? new Vector3(0, 1.6f, 0) + Quaternion.Euler(pitch, 0, 0) * new Vector3(0, .4f, -3) : new Vector3(0, 1.58f, .12f);
        foreach (var renderer in bodyRenderers) renderer.enabled = !IsWorkerMode || (ThirdPerson && !PdaRaised);
    }
    void UpdateCursor()
    { Cursor.lockState = PdaRaised ? CursorLockMode.None : CursorLockMode.Locked; Cursor.visible = PdaRaised; }
    public void TogglePda()
    {
        if (!IsWorkerMode) return;
        PdaRaised = !PdaRaised; galleryOpen = false; UpdateCameras(); UpdateCursor();
    }
    void Update()
    {
        if (WorkerRoot == null) return;
        if (!PdaRaised && Input.GetKeyDown(KeyCode.F)) { if (IsWorkerMode) ExitWorker(); else EnterWorker(); }
        if (!IsWorkerMode) return;
        if (Input.GetKeyDown(KeyCode.P) || (PdaRaised && Input.GetKeyDown(KeyCode.Escape))) TogglePda();
        if (PdaRaised) { if (!galleryOpen && !capture.HasPreview && cameraStream?.Streaming!=true) capture.RenderLivePreview(); return; }
        if (Input.GetKeyDown(KeyCode.V)) { ThirdPerson = !ThirdPerson; UpdateCameras(); }
        Step(Time.deltaTime, new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")), new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")));
    }
    void OpenGalleryImage(string path)
    {
        Texture2D image = null;
        try {
            image = new Texture2D(2, 2);
            if (!image.LoadImage(System.IO.File.ReadAllBytes(path))) throw new System.IO.IOException("Image unavailable");
            Remove(galleryImage); galleryImage = image; image = null; galleryPath = path; galleryStatus = "";
        } catch (Exception error) { galleryStatus = "사진 열기 실패: " + error.Message; Debug.LogWarning(galleryStatus); }
        finally { Remove(image); }
    }
    void DrawPhoto(Texture image)
    {
        float imageHeight = Mathf.Min(260, Mathf.Max(90, Screen.height - 340));
        Rect rect = GUILayoutUtility.GetRect(0, imageHeight, GUILayout.ExpandWidth(true));
        GUI.DrawTexture(rect, image, ScaleMode.ScaleToFit, false);
    }
    void OnGUI()
    {
        if(!IsWorkerMode || WorkerRoot==null) return;
        var ui=FactoryUi.For(this);
        using(ui.Use()) { DrawGui(); }
    }
    void DrawGui()
    {
        if(WorkerRoot==null || !IsWorkerMode) return;
        var ui=FactoryUi.For(this);
        if(!PdaRaised) {
            GUI.Box(new Rect(16,16,Mathf.Min(320,Screen.width-32),96),"현장 이동\nWASD 이동 · 마우스 시점\nP PDA · V 시점 전환 · F 관제");
            GUI.Label(new Rect(Screen.width/2-5,Screen.height/2-12,20,24),"+");
            return;
        }
        var e=Event.current;
        if(!galleryOpen && !capture.HasPreview && e.type==EventType.KeyDown &&
            (e.keyCode==KeyCode.Space || e.keyCode==KeyCode.Return || e.keyCode==KeyCode.KeypadEnter)) { capture.Capture(); e.Use(); }
        panel=FactoryUi.ScreenLayout.Pda;
        GUI.Box(new Rect(0,0,Screen.width,Screen.height),GUIContent.none);
        GUILayout.BeginArea(panel,GUI.skin.box);
        GUILayout.BeginHorizontal();
        GUILayout.Label("현장 PDA",ui.Heading);
        if(GUILayout.Button("닫기 [P / Esc]",GUILayout.Width(132))) TogglePda();
        GUILayout.EndHorizontal();
        pdaScroll=GUILayout.BeginScrollView(pdaScroll);
        GUILayout.Label(galleryOpen ? "사진 보관함" : capture.HasPreview ? "촬영 결과 확인" : "설비 사진 촬영",ui.Heading);
        GUILayout.Label("촬영 · 저장 기능 / 장비 인식 미연결",ui.Caption);
        if(galleryOpen) {
            GUILayout.Label(string.IsNullOrEmpty(galleryStatus) ? capture.Status : galleryStatus,ui.Caption);
            if(capture.Gallery.Count==0) GUILayout.Label("저장한 사진이 없습니다. 촬영 후 사진을 저장해 주세요.");
            if(galleryImage!=null) DrawPhoto(galleryImage);
            if(!string.IsNullOrEmpty(galleryPath)) GUILayout.Label(System.IO.Path.GetFileName(galleryPath),ui.Caption);
            galleryScroll=GUILayout.BeginScrollView(galleryScroll,GUILayout.Height(120));
            foreach(var path in capture.Gallery)
                if(GUILayout.Button(System.IO.Path.GetFileName(path))) OpenGalleryImage(path);
            GUILayout.EndScrollView();
            if(GUILayout.Button("촬영 화면으로 돌아가기")) galleryOpen=false;
        } else if(capture.HasPreview) {
            DrawPhoto(capture.Preview);
            GUILayout.Label(capture.Status,ui.Caption);
            GUILayout.BeginHorizontal();
            GUI.enabled=!capture.PreviewSaved;
            if(GUILayout.Button(capture.PreviewSaved ? "저장 완료" : "사진 저장",ui.Primary)) capture.Save();
            GUI.enabled=true;
            if(GUILayout.Button("다시 촬영")) capture.Retake();
            GUILayout.EndHorizontal();
        } else {
            if(capture.LivePreview!=null) DrawPhoto(capture.LivePreview);
            GUILayout.Label("P로 PDA를 닫고 시점을 조정하세요.",ui.Caption);
            if(GUILayout.Button("사진 촬영 [Space / Enter]",ui.Primary,GUILayout.Height(44))) capture.Capture();
            GUILayout.Label(capture.Status,ui.Caption);
        }
        GUILayout.Space(8);
        if(!galleryOpen && GUILayout.Button("사진 보관함 ("+capture.Gallery.Count+")")) { capture.RefreshGallery(); galleryOpen=true; }
        GUILayout.EndScrollView();
        GUILayout.EndArea();
    }
    void OnDisable() { ExitWorker(); }
    void OnDestroy()
    {
        ExitWorker();
        Remove(galleryImage); foreach (var material in materials) Remove(material);
        if (WorkerRoot != null) Remove(WorkerRoot.gameObject);
    }
}
