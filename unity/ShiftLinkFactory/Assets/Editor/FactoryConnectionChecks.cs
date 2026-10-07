using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryConnectionChecks
{
    static float PointGap(Vector3 point,Vector3 a,Vector3 b)
    {
        var delta=b-a;
        if(delta.sqrMagnitude<1e-8f) return Vector3.Distance(point,a);
        return Vector3.Distance(point,a+delta*Mathf.Clamp01(Vector3.Dot(point-a,delta)/delta.sqrMagnitude));
    }
    static float SegmentGap(Vector3 a,Vector3 b,Vector3 c,Vector3 d)
    {
        var u=b-a; var v=d-c; var w=a-c;
        float uu=Vector3.Dot(u,u),uv=Vector3.Dot(u,v),vv=Vector3.Dot(v,v),uw=Vector3.Dot(u,w),vw=Vector3.Dot(v,w);
        float gap=Mathf.Min(Mathf.Min(PointGap(a,c,d),PointGap(b,c,d)),Mathf.Min(PointGap(c,a,b),PointGap(d,a,b)));
        float denominator=uu*vv-uv*uv;
        if(denominator>1e-6f) {
            float s=(uv*vw-vv*uw)/denominator,t=(uu*vw-uv*uw)/denominator;
            if(s>=0 && s<=1 && t>=0 && t<=1) gap=Mathf.Min(gap,Vector3.Distance(a+s*u,c+t*v));
        }
        return gap;
    }
    public static void Run()
    {
        var failures=new List<string>();
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Connection review").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state); demo.SetExteriorView(false);
            var nodes=demo.transform.Find("MES equipment");
            var connections=nodes.Cast<Transform>().Where(t=>t.name.StartsWith("Connection_")).ToArray();
            for(int i=0;i<connections.Length;i++) for(int j=i+1;j<connections.Length;j++)
                if(connections[i].name==connections[j].name && Vector3.Distance(connections[i].position,connections[j].position)<.001f)
                    failures.Add("Duplicate connection at same port: "+connections[i].name+" "+connections[i].position);
            var lines=nodes.GetComponentsInChildren<LineRenderer>().Where(l=>l.name.StartsWith("Power cable") || l.name.StartsWith("Hydraulic supply") || l.name.StartsWith("Assumed hydraulic return") || l.name=="CAU air riser").ToArray();
            for(int i=0;i<lines.Length;i++) for(int j=i+1;j<lines.Length;j++)
                for(int x=1;x<lines[i].positionCount;x++) for(int y=1;y<lines[j].positionCount;y++)
                    if(SegmentGap(lines[i].GetPosition(x-1),lines[i].GetPosition(x),lines[j].GetPosition(y-1),lines[j].GetPosition(y))<.5f*(lines[i].widthMultiplier+lines[j].widthMultiplier)-.001f)
                        failures.Add("Intersecting utility runs: "+lines[i].name+" segment "+x+" / "+lines[j].name+" segment "+y);
            foreach(var text in demo.GetComponentsInChildren<TextMesh>()) text.gameObject.SetActive(false);
            demo.transform.Find("Factory status display").gameObject.SetActive(false);
            foreach(string id in new[]{"EQ-0001","EQ-0002","EQ-0004","EQ-0005","EQ-0008"}) {
                var target=nodes.Find(id).position+new Vector3(.4f,1.1f,-.3f);
                Camera.main.transform.position=target+new Vector3(3,3,-4); Camera.main.transform.LookAt(target);
                FactoryChecks.Capture(Path.Combine(dir,"connection-"+id+".png"));
            }
            File.WriteAllText(Path.Combine(dir,"connection-result.txt"),failures.Count==0 ? "PASS: no duplicated connection assets, overlapping or intersecting utility runs" : string.Join("\n",failures));
            foreach(var failure in failures) Debug.LogError(failure);
            EditorApplication.Exit(failures.Count==0 ? 0 : 1);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
