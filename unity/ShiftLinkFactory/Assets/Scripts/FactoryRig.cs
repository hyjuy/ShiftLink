using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Synthetic MES visualization. Position is authoritative; gearing and cradle geometry are assumptions.
public class FactoryRig : MonoBehaviour
{
    Dictionary<string,GameObject> equipment;
    FactoryConfig config;
    readonly List<Tuple<string,Transform,Vector3,float>> rotating=new List<Tuple<string,Transform,Vector3,float>>();
    readonly Dictionary<string,List<Transform>> beltMarkers=new Dictionary<string,List<Transform>>();
    readonly List<Material> owned=new List<Material>();
    readonly Dictionary<Color,Material> colors=new Dictionary<Color,Material>();
    Material Solid(Color color)
    {
        Material mat;
        if(!colors.TryGetValue(color,out mat)) { mat=new Material(Shader.Find("Standard")); mat.color=color; owned.Add(mat); colors[color]=mat; }
        return mat;
    }
    public static Vector3 Layout(string code,int index,int count,int auxiliary)
    {
        if(index>=0) return new Vector3((index-(count-1)*.5f)*5.4f,0,0);
        switch(code) {
            case "GR-01": return new Vector3(-11,0,3);
            case "GR-02": return new Vector3(0,0,3);
            case "HPU-01": return new Vector3(-6,0,6);
            case "PDP-01": return new Vector3(-2,0,6);
            case "CAU-01": return new Vector3(2,3.2f,6);
            case "CV-02": return new Vector3(5.4f,0,-4);
            default: return new Vector3(auxiliary*3,0,9);
        }
    }
    static GameObject Asset(string name,Transform parent)
    {
        var prefab=Resources.Load<GameObject>("Factory/"+name);
        if(prefab==null) throw new InvalidOperationException("Missing imported factory prefab: "+name+"; run FactoryAssetBuilder.Prepare");
        var obj=Instantiate(prefab,parent); obj.name=name; return obj;
    }
    public static void InstantiateEquipment(EquipmentSpec spec,Transform parent)
    {
        string typ=(spec.profile_id??"pdp").ToUpperInvariant();
        var model=Asset(spec.code=="RT-02" ? "Equipment_RT02" : "Equipment_"+typ,parent);
        if(typ=="GR") {
            var output=model.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("OutputShaft") && t.childCount>0);
            if(output.position.x<parent.position.x) model.transform.localRotation=Quaternion.Euler(0,180,0)*model.transform.localRotation;
        }
        if(spec.code=="CV-02") {
            parent.localRotation=Quaternion.Euler(0,90,0);
            foreach(var t in model.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("DiverterArm") || t.name.StartsWith("Pneumatic") || t.name.StartsWith("AirHose") || t.name.StartsWith("HydraulicTensioner") || t.name.StartsWith("TensionerSlide") || t.name.StartsWith("BeltTop") || t.name.StartsWith("BeltReturn")).ToArray()) t.gameObject.SetActive(false);
        }
        if(spec.code=="RT-03") {
            var scrap=new GameObject("ScrapOutputAnchor_RT").transform; scrap.SetParent(parent); scrap.localPosition=new Vector3(1.7f,1.22f,-.85f);
        }
        var bounds=new Bounds(parent.position,Vector3.zero);
        foreach(var r in model.GetComponentsInChildren<Renderer>()) bounds.Encapsulate(r.bounds);
        var collider=parent.gameObject.AddComponent<BoxCollider>();
        collider.center=parent.InverseTransformPoint(bounds.center);
        var size=parent.InverseTransformVector(bounds.size); collider.size=new Vector3(Mathf.Abs(size.x),Mathf.Abs(size.y),Mathf.Abs(size.z));
    }
    Transform Anchor(string id,string name)
    {
        return equipment[id].GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith(name));
    }
    GameObject Block(string name,Vector3 pos,Vector3 size,Color color)
    {
        var obj=GameObject.CreatePrimitive(PrimitiveType.Cube); obj.name=name; obj.transform.SetParent(transform); obj.transform.position=pos; obj.transform.localScale=size;
        obj.GetComponent<Renderer>().sharedMaterial=Solid(color);
        DestroyImmediate(obj.GetComponent<Collider>()); return obj;
    }
    void Segment(string asset,Vector3 a,Vector3 b,Vector3 originOffset,string driveId=null)
    {
        var delta=b-a; if(delta.magnitude<.001f) return;
        var obj=Asset(asset,transform);
        var rotation=Quaternion.FromToRotation(Vector3.right,delta.normalized);
        obj.transform.rotation=rotation; obj.transform.position=(a+b)*.5f-rotation*originOffset;
        obj.transform.localScale=new Vector3(delta.magnitude,1,1);
        if(driveId!=null) {
            var pivot=obj.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("RotationPivot"));
            rotating.Add(Tuple.Create(driveId,pivot,delta.normalized,.12f));
        }
    }
    void Pipe(string name,Vector3[] points,Color color)
    {
        var obj=new GameObject(name); obj.transform.SetParent(transform);
        var line=obj.AddComponent<LineRenderer>(); line.positionCount=points.Length; line.SetPositions(points); line.widthMultiplier=.045f; line.numCornerVertices=4; line.numCapVertices=4;
        line.sharedMaterial=Solid(color);
    }
    public void Build(FactoryConfig next,Dictionary<string,GameObject> nodes)
    {
        config=next; equipment=nodes;
        foreach(var spec in next.equipment) {
            var node=nodes[spec.equipment_id];
            foreach(var t in node.GetComponentsInChildren<Transform>()) {
                if(t.name.StartsWith("Roller_") && t.childCount>0) rotating.Add(Tuple.Create(spec.equipment_id,t,node.transform.TransformDirection(Vector3.forward),.12f));
                if(t.name.StartsWith("HeadDrum") || t.name.StartsWith("TailDrum")) {
                    if(t.childCount>0) rotating.Add(Tuple.Create(spec.equipment_id,t,node.transform.TransformDirection(Vector3.forward),.175f));
                }
                if(t.name.StartsWith("OutputShaft") && t.childCount>0) rotating.Add(Tuple.Create(spec.equipment_id,t,Vector3.right,.12f));
            }
            if(spec.profile_id=="cv") {
                var markers=new List<Transform>(); beltMarkers[spec.equipment_id]=markers;
                bool scrap=spec.code=="CV-02"; int count=scrap ? 24 : 12;
                for(int i=0;i<count;i++) {
                    var marker=Block(scrap ? "Scrap belt slat" : "Belt travel marker",Vector3.zero,new Vector3(scrap ? .19f : .03f,scrap ? .045f : .008f,1.4f),scrap ? new Color(.55f,.59f,.63f) : new Color(.25f,.28f,.3f));
                    marker.transform.SetParent(node.transform); marker.transform.localPosition=new Vector3(-2.3f+i*4.8f/count,1.185f,0); marker.transform.localRotation=Quaternion.identity; markers.Add(marker.transform);
                }
            }
        }
        // Raised CAU utility platform follows the catalog's second-floor location.
        Block("CAU utility platform",new Vector3(2,3.05f,6),new Vector3(3.8f,.3f,2),FactoryRules.Grey);
        for(int x=-1;x<=1;x+=2) for(int z=-1;z<=1;z+=2) Block("Platform support",new Vector3(2+x*1.5f,1.5f,6+z*.8f),new Vector3(.15f,3,.15f),FactoryRules.Grey);
        foreach(var rel in next.relations??new RelationSpec[0]) {
            if(!nodes.ContainsKey(rel.from_id) || !nodes.ContainsKey(rel.to_id)) continue;
            Vector3 a=nodes[rel.from_id].transform.position,b=nodes[rel.to_id].transform.position;
            if(rel.relation_type=="material_flow") {
                bool branch=Array.IndexOf(next.route,rel.to_id)<0;
                var start=Anchor(rel.from_id,branch ? "ScrapOutputAnchor_" : "OutputAnchor_").position; var end=Anchor(rel.to_id,"InputAnchor_").position;
                if(nodes[rel.to_id].transform.localRotation!=Quaternion.identity) {
                    var chute=Asset("Connection_ScrapChute",transform); chute.transform.position=(start+end)*.5f-Vector3.up*.2f;
                    chute.transform.rotation=Quaternion.FromToRotation(Vector3.right,(end-start).normalized); chute.transform.localScale=new Vector3((end-start).magnitude,1,1);
                } else {
                    var bridge=Asset("Connection_TransferBridge",transform); bridge.transform.position=(start+end)*.5f-Vector3.up*.38f;
                }
            } else if(rel.relation_type=="drive") {
                var output=nodes[rel.from_id].GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("OutputShaft") && t.childCount>0);
                var start=output.position+Vector3.right*.25f;
                var input=nodes[rel.to_id].GetComponentsInChildren<Transform>().FirstOrDefault(t=>t.name.StartsWith("DriveInput"));
                if(input==null) input=nodes[rel.to_id].GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("HeadDrum") && t.childCount>0);
                var end=input.position;
                var junction=new Vector3(end.x,start.y,a.z);
                Segment("Connection_DriveShaft",start,junction,new Vector3(0,.2f,0),rel.from_id);
                Block("Assumed right-angle distributor",junction,new Vector3(.3f,.3f,.3f),FactoryRules.Grey);
                var side=new Vector3(end.x,start.y,end.z);
                Segment("Connection_DriveShaft",junction,side,new Vector3(0,.2f,0),rel.from_id);
                var coupling=Asset("Connection_FlexibleCoupling",transform); coupling.transform.position=start-Vector3.up*.15f;
                rotating.Add(Tuple.Create(rel.from_id,coupling.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("RotationPivot")),Vector3.right,.12f));
                var guard=Asset("Connection_ShaftGuard",transform); guard.transform.position=start-Vector3.up*.17f;
                var bearing=Asset("Connection_BearingPedestal",transform); bearing.transform.position=(start+junction)*.5f-Vector3.up*.23f;
                Block("Guarded chain drive",(side+end)*.5f,new Vector3(.3f,Mathf.Max(.2f,Mathf.Abs(end.y-side.y)),.2f),FactoryRules.Amber);
            } else if(rel.relation_type=="hydraulic_supply") {
                var start=a+new Vector3(1,.6f,0); var end=b+new Vector3(1.2f,1.6f,.94f);
                if(next.equipment.First(e=>e.equipment_id==rel.to_id).profile_id=="cv") end=b+new Vector3(-1.8f,.8f,-1);
                Pipe("Hydraulic supply "+rel.to_id,new[]{start,new Vector3(start.x,.45f,2),new Vector3(end.x,.45f,2),end},new Color(.1f,.6f,.7f));
                Pipe("Assumed hydraulic return "+rel.to_id,new[]{end+Vector3.forward*.1f,new Vector3(end.x,.45f,2.1f),new Vector3(start.x,.45f,2.1f),start+Vector3.forward*.1f},FactoryRules.Grey);
            } else if(rel.relation_type=="power_supply") {
                Pipe("Power cable "+rel.to_id,new[]{a+new Vector3(0,.15f,.4f),new Vector3(a.x,.15f,4.7f),new Vector3(b.x,.15f,4.7f),b+new Vector3(-.68f,.91f,0)},Color.black);
            } else if(rel.relation_type=="pneumatic_supply") {
                Pipe("CAU air riser",new[]{a+new Vector3(1.6f,1.8f,0),new Vector3(a.x+1.6f,2.5f,5.1f),new Vector3(b.x+.7f,2.5f,5.1f),b+new Vector3(.7f,.45f,1.06f)},new Color(.2f,.5f,.9f));
            }
        }
        for(int i=0;i<13;i++) { var tray=Asset("Connection_CableTray",transform); tray.transform.position=new Vector3(-7+i,.06f,4.7f); }
    }
    public Vector3 MaterialPosition(string id,float position)
    {
        var start=Anchor(id,"InputAnchor_").position; var end=Anchor(id,"OutputAnchor_").position;
        int index=Array.IndexOf(config.route,id);
        if(index>=0 && index+1<config.route.Length) end=Anchor(config.route[index+1],"InputAnchor_").position;
        return Vector3.Lerp(start,end,position)+Vector3.up*.02f;
    }
    public Vector3[] TransferWaypoints(string from,string to)
    {
        bool branch=(config.branches??new BranchSpec[0]).Any(b=>b.from_id==from && b.to_id==to);
        if(!branch && !(config.relations??new RelationSpec[0]).Any(r=>r.relation_type=="material_flow" && r.from_id==from && r.to_id==to)) return new Vector3[0];
        return new[]{Anchor(from,branch ? "ScrapOutputAnchor_" : "OutputAnchor_").position+Vector3.up*.02f,Anchor(to,"InputAnchor_").position+Vector3.up*.02f};
    }
    public static Transform CreateLoad(string id,Transform parent,bool scrap)
    {
        var load=new GameObject(id); load.transform.SetParent(parent);
        if(scrap) {
            var sheet=GameObject.CreatePrimitive(PrimitiveType.Cube); sheet.name="Rejected cut sheet"; sheet.transform.SetParent(load.transform); sheet.transform.localScale=new Vector3(.8f,.02f,.58f); sheet.transform.localPosition=Vector3.up*.01f;
        } else {
            var coil=Asset("Material_Coil",load.transform); coil.transform.localPosition=Vector3.up*.14f;
            // A synthetic saddle carries the coil; it does not free-roll through clamps.
            foreach(float side in new[]{-.27f,.27f}) {
                var saddle=GameObject.CreatePrimitive(PrimitiveType.Cube); saddle.name="Assumed transport saddle"; saddle.transform.SetParent(load.transform); saddle.transform.localPosition=new Vector3(side,.09f,0); saddle.transform.localScale=new Vector3(.65f,.12f,.9f); saddle.transform.localRotation=Quaternion.Euler(0,0,side<0 ? -20 : 20);
            }
        }
        return load.transform;
    }
    public void Advance(MesSnapshot snapshot,float dt)
    {
        if(snapshot.line_mode!="running") return;
        var readings=snapshot.equipment.ToDictionary(e=>e.equipment_id);
        var speeds=new Dictionary<string,float>();
        foreach(var m in snapshot.measurements??new MeasurementReading[0])
            if((m.signal=="rt_speed" || m.signal=="cv_speed") && m.unit=="m_min" && m.quality=="good" && !float.IsNaN(m.value) && !float.IsInfinity(m.value)) speeds[m.equipment_id]=Mathf.Max(0,m.value)/60;
        foreach(var spec in config.equipment.Where(e=>e.profile_id=="gr")) {
            var driven=(config.relations??new RelationSpec[0]).Where(r=>r.from_id==spec.equipment_id && r.relation_type=="drive").Select(r=>r.to_id);
            speeds[spec.equipment_id]=driven.Where(id=>speeds.ContainsKey(id) && readings.ContainsKey(id) && readings[id].operating_state=="running" && readings[id].fault_level!="critical").Select(id=>speeds[id]).DefaultIfEmpty(0).Max();
        }
        foreach(var part in rotating) {
            float speed; EquipmentReading state;
            if(speeds.TryGetValue(part.Item1,out speed) && readings.TryGetValue(part.Item1,out state) && state.operating_state=="running" && state.fault_level!="critical")
                part.Item2.RotateAround(part.Item2.position,part.Item3,-speed/part.Item4*Mathf.Rad2Deg*dt);
        }
        foreach(var pair in beltMarkers) {
            float speed; EquipmentReading state; if(!readings.TryGetValue(pair.Key,out state)) continue;
            if(!speeds.TryGetValue(pair.Key,out speed) || state.operating_state!="running" || state.fault_level=="critical") continue;
            foreach(var marker in pair.Value) { var p=marker.localPosition; p.x=Mathf.Repeat(p.x+2.4f+speed*dt,4.8f)-2.4f; marker.localPosition=p; }
        }
    }
    void OnDestroy() { foreach(var mat in owned) { if(Application.isPlaying) Destroy(mat); else DestroyImmediate(mat); } }
}
