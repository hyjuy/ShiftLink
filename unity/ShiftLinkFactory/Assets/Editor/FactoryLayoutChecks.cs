using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class FactoryLayoutChecks
{
    public static Bounds BoundsOf(Transform node)
    {
        var renderers=node.GetComponentsInChildren<MeshRenderer>().Where(r=>r.GetComponent<TextMesh>()==null).ToArray();
        var bounds=renderers[0].bounds;
        foreach(var r in renderers.Skip(1)) bounds.Encapsulate(r.bounds);
        return bounds;
    }
    public static void Run()
    {
        var failures=new List<string>();
        Action<bool,string> check=(ok,label)=>{ if(!ok) failures.Add(label); Debug.Log((ok ? "PASS: " : "FAIL: ")+label); };
        try {
            FactoryAssetBuilder.Prepare();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            string dir=Path.Combine(Application.dataPath,"../Checks");
            var config=JsonUtility.FromJson<ConfigEnvelope>(File.ReadAllText(Path.Combine(dir,"config.json"))).config;
            var state=JsonUtility.FromJson<MesSnapshot>(File.ReadAllText(Path.Combine(dir,"state.json")));
            var demo=new GameObject("Layout review").AddComponent<FactoryDemo>();
            demo.CreateEnvironment(); demo.Build(config); demo.Apply(state);
            var nodes=demo.transform.Find("MES equipment");
            var building=demo.transform.Find("Factory building");
            check(building!=null && building.Find("Exterior envelope")!=null,"factory walls and roof installed");
            check(building!=null && building.GetComponentsInChildren<Light>(true).Count(l=>l.type==LightType.Spot && l.intensity>0)>=16,"interior and exterior working lights installed");
            check(building!=null && building.Find("Personnel entry route")!=null,"personnel entrance connects walkway");
            check(typeof(FactoryDemo).GetMethod("SetExteriorView")!=null,"exterior and interior view toggle available");
            check(demo.EquipmentCount==config.equipment.Length,"auxiliary rollers do not create MES equipment");
            var beds=nodes.Find("Auxiliary roller beds");
            check(beds!=null && beds.GetComponentsInChildren<Transform>().Count(t=>t.name.StartsWith("Auxiliary roller_") && t.childCount>0)>=30,"additional inlet outlet and transfer rollers");
            var pedestrianAreas=new[]{"Pedestrian aisle","Maintenance aisle","Aisle connection","Stair approach","Stair entrance"};
            foreach(var name in pedestrianAreas) {
                var area=nodes.Find(name);
                if(area==null) { check(false,name+" provided"); continue; }
                var footprint=BoundsOf(area);
                check(Mathf.Min(footprint.size.x,footprint.size.z)>=1.49f,name+" minimum 1.5m width");
                var headspace=new Bounds(new Vector3(footprint.center.x,1.1f,footprint.center.z),new Vector3(footprint.size.x,2.2f,footprint.size.z));
                var blocked=nodes.GetComponentsInChildren<MeshRenderer>().Where(r=>r.GetComponent<TextMesh>()==null && r.bounds.max.y>.05f && r.bounds.min.y<2.2f && headspace.Intersects(r.bounds)).Select(r=>r.name).Distinct().ToArray();
                check(blocked.Length==0,name+" clear 2.2m headroom "+string.Join(",",blocked));
                foreach(var line in nodes.GetComponentsInChildren<LineRenderer>().Where(l=>l.name.StartsWith("Power cable") || l.name.StartsWith("Hydraulic") || l.name.StartsWith("Assumed hydraulic") || l.name=="CAU air riser")) {
                    bool clear=true;
                    for(int i=1;i<line.positionCount;i++) {
                        var a=line.GetPosition(i-1); var delta=line.GetPosition(i)-a; float hit;
                        if(headspace.Contains(a) || (headspace.IntersectRay(new Ray(a,delta.normalized),out hit) && hit<=delta.magnitude)) clear=false;
                    }
                    check(clear,name+" headroom clears "+line.name);
                }
            }
            if(beds!=null) {
                var aux=beds.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("Auxiliary roller_") && t.childCount>0);
                var auxiliaryRotation=aux.rotation; demo.AdvanceVisuals(.1f);
                check(Quaternion.Angle(auxiliaryRotation,aux.rotation)>.01f,"auxiliary rollers follow MES running speed");
                state.line_mode="paused"; demo.Apply(state); auxiliaryRotation=aux.rotation; demo.AdvanceVisuals(.1f);
                check(Quaternion.Angle(auxiliaryRotation,aux.rotation)<.001f,"auxiliary rollers stop on pause");
                state.line_mode="running"; demo.Apply(state);
            }
            foreach(string id in new[]{"EQ-0001","EQ-0002","EQ-0003","EQ-0004","EQ-0005"}) {
                var model=nodes.Find(id).Find("Equipment_"+config.equipment.First(e=>e.equipment_id==id).profile_id.ToUpperInvariant()).Find("Model");
                check(Mathf.Abs(model.localScale.x-1)<.001f,"native metres "+id);
            }
            var specs=config.equipment.Where(e=>e.active).ToArray();
            for(int i=0;i<specs.Length;i++) for(int j=i+1;j<specs.Length;j++)
                check(!BoundsOf(nodes.Find(specs[i].equipment_id)).Intersects(BoundsOf(nodes.Find(specs[j].equipment_id))),"equipment clearance "+specs[i].code+" / "+specs[j].code);
            var platform=nodes.Find("CAU utility platform");
            var cau=BoundsOf(nodes.Find("EQ-0003")); var support=BoundsOf(platform);
            check(support.min.x<=cau.min.x && support.max.x>=cau.max.x && support.min.z<=cau.min.z && support.max.z>=cau.max.z,"CAU fully supported");
            check(nodes.Find("CAU access stairs")!=null && nodes.Find("CAU platform rail")!=null,"CAU stairs and rails");
            check(nodes.GetComponentsInChildren<Transform>().Any(t=>t.name=="Connection_ScrapChute"),"scrap branch chute rendered");
            check(nodes.Find("Pedestrian aisle")!=null && nodes.Find("Maintenance aisle")!=null && nodes.Find("Incoming staging")!=null && nodes.Find("Outgoing staging")!=null && nodes.Find("Scrap collection bin")!=null,"logistics and maintenance areas");
            if(nodes.Find("Scrap collection bin")!=null && nodes.Find("Pedestrian aisle")!=null) {
                var bin=BoundsOf(nodes.Find("Scrap collection bin")); var aisle=BoundsOf(nodes.Find("Pedestrian aisle"));
                check(bin.max.z<aisle.min.z || bin.min.z>aisle.max.z,"scrap collection outside pedestrian aisle");
            }
            var cables=nodes.GetComponentsInChildren<LineRenderer>().Where(l=>l.name.StartsWith("Power cable")).ToArray();
            check(cables.Length==3 && cables.All(l=>l.GetPosition(1).y>=2.8f),"power routed overhead");
            foreach(var line in nodes.GetComponentsInChildren<LineRenderer>().Where(l=>l.name.StartsWith("Power cable") || l.name.StartsWith("Hydraulic supply") || l.name.StartsWith("Assumed hydraulic return") || l.name=="CAU air riser")) {
                string type=line.name.StartsWith("Power") ? "power_supply" : line.name=="CAU air riser" ? "pneumatic_supply" : "hydraulic_supply";
                var relation=config.relations.First(r=>r.relation_type==type && (line.name=="CAU air riser" || line.name.EndsWith(r.to_id)));
                foreach(var spec in specs.Where(e=>e.equipment_id!=relation.from_id && e.equipment_id!=relation.to_id)) {
                    var bounds=BoundsOf(nodes.Find(spec.equipment_id)); bool clear=true;
                    for(int i=1;i<line.positionCount;i++) {
                        var a=line.GetPosition(i-1); var delta=line.GetPosition(i)-a; float hit;
                        if(bounds.Contains(a) || (bounds.IntersectRay(new Ray(a,delta.normalized),out hit) && hit<=delta.magnitude)) clear=false;
                    }
                    check(clear,line.name+" clears "+spec.code);
                }
            }
            foreach(string area in new[]{"Pedestrian aisle","Maintenance aisle","Aisle connection","Stair approach","Stair entrance"}) {
                var aisle=nodes.Find(area);
                if(aisle==null) { check(false,area+" exists"); continue; }
                var a=BoundsOf(aisle);
                foreach(var spec in specs) {
                    var b=BoundsOf(nodes.Find(spec.equipment_id));
                    check(a.max.x<=b.min.x || a.min.x>=b.max.x || a.max.z<=b.min.z || a.min.z>=b.max.z,area+" clears "+spec.code);
                }
            }
            var coil=demo.transform.Find("MES coils").GetChild(0);
            var reading=state.coils.First(c=>c.coil_id==coil.name);
            var speed=state.measurements.First(m=>m.equipment_id==reading.equipment_id && m.signal=="rt_speed");
            speed.value=30; speed.quality="good"; reading.position=Mathf.Min(.9f,reading.position+.2f);
            demo.Apply(state); var old=coil.position; demo.AdvanceVisuals(.1f);
            check(Mathf.Abs(Vector3.Distance(old,coil.position)-.05f)<.002f,"coil follows 30 m/min");
            speed.quality="unavailable"; demo.Apply(state); old=coil.position; demo.AdvanceVisuals(.1f);
            check(Vector3.Distance(old,coil.position)<.001f,"missing speed stops coil");
            FactoryChecks.Capture(Path.Combine(dir,"layout-factory.png"));
            File.WriteAllText(Path.Combine(dir,"layout-result.txt"),failures.Count==0 ? "PASS: dimensions, clearance, platform, branch, utility routes, speed, logistics" : string.Join("\n",failures));
            EditorApplication.Exit(failures.Count==0 ? 0 : 1);
        } catch(Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
    }
}
