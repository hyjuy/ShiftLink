using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

// ponytail: MJPEG for one PDA. Use WebRTC if measured latency or bandwidth requires it.
public class FactoryCameraStream : MonoBehaviour
{
    FactoryWorker worker;
    FactoryCapture capture;
    TcpListener listener;
    Thread server;
    volatile bool running;
    bool previousBackground;
    readonly object frameLock = new object();
    byte[] jpeg;
    long frameAt, requestedAt;
    bool streaming, enteredWorker, raisedPda;
    float nextFrame;
    RenderTexture target;
    Texture2D pixels;
    public int FrameCount { get; private set; }
    public bool Streaming { get { return streaming; } }
    public string Error { get; private set; }

    public void Initialize(FactoryWorker employee, FactoryCapture photos)
    {
        worker = employee; capture = photos;
        if(!Application.isPlaying || running) return;
        previousBackground=Application.runInBackground;
        Application.runInBackground=true;
        int port = 8090;
        var args = Environment.GetCommandLineArgs();
        for(int i=0; i<args.Length-1; i++) if(args[i]=="--camera-port") port=int.Parse(args[i+1]);
        try {
            // Pi reaches this loopback-only endpoint through SSH reverse forwarding.
            listener = new TcpListener(IPAddress.Loopback, port); listener.Start(); running=true;
            server = new Thread(Serve) {IsBackground=true}; server.Start();
        } catch(Exception error) { Error=error.Message; Debug.LogWarning("PDA camera: "+Error); }
    }
    void Serve()
    {
        while(running) {
            try {
                var client = listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(_ => Reply(client));
            } catch(SocketException) { if(!running) return; }
            catch(ObjectDisposedException) { return; }
        }
    }
    void Reply(TcpClient client)
    {
        using(client) {
            try {
                client.ReceiveTimeout=2000; client.SendTimeout=2000;
                client.NoDelay=true;
                var stream=client.GetStream();
                // Bound the request before decoding; browser/proxy sends no body for this endpoint.
                var bytes=new MemoryStream(); int last=0, value;
                while(bytes.Length<4096 && (value=stream.ReadByte())>=0) {
                    bytes.WriteByte((byte)value);
                    if(value==10 && last==10) break;
                    if(value!=13) last=value;
                }
                string request=Encoding.ASCII.GetString(bytes.ToArray());
                if(request.StartsWith("GET /stream.mjpg HTTP/1.", StringComparison.Ordinal) && bytes.Length<4096) {
                    StreamFrames(stream,client); return;
                }
                byte[] body; string status, type;
                if(!request.StartsWith("GET /frame.jpg HTTP/1.", StringComparison.Ordinal) || bytes.Length>=4096) {
                    body=Encoding.UTF8.GetBytes("Not found"); status="404 Not Found"; type="text/plain";
                } else {
                    Interlocked.Exchange(ref requestedAt, DateTime.UtcNow.Ticks);
                    lock(frameLock) {
                        bool fresh=jpeg!=null && DateTime.UtcNow.Ticks-frameAt<TimeSpan.TicksPerSecond*2;
                        body=fresh ? jpeg : Encoding.UTF8.GetBytes("Camera starting");
                        status=fresh ? "200 OK" : "503 Service Unavailable"; type=fresh ? "image/jpeg" : "text/plain";
                    }
                }
                var header=Encoding.ASCII.GetBytes("HTTP/1.1 "+status+"\r\nContent-Type: "+type+"\r\nContent-Length: "+body.Length+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n");
                stream.Write(header,0,header.Length); stream.Write(body,0,body.Length);
            } catch(IOException) {} catch(ObjectDisposedException) {} catch(SocketException) {}
        }
    }
    void StreamFrames(NetworkStream stream, TcpClient client)
    {
        Interlocked.Exchange(ref requestedAt,DateTime.UtcNow.Ticks);
        long sentAt=0;
        var header=Encoding.ASCII.GetBytes("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n");
        stream.Write(header,0,header.Length);
        while(running) {
            if(client.Client.Poll(0,SelectMode.SelectRead) && client.Available==0) return;
            Interlocked.Exchange(ref requestedAt,DateTime.UtcNow.Ticks);
            byte[] frame=null;
            lock(frameLock) {
                if(jpeg!=null && frameAt!=sentAt && DateTime.UtcNow.Ticks-frameAt<TimeSpan.TicksPerSecond) {
                    frame=jpeg; sentAt=frameAt;
                }
            }
            if(frame==null) { Thread.Sleep(10); continue; }
            var part=Encoding.ASCII.GetBytes("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "+frame.Length+"\r\n\r\n");
            stream.Write(part,0,part.Length); stream.Write(frame,0,frame.Length);
            stream.WriteByte(13); stream.WriteByte(10);
        }
    }
    void LateUpdate()
    {
        if(!running || worker==null || capture==null) return;
        bool wanted=DateTime.UtcNow.Ticks-Interlocked.Read(ref requestedAt)<TimeSpan.TicksPerSecond*3;
        if(wanted && !streaming) {
            enteredWorker=!worker.IsWorkerMode; raisedPda=!worker.PdaRaised;
            worker.EnterWorker(); if(!worker.PdaRaised) worker.TogglePda();
            streaming=true;
        } else if(!wanted && streaming) StopCamera();
        if(!streaming || Time.realtimeSinceStartup<nextFrame) return;
        nextFrame=Time.realtimeSinceStartup+.05f;
        try {
            if(!capture.RenderLivePreview()) return;
            if(target==null) {
                target=new RenderTexture(960,540,0); target.Create();
                pixels=new Texture2D(960,540,TextureFormat.RGB24,false);
            }
            var previous=RenderTexture.active;
            try {
                Graphics.Blit(capture.LivePreview,target); RenderTexture.active=target;
                pixels.ReadPixels(new Rect(0,0,960,540),0,0); pixels.Apply();
            } finally { RenderTexture.active=previous; }
            var frame=pixels.EncodeToJPG(85);
            lock(frameLock) { jpeg=frame; frameAt=DateTime.UtcNow.Ticks; }
            FrameCount++;
        } catch(Exception error) { Error=error.Message; }
    }
    void StopCamera()
    {
        if(raisedPda && worker.PdaRaised) worker.TogglePda();
        if(enteredWorker) worker.ExitWorker();
        streaming=false;
        lock(frameLock) { jpeg=null; frameAt=0; }
    }
    void OnDisable()
    {
        running=false; listener?.Stop();
        Application.runInBackground=previousBackground;
        if(streaming && worker!=null) StopCamera();
        if(server!=null && server.IsAlive) server.Join(2500);
        if(target!=null) { target.Release(); Destroy(target); }
        if(pixels!=null) Destroy(pixels);
    }
}
