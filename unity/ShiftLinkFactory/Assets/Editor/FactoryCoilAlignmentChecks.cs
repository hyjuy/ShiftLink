using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryCoilAlignmentChecks
{
    public static void Run()
    {
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var failures=new List<string>();
            var measurements=new List<string>();
            var load=FactoryRig.CreateLoad("Coil alignment",null,false);
            var coil=load.GetComponentsInChildren<Renderer>().Where(r=>r.name!="Assumed transport saddle").ToArray();
            var bounds=coil[0].bounds;
            foreach(var renderer in coil) bounds.Encapsulate(renderer.bounds);
            var saddles=load.GetComponentsInChildren<Renderer>().Where(r=>r.name=="Assumed transport saddle").ToArray();
            var centre=(saddles[0].transform.position+saddles[1].transform.position)*.5f;
            measurements.Add("Coil bounds: "+bounds+"; saddle centre: "+centre);
            foreach(var r in coil) measurements.Add(r.name+": "+r.bounds);
            if(Mathf.Abs(bounds.center.x-centre.x)>.001f || Mathf.Abs(bounds.center.z-centre.z)>.001f)
                failures.Add("Large steel coil is not horizontally centred on its cradle: "+bounds.center+" / "+centre);
            var camera=new GameObject("Camera").AddComponent<Camera>(); camera.tag="MainCamera";
            camera.transform.position=bounds.center+new Vector3(2,1.4f,-3); camera.transform.LookAt(bounds.center);
            camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=Color.gray;
            var light=new GameObject("Light").AddComponent<Light>(); light.type=LightType.Directional; light.transform.rotation=Quaternion.Euler(40,-30,0);
            FactoryChecks.Capture(Path.Combine(dir,"coil-alignment.png"));
            UnityEngine.Object.DestroyImmediate(load.gameObject);
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var demo=new GameObject("Station coil review").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.SetExteriorView(false);
            foreach(var text in demo.GetComponentsInChildren<TextMesh>()) text.gameObject.SetActive(false);
            demo.transform.Find("Factory status display").gameObject.SetActive(false);
            var campus=demo.transform.Find("Virtual process campus");
            foreach(string name in new[]{"Decoiler","Recoiler"}) {
                var station=campus.Find(name);
                var reel=station.Find("Station reel");
                var body=reel.GetComponentsInChildren<Renderer>().Single(r=>r.name=="WoundSheet");
                var mandrel=station.Find("Winding mandrel");
                float error=Vector3.Distance(body.bounds.center,mandrel.position);
                measurements.Add(name+": coil centre="+body.bounds.center+"; mandrel centre="+mandrel.position+"; error="+error.ToString("F6"));
                if(error>.001f) failures.Add(name+" coil bore and support shaft centres differ by "+error.ToString("F6")+"m");
                if(reel.GetComponentsInChildren<Transform>().Any(t=>t.name=="Assumed transport saddle"))
                    failures.Add(name+" mounted coil must not carry a moving transport saddle");
                Camera.main.transform.position=mandrel.position+new Vector3(3,2,-5); Camera.main.transform.LookAt(mandrel.position);
                FactoryChecks.Capture(Path.Combine(dir,"coil-alignment-"+name+".png"));
            }
            File.WriteAllText(Path.Combine(dir,"coil-alignment-result.txt"),string.Join("\n",measurements.Concat(failures))+(failures.Count==0 ? "\nPASS" : "\nFAIL"));
            foreach(var failure in failures) Debug.LogError(failure);
            EditorApplication.Exit(failures.Count==0 ? 0 : 1);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
