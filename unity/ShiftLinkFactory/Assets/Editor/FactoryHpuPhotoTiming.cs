using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Debug=UnityEngine.Debug;

[InitializeOnLoad]
public static class FactoryHpuPhotoTiming
{
    [Serializable] class Result { public string equipment_id,photo; public long move_unix_ms; public double move_to_photo_ms,capture_ms,save_ms,move_to_stream_ready_ms; public bool hpu_visible; }
    static string request=Path.Combine(Application.dataPath,"../Checks/hpu-photo-request.flag"),output=Path.Combine(Application.dataPath,"../Checks/hpu-photo-timing.json");
    static int phase; static FactoryWorker worker; static FactoryCameraStream stream; static Result result; static Stopwatch total; static int frames;
    static FactoryHpuPhotoTiming() { phase=SessionState.GetBool("ShiftLink.HpuRestart",false)?2:0; EditorApplication.update+=Tick; }
    static void Tick()
    {
        if(!File.Exists(request)) return;
        try {
            if(phase==0) { EditorApplication.isPlaying=false; phase=1; return; }
            if(phase==1) { if(EditorApplication.isPlayingOrWillChangePlaymode) return; SessionState.SetBool("ShiftLink.HpuRestart",true); EditorApplication.EnterPlaymode(); phase=2; return; }
            if(!Application.isPlaying) return;
            if(phase==2) {
                var demo=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>(); if(demo==null || !demo.Connected) return;
                worker=demo.GetComponent<FactoryWorker>(); stream=demo.GetComponent<FactoryCameraStream>(); if(!stream.Streaming) return;
                var flags=BindingFlags.Instance|BindingFlags.NonPublic;
                var config=(FactoryConfig)typeof(FactoryDemo).GetField("config",flags).GetValue(demo);
                var nodes=(Dictionary<string,GameObject>)typeof(FactoryDemo).GetField("equipment",flags).GetValue(demo);
                var equipment=config.equipment.Single(e=>e.code=="HPU-01"); var node=nodes[equipment.equipment_id];
                var renderers=node.GetComponentsInChildren<Renderer>(); var bounds=renderers[0].bounds; foreach(var r in renderers) if(r.GetComponent<TextMesh>()==null) bounds.Encapsulate(r.bounds);
                worker.EnterWorker(); if(worker.PdaRaised) worker.TogglePda();
                var controller=worker.WorkerRoot.GetComponent<CharacterController>(); controller.enabled=false;
                worker.WorkerRoot.position=node.transform.position+new Vector3(0,.05f,-5); controller.enabled=true;
                typeof(FactoryWorker).GetField("yaw",flags).SetValue(worker,0f); Physics.SyncTransforms();
                result=new Result {equipment_id=equipment.equipment_id,move_unix_ms=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}; total=Stopwatch.StartNew();
                worker.Step(.1f,Vector2.up,Vector2.zero); worker.TogglePda(); worker.PdaCamera.transform.LookAt(bounds.center);
                var capture=demo.GetComponent<FactoryCapture>(); capture.Retake(); capture.outputDirectory=Path.Combine(Application.dataPath,"../Checks/hpu-timing-photos");
                var timer=Stopwatch.StartNew(); if(!capture.Capture()) throw new Exception(capture.Status); result.capture_ms=timer.Elapsed.TotalMilliseconds;
                result.hpu_visible=capture.PreviewMetadata.objects.Any(o=>o.equipment_id==equipment.equipment_id); if(!result.hpu_visible) throw new Exception("HPU not visible in capture mask");
                timer.Restart(); if(!capture.Save()) throw new Exception(capture.Status); result.save_ms=timer.Elapsed.TotalMilliseconds;
                result.photo=capture.LastSavedPath; result.move_to_photo_ms=total.Elapsed.TotalMilliseconds; frames=stream.FrameCount; phase=3;
            }
            if(phase==3 && stream.FrameCount>=frames+2) {
                result.move_to_stream_ready_ms=total.Elapsed.TotalMilliseconds; File.WriteAllText(output,JsonUtility.ToJson(result,true));
                File.Delete(request); SessionState.SetBool("ShiftLink.HpuRestart",false); phase=0; Debug.Log("PASS: HPU visible photo and metadata saved; "+output);
            }
        } catch(Exception e) { Debug.LogException(e); File.Delete(request); SessionState.SetBool("ShiftLink.HpuRestart",false); phase=0; }
    }
}
