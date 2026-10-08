using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

[InitializeOnLoad]
public static class FactoryCameraStreamChecks
{
    static UnityWebRequest request;
    static int frames;
    static double stoppedAt;
    static FactoryCameraStreamChecks() { EditorApplication.update+=Check; }
    public static void Run()
    {
        SessionState.SetBool("ShiftLink.CameraCheck",true);
        SessionState.SetFloat("ShiftLink.CameraCheckStart",(float)EditorApplication.timeSinceStartup);
        FactoryChecks.OpenDemo();
    }
    static void Check()
    {
        if(!SessionState.GetBool("ShiftLink.CameraCheck",false)) return;
        try {
            if(EditorApplication.timeSinceStartup-SessionState.GetFloat("ShiftLink.CameraCheckStart",0)>60)
                throw new Exception("Unity camera HTTP check timed out");
            var factory=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
            if(!Application.isPlaying || factory==null || !factory.Connected) return;
            var stream=factory.GetComponent<FactoryCameraStream>();
            if(stream==null || stream.Error!=null) throw new Exception("Unity camera server unavailable: "+stream?.Error);
            if(frames>=3) {
                if(EditorApplication.timeSinceStartup-stoppedAt<4) return;
                if(stream.Streaming) throw new Exception("Camera must stop when the PDA disconnects");
                string result="PASS: Unity PDA camera served 3 real JPEG frames at 960x540; rendered="+stream.FrameCount+"; camera stopped after disconnect";
                File.WriteAllText(Path.Combine(Application.dataPath,"../Checks/camera-stream-check-result.txt"),result);
                SessionState.SetBool("ShiftLink.CameraCheck",false);
                Debug.Log(result); EditorApplication.Exit(0); return;
            }
            if(request==null) {
                request=UnityWebRequest.Get("http://127.0.0.1:8090/frame.jpg"); request.timeout=3;
                request.SendWebRequest(); return;
            }
            if(!request.isDone) return;
            if(request.result==UnityWebRequest.Result.Success) {
                var image=new Texture2D(2,2);
                try {
                    if(!image.LoadImage(request.downloadHandler.data) || image.width!=960 || image.height!=540)
                        throw new Exception("Invalid Unity camera JPEG dimensions");
                    Directory.CreateDirectory(Path.Combine(Application.dataPath,"../Checks"));
                    File.WriteAllBytes(Path.Combine(Application.dataPath,"../Checks/camera-stream.jpg"),request.downloadHandler.data);
                    frames++;
                } finally { UnityEngine.Object.DestroyImmediate(image); }
                if(frames>=3) stoppedAt=EditorApplication.timeSinceStartup;
            }
            request.Dispose(); request=null;
        } catch(Exception error) {
            request?.Dispose(); request=null;
            SessionState.SetBool("ShiftLink.CameraCheck",false);
            Debug.LogException(error); EditorApplication.Exit(1);
        }
    }
}
