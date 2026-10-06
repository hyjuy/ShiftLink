using System;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;

public static class FactoryLogisticsChecks
{
    public static void Run()
    {
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Logistics review").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state);
            var type=typeof(FactoryDemo).Assembly.GetType("FactoryLogistics");
            Require(type!=null,"complete virtual finishing and shipping line installed");
            var logistics=demo.GetComponent(type);
            Func<string,int> count=name=>(int)type.GetProperty(name).GetValue(logistics);
            Action<float,bool> advance=(dt,running)=>type.GetMethod("Advance").Invoke(logistics,new object[]{dt,running});
            var last=state.coils[0]; last.equipment_id=config.route.Last(); last.position=1;
            demo.Apply(state);
            var original=demo.transform.Find("MES coils").Find(last.coil_id);
            state.sequence++; state.coils=state.coils.Skip(1).ToArray(); demo.Apply(state);
            Require(count("InTransitCount")==1,"MES outlet coil retained by identity");
            Require(original!=null && original.name==last.coil_id,"same coil object continues downstream");
            var before=original.position; advance(5,false);
            Require(original.position==before,"pause freezes virtual material");
            for(int i=0;i<600;i++) advance(1,true);
            Require(count("StoredCount")==1 && count("InTransitCount")==0,"coil traverses finishing line into warehouse");
            type.GetMethod("DispatchStored").Invoke(logistics,null);
            for(int i=0;i<100;i++) advance(1,true);
            Require(count("TruckCount")==1 && count("StoredCount")==0,"stored coil loaded on truck");
            type.GetProperty("SendToTruck").SetValue(logistics,true);
            for(int i=0;i<9;i++) {
                var load=FactoryRig.CreateLoad("Test-"+i,demo.transform,false);
                load.position=new Vector3(15.3f,1.24f,0);
                type.GetMethod("Accept").Invoke(logistics,new object[]{load});
            }
            for(int i=0;i<900;i++) advance(1,true);
            Require(count("TruckCount")==8 && count("StoredCount")==2,"truck capacity overflow diverted to warehouse");
            type.GetMethod("DepartTruck").Invoke(logistics,null);
            Require(count("TruckCount")==0,"truck departure clears loaded shipment");
            Require(demo.EquipmentCount==config.equipment.Length,"virtual line does not add MES identifiers");
            var extension=demo.transform.Find("Virtual process campus");
            Require(extension!=null,"factory annex and yards installed");
            foreach(var name in new[]{"Decoiler","Leveler","Slitter","Recoiler","Inspection","Packaging","Coil warehouse","Shipping truck","Overhead crane","Incoming coil yard"})
                Require(extension.GetComponentsInChildren<Transform>(true).Any(t=>t.name==name),name+" installed");
            var aisle=extension.Find("Extended pedestrian aisle");
            var space=new Bounds(new Vector3(aisle.position.x,1.1f,aisle.position.z),new Vector3(aisle.localScale.x,2.2f,1.5f));
            foreach(var r in extension.GetComponentsInChildren<MeshRenderer>(true).Where(r=>r.GetComponent<TextMesh>()==null && r.bounds.min.y<2.2f && r.bounds.max.y>.05f))
                Require(!space.Intersects(r.bounds),"extended walkway clears "+r.name);
            demo.SetExteriorView(false); FactoryChecks.Capture(Path.Combine(dir,"factory-campus-interior.png"));
            demo.SetExteriorView(true); FactoryChecks.Capture(Path.Combine(dir,"factory-campus-exterior.png"));
            demo.Disconnect("test");
            Require(count("StoredCount")==0 && count("InTransitCount")==0,"disconnect clears inferred session loads");
            File.WriteAllText(Path.Combine(dir,"logistics-result.txt"),"PASS: complete virtual line, retained coils, pause, warehouse, shipping, capacity, walkway, reset");
            EditorApplication.Exit(0);
        } catch(Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
    static void Require(bool ok,string message) { if(!ok) throw new Exception("FAIL: "+message); Debug.Log("PASS: "+message); }
}
