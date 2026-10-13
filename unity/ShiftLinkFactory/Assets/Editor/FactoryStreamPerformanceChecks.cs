using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

public static class FactoryStreamPerformanceChecks
{
    static FactoryDemo demo;
    static FactoryCameraStream stream;
    static FactoryCapture capture;
    static readonly List<double> mainMs = new List<double>(), publishMs = new List<double>();
    static readonly List<long> allocated = new List<long>();
    static Stopwatch pending;
    static double next;
    static int before;
    static string label;
    static int regressionPhase;
    static double regressionStart;
    static readonly BindingFlags flags = BindingFlags.Instance | BindingFlags.NonPublic;
    static void Set(string name, object value) { typeof(FactoryCameraStream).GetField(name,flags).SetValue(stream,value); }
    static void Setup()
    {
        var obj = new GameObject("Stream performance fixture");
        demo = obj.AddComponent<FactoryDemo>(); demo.CreateEnvironment(); demo.LoadDefaultFactory();
        capture = obj.GetComponent<FactoryCapture>(); stream = obj.GetComponent<FactoryCameraStream>();
    }
    public static void Regression()
    {
        try {
            Setup();
            var method=typeof(FactoryCapture).GetMethod("RenderStreamPreview");
            if(method==null) throw new Exception("RED: dedicated stream render is missing");
            var target=new RenderTexture(960,540,24,RenderTextureFormat.ARGB32); target.Create();
            try {
                var disabled=new GameObject("excluded disabled"); disabled.transform.SetParent(demo.transform);
                var renderer=disabled.AddComponent<MeshRenderer>(); renderer.enabled=false;
                if(!(bool)method.Invoke(capture,new object[]{target})) throw new Exception("Stream render failed");
                if(capture.LivePreview!=null) throw new Exception("Stream allocated the photo preview");
                if(renderer.enabled) throw new Exception("Disabled renderer state lost");
                if(capture.width!=1280 || capture.height!=720) throw new Exception("Photo dimensions changed");
            } finally { target.Release(); UnityEngine.Object.DestroyImmediate(target); }
            Debug.Log("PASS: dedicated low-resolution render, photo isolation, renderer state");
            Set("running",true); Set("requestedAt",DateTime.UtcNow.Ticks); Set("nextFrame",0f);
            typeof(FactoryCameraStream).GetMethod("LateUpdate",flags).Invoke(stream,null);
            for(int i=0;i<3;i++) { Set("nextFrame",0f); typeof(FactoryCameraStream).GetMethod("LateUpdate",flags).Invoke(stream,null); }
            if(stream.FrameCount!=0 || (int)typeof(FactoryCameraStream).GetField("pipelineBusy",flags).GetValue(stream)!=1)
                throw new Exception("Readback must be asynchronous with one pending frame");
            typeof(FactoryCameraStream).GetMethod("StopCamera",flags).Invoke(stream,null);
            regressionStart=EditorApplication.timeSinceStartup; regressionPhase=0;
            EditorApplication.update+=CheckAsync;
        } catch(Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
    static void CheckAsync()
    {
        try {
            EditorApplication.QueuePlayerLoopUpdate();
            if(EditorApplication.timeSinceStartup-regressionStart>30) throw new Exception("Async regression timeout: phase="+regressionPhase+" busy="+typeof(FactoryCameraStream).GetField("pipelineBusy",flags).GetValue(stream)+" frames="+stream.FrameCount+" streaming="+stream.Streaming+" running="+typeof(FactoryCameraStream).GetField("running",flags).GetValue(stream)+" workerAlive="+(demo.GetComponent<FactoryWorker>()!=null)+" targetCreated="+((RenderTexture)typeof(FactoryCameraStream).GetField("target",flags).GetValue(stream)).IsCreated()+" captureStatus="+capture.Status);
            if(stream.Error!=null) throw new Exception(stream.Error);
            if(regressionPhase==0) {
                if((int)typeof(FactoryCameraStream).GetField("pipelineBusy",flags).GetValue(stream)!=0) return;
                if(stream.FrameCount!=0 || typeof(FactoryCameraStream).GetField("jpeg",flags).GetValue(stream)!=null)
                    throw new Exception("Disconnected readback published a stale frame");
                // Camera switches and graphics resets can release the native target without destroying its object.
                ((RenderTexture)typeof(FactoryCameraStream).GetField("target",flags).GetValue(stream)).Release();
                Set("requestedAt",DateTime.UtcNow.Ticks); Set("nextFrame",0f);
                typeof(FactoryCameraStream).GetMethod("LateUpdate",flags).Invoke(stream,null);
                regressionPhase=1; return;
            }
            if(stream.FrameCount==0) return;
            var jpg=(byte[])typeof(FactoryCameraStream).GetField("jpeg",flags).GetValue(stream);
            var image=new Texture2D(2,2);
            if(!image.LoadImage(jpg) || image.width!=960 || image.height!=540) throw new Exception("Invalid async JPEG");
            var target=(RenderTexture)typeof(FactoryCameraStream).GetField("target",flags).GetValue(stream);
            var previous=RenderTexture.active; var reference=new Texture2D(960,540,TextureFormat.RGBA32,false);
            try {
                RenderTexture.active=target; reference.ReadPixels(new Rect(0,0,960,540),0,0,false);
                double error=0, flipped=0; int count=0;
                for(int y=30;y<540;y+=60) for(int x=30;x<960;x+=60) {
                    var expected=reference.GetPixel(x,y); var actual=image.GetPixel(x,y); var reverse=image.GetPixel(x,539-y);
                    error+=Math.Abs(expected.r-actual.r)+Math.Abs(expected.g-actual.g)+Math.Abs(expected.b-actual.b);
                    flipped+=Math.Abs(expected.r-reverse.r)+Math.Abs(expected.g-reverse.g)+Math.Abs(expected.b-reverse.b); count++;
                }
                if(error/count>.12 || error>flipped) throw new Exception("JPEG orientation/color mismatch: "+error/count);
                Debug.Log("PASS: async readback, bounded work, stale-frame rejection, reconnect, JPEG color/orientation; mean RGB error="+error/count);
            } finally { RenderTexture.active=previous; UnityEngine.Object.DestroyImmediate(reference); UnityEngine.Object.DestroyImmediate(image); }
            Set("requestedAt",DateTime.UtcNow.Ticks); Set("nextFrame",0f);
            typeof(FactoryCameraStream).GetMethod("LateUpdate",flags).Invoke(stream,null);
            UnityEngine.Object.DestroyImmediate(demo.gameObject);
            Debug.Log("PASS: disposal while readback is pending");
            EditorApplication.update-=CheckAsync; EditorApplication.Exit(0);
        } catch(Exception e) { EditorApplication.update-=CheckAsync; Debug.LogException(e); EditorApplication.Exit(1); }
    }
    public static void Benchmark()
    {
        try {
            label="baseline";
            var args=Environment.GetCommandLineArgs();
            for(int i=0;i<args.Length-1;i++) if(args[i]=="--stream-label") label=args[i+1];
            Setup(); Set("running",true);
            next=EditorApplication.timeSinceStartup;
            EditorApplication.update+=Tick;
        } catch(Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
    static double Percentile(IEnumerable<double> values,double p) { var a=values.OrderBy(v=>v).ToArray(); return a[(int)Math.Ceiling((a.Length-1)*p)]; }
    static void Tick()
    {
        try {
            if(stream.Error!=null) throw new Exception(stream.Error);
            if(pending!=null) {
                if(stream.FrameCount==before) { if(pending.Elapsed.TotalSeconds>10) throw new Exception("Frame publish timeout"); return; }
                publishMs.Add(pending.Elapsed.TotalMilliseconds); pending=null;
                if(publishMs.Count==110) {
                    var args=Environment.GetCommandLineArgs(); string output=Path.Combine(Application.dataPath,"../Checks"); Directory.CreateDirectory(output);
                    string result="label="+label+"; samples=100; warmup=10; resolution=960x540; quality=70; rate=10; editor="+Application.unityVersion+"; gpu="+SystemInfo.graphicsDeviceName+
                        "; main_ms_p50="+Percentile(mainMs.Skip(10),.5).ToString("F3")+"; main_ms_p95="+Percentile(mainMs.Skip(10),.95).ToString("F3")+
                        "; publish_ms_p50="+Percentile(publishMs.Skip(10),.5).ToString("F3")+"; publish_ms_p95="+Percentile(publishMs.Skip(10),.95).ToString("F3")+
                        "; allocation_counter=unavailable_on_this_Unity_Mono";
                    File.WriteAllText(Path.Combine(output,"stream-"+label+".txt"),result);
                    var jpg=(byte[])typeof(FactoryCameraStream).GetField("jpeg",flags).GetValue(stream);
                    File.WriteAllBytes(Path.Combine(output,"stream-"+label+".jpg"),jpg);
                    var image=new Texture2D(2,2);
                    if(!image.LoadImage(jpg) || image.width!=960 || image.height!=540) throw new Exception("Invalid encoded JPEG");
                    UnityEngine.Object.DestroyImmediate(image);
                    Debug.Log(result);
                    EditorApplication.update-=Tick; UnityEngine.Object.DestroyImmediate(demo.gameObject); EditorApplication.Exit(0); return;
                }
            }
            if(EditorApplication.timeSinceStartup<next) return;
            next=EditorApplication.timeSinceStartup+.1;
            Set("requestedAt",DateTime.UtcNow.Ticks); Set("nextFrame",0f); before=stream.FrameCount;
            long bytes=GC.GetAllocatedBytesForCurrentThread(); pending=Stopwatch.StartNew();
            typeof(FactoryCameraStream).GetMethod("LateUpdate",flags).Invoke(stream,null);
            mainMs.Add(pending.Elapsed.TotalMilliseconds); allocated.Add(GC.GetAllocatedBytesForCurrentThread()-bytes);
        } catch(Exception e) { Debug.LogException(e); EditorApplication.update-=Tick; EditorApplication.Exit(1); }
    }
}
