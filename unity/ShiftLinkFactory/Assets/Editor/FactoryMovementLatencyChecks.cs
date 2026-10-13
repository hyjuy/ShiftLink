using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

// Temporary editor-only movement experiment; never changes MES state or deployed PDA code.
[InitializeOnLoad]
public static class FactoryMovementLatencyChecks
{
    [Serializable] public class Trial { public int sequence; public long input_unix_ms; public float before_x,after_x; public string color; }
    [Serializable] public class Results { public string input="synthetic FactoryWorker.Step"; public List<Trial> trials=new List<Trial>(); }
    static readonly string request=Path.Combine(Application.dataPath,"../Checks/movement-request.flag");
    static readonly string output=Path.Combine(Application.dataPath,"../Checks/movement-events.json");
    static int phase;
    static double next;
    static FactoryWorker worker;
    static GameObject marker;
    static Material material;
    static Results results;
    static FactoryMovementLatencyChecks() { phase=SessionState.GetBool("ShiftLink.MovementRestart",false)?2:0; EditorApplication.update+=Tick; }
    static void Tick()
    {
        if(!File.Exists(request)) return;
        try {
            if(phase==0) { EditorApplication.isPlaying=false; phase=1; return; }
            if(phase==1) {
                if(EditorApplication.isPlayingOrWillChangePlaymode) return;
                SessionState.SetBool("ShiftLink.MovementRestart",true);
                EditorApplication.EnterPlaymode(); phase=2; return;
            }
            if(!Application.isPlaying) return;
            if(phase<2 && SessionState.GetBool("ShiftLink.MovementRestart",false)) phase=2;
            if(phase==2) {
                worker=UnityEngine.Object.FindFirstObjectByType<FactoryWorker>();
                var demo=UnityEngine.Object.FindFirstObjectByType<FactoryDemo>();
                var stream=worker?.GetComponent<FactoryCameraStream>();
                if(worker==null || demo==null || !demo.Connected || stream==null || !stream.Streaming) return;
                if(worker.PdaRaised) worker.TogglePda();
                marker=GameObject.CreatePrimitive(PrimitiveType.Quad); marker.name="Temporary movement timing marker";
                UnityEngine.Object.Destroy(marker.GetComponent<Collider>());
                material=new Material(Shader.Find("Unlit/Color")); material.color=Color.blue;
                marker.GetComponent<Renderer>().sharedMaterial=material;
                results=new Results(); next=EditorApplication.timeSinceStartup+2; phase=3;
            }
            if(phase!=3) return;
            var camera=worker.PdaCamera;
            float markerHeight=2*.2f*Mathf.Tan(camera.fieldOfView*Mathf.Deg2Rad*.5f);
            marker.transform.position=camera.transform.TransformPoint(new Vector3(-.45f*markerHeight*(960f/540f),.45f*markerHeight,.2f));
            marker.transform.rotation=camera.transform.rotation;
            float height=2*.2f*Mathf.Tan(camera.fieldOfView*Mathf.Deg2Rad*.5f);
            marker.transform.localScale=new Vector3(height*(960f/540f)*.04f,height*.07f,1);
            if(EditorApplication.timeSinceStartup<next) return;
            next=EditorApplication.timeSinceStartup+2;
            if(results.trials.Count==20) {
                File.WriteAllText(output,JsonUtility.ToJson(results,true));
                File.Delete(request); SessionState.SetBool("ShiftLink.MovementRestart",false);
                UnityEngine.Object.Destroy(marker); UnityEngine.Object.Destroy(material);
                Debug.Log("PASS: movement timing generated 20 controller inputs; "+output); phase=0; return;
            }
            int sequence=results.trials.Count+1;
            var trial=new Trial {sequence=sequence,input_unix_ms=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),before_x=worker.WorkerRoot.position.x,color=sequence%2==1?"red":"green"};
            worker.Step(.1f,sequence%2==1?Vector2.right:Vector2.left,Vector2.zero);
            trial.after_x=worker.WorkerRoot.position.x;
            if(Mathf.Abs(trial.after_x-trial.before_x)<.01f) throw new Exception("Movement blocked; trial invalid");
            material.color=sequence%2==1?Color.red:Color.green;
            results.trials.Add(trial); File.WriteAllText(output,JsonUtility.ToJson(results,true));
        } catch(Exception e) { Debug.LogException(e); File.Delete(request); phase=0; }
    }
}
