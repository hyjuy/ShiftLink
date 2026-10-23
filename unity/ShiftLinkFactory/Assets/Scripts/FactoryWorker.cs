using System;
using UnityEngine;

// Small built-in employee controller: no external character or camera packages.
public class FactoryWorker : MonoBehaviour
{
    public float speed = 2.2f, runSpeed = 4.4f, jumpHeight = 1.1f, lookSensitivity = 2f;
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
    Transform body;
    FactoryWorkerVisual visual;
    float yaw, pitch, verticalSpeed;
    bool galleryOpen;
    Texture2D galleryImage;
    string galleryPath;
    Vector2 pdaScroll;
    string galleryStatus = "";
    CursorLockMode previousLock;
    bool previousCursor;
    Rect panel;
    Vector2 galleryScroll;

    static void Remove(UnityEngine.Object value)
    { if (value == null) return; if (Application.isPlaying) Destroy(value); else DestroyImmediate(value); }
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
        var prefab = Resources.Load<GameObject>("Factory/WorkerMale");
        if (prefab == null) throw new InvalidOperationException("WorkerMale prefab missing; run FactoryWorkerAssetBuilder.Prepare in the Unity Editor");
        body = Instantiate(prefab, WorkerRoot, false).transform; body.name = "Employee visual";
        visual = body.GetComponent<FactoryWorkerVisual>(); visual.Initialize();
        visual.RunSpeedThreshold = (speed+runSpeed)*.5f;
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
        visual.Advance(0, 0, true, 0, false);
        if (demo != null) demo.SetExteriorView(false);
        if (observation != null) observation.enabled = false;
        employeeView.enabled = true; UpdateCameras(); UpdateCursor();
    }
    public void ExitWorker()
    {
        if (!IsWorkerMode) return;
        IsWorkerMode = false; PdaRaised = false;
        if (visual != null) visual.Advance(0, 0, true, 0, false);
        if (employeeView != null) employeeView.enabled = false;
        if (body != null) foreach (var renderer in bodyRenderers) renderer.enabled = true;
        if (observation != null) observation.enabled = true;
        if (demo != null) demo.SetExteriorView(false);
        Cursor.lockState = previousLock; Cursor.visible = previousCursor;
    }
    public void Step(float seconds, Vector2 movement, Vector2 look)
    { StepMovement(seconds, movement, look, false, false); }
    public void StepMovement(float seconds, Vector2 movement, Vector2 look, bool running, bool jump)
    {
        if (!IsWorkerMode || PdaRaised || controller == null || seconds <= 0 || float.IsNaN(seconds) || float.IsInfinity(seconds)) return;
        yaw += look.x * lookSensitivity; pitch = Mathf.Clamp(pitch - look.y * lookSensitivity, -75, 75);
        WorkerRoot.rotation = Quaternion.Euler(0, yaw, 0);
        Vector3 direction = WorkerRoot.TransformDirection(new Vector3(movement.x, 0, movement.y).normalized);
        bool grounded = controller.isGrounded;
        if (grounded && verticalSpeed < 0) verticalSpeed = -2;
        if (grounded && jump) verticalSpeed = Mathf.Sqrt(-2 * Physics.gravity.y * jumpHeight);
        verticalSpeed += Physics.gravity.y * seconds;
        float moveSpeed = running ? runSpeed : speed;
        Vector3 before = WorkerRoot.position;
        var collisions = controller.Move((direction * moveSpeed + Vector3.up * verticalSpeed) * seconds);
        if ((collisions & CollisionFlags.Above) != 0 && verticalSpeed > 0) verticalSpeed = 0;
        Vector3 travelled = WorkerRoot.position-before; travelled.y = 0;
        visual.RunSpeedThreshold = (speed+runSpeed)*.5f;
        visual.Advance(seconds, travelled.magnitude/seconds, controller.isGrounded, verticalSpeed, false);
        UpdateCameras();
    }
    void UpdateCameras()
    {
        if (employeeView == null) return;
        // The rear lens faces away from the employee, opposite the visible PDA screen.
        PdaCamera.transform.position = visual.PhotoLens.position;
        PdaCamera.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
        employeeView.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
        employeeView.transform.localPosition = ThirdPerson ? new Vector3(0, 1.1f, 0) + Quaternion.Euler(pitch, 0, 0) * new Vector3(0, .25f, -2.6f) : new Vector3(0, 1.25f, .08f);
        foreach (var renderer in bodyRenderers) renderer.enabled = !IsWorkerMode || ThirdPerson;
    }
    void UpdateCursor()
    { Cursor.lockState = PdaRaised ? CursorLockMode.None : CursorLockMode.Locked; Cursor.visible = PdaRaised; }
    public void TogglePda()
    {
        if (!IsWorkerMode) return;
        PdaRaised = !PdaRaised; galleryOpen = false;
        visual.Advance(0, 0, controller.isGrounded, verticalSpeed, PdaRaised);
        UpdateCameras(); UpdateCursor();
    }
    public void SetThirdPerson(bool value) { ThirdPerson = value; UpdateCameras(); }
    public bool TakePhoto()
    {
        if (!IsWorkerMode || !PdaRaised || !capture.Capture()) return false;
        visual.Shutter(); return true;
    }
    void Update()
    {
        if (WorkerRoot == null) return;
        if (!PdaRaised && Input.GetKeyDown(KeyCode.F)) { if (IsWorkerMode) ExitWorker(); else EnterWorker(); }
        if (!IsWorkerMode) { visual.Advance(Time.deltaTime, 0, true, 0, false); return; }
        if (Input.GetKeyDown(KeyCode.P) || (PdaRaised && Input.GetKeyDown(KeyCode.Escape))) TogglePda();
        if (PdaRaised) {
            visual.Advance(Time.deltaTime, 0, controller.isGrounded, verticalSpeed, true); UpdateCameras();
            if (!galleryOpen && !capture.HasPreview && cameraStream?.Streaming!=true) capture.RenderLivePreview(); return;
        }
        if (Input.GetKeyDown(KeyCode.V)) SetThirdPerson(!ThirdPerson);
        StepMovement(Time.deltaTime, new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")),
            new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")),
            Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift), Input.GetKeyDown(KeyCode.Space));
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
            GUI.Box(new Rect(16,16,Mathf.Min(360,Screen.width-32),116),"현장 이동\nWASD 이동 · 마우스 시점\nShift 달리기 · Space 점프\nP PDA · V 시점 전환 · F 관제");
            GUI.Label(new Rect(Screen.width/2-5,Screen.height/2-12,20,24),"+");
            return;
        }
        var e=Event.current;
        if(!galleryOpen && !capture.HasPreview && e.type==EventType.KeyDown &&
            (e.keyCode==KeyCode.Space || e.keyCode==KeyCode.Return || e.keyCode==KeyCode.KeypadEnter)) { TakePhoto(); e.Use(); }
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
            var live=cameraStream?.Preview ?? capture.LivePreview;
            if(live!=null) DrawPhoto(live);
            GUILayout.Label("P로 PDA를 닫고 시점을 조정하세요.",ui.Caption);
            if(GUILayout.Button("사진 촬영 [Space / Enter]",ui.Primary,GUILayout.Height(44))) TakePhoto();
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
        Remove(galleryImage);
        if (WorkerRoot != null) Remove(WorkerRoot.gameObject);
    }
}
