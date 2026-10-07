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
    Transform auxiliaryBeds;
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
            case "GR-01": return new Vector3(-(count-1)*2.7f-3.8f,0,3);
            case "GR-02": return new Vector3((count-3)*2.7f-3.8f,0,3);
            case "HPU-01": return new Vector3(-6,0,8);
            case "PDP-01": return new Vector3(-2,0,8);
            case "CAU-01": return new Vector3(3,3.2f,8);
            case "CV-02": return new Vector3((count-3)*2.7f+1.7f,0,-4);
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
    void Rail(string name,Vector3 a,Vector3 b)
    {
        Pipe(name,new[]{a,b},FactoryRules.Amber);
        int count=Mathf.Max(1,Mathf.CeilToInt(Vector3.Distance(a,b)/1.2f));
        for(int i=0;i<=count;i++) {
            var p=Vector3.Lerp(a,b,(float)i/count);
            Block(name+" post",p-Vector3.up*.5f,new Vector3(.06f,1,.06f),FactoryRules.Amber);
        }
    }
    void GuardedShaft(Vector3 a,Vector3 b,string driveId)
    {
        Segment("Connection_DriveShaft",a,b,new Vector3(0,.2f,0),driveId);
        var delta=b-a;
        if(delta.magnitude<.001f) return;
        var cover=Block("Drive shaft guard",(a+b)*.5f,new Vector3(delta.magnitude,.28f,.28f),FactoryRules.Grey);
        cover.transform.rotation=Quaternion.FromToRotation(Vector3.right,delta.normalized);
        int count=Mathf.Max(1,Mathf.CeilToInt(delta.magnitude/2.5f));
        for(int i=0;i<count;i++) {
            var p=Vector3.Lerp(a,b,(i+.5f)/count);
            Block("Shaft support",new Vector3(p.x,p.y*.5f,p.z),new Vector3(.12f,p.y,.12f),FactoryRules.Grey);
        }
    }
    void AccessAndLogistics(FactoryConfig next)
    {
        if(next.equipment.Any(e=>e.code=="CAU-01" && e.active)) {
            var p=EquipmentPosition(next,"CAU-01");
            Block("CAU utility platform",p-Vector3.up*.15f,new Vector3(4.8f,.3f,2.8f),FactoryRules.Grey);
            foreach(float x in new[]{-2.1f,2.1f}) foreach(float z in new[]{-1.1f,1.1f})
                Block("Platform support",p+new Vector3(x,-1.75f,z),new Vector3(.15f,2.9f,.15f),FactoryRules.Grey);
            Rail("CAU platform rail",p+new Vector3(-2.4f,1,-1.4f),p+new Vector3(2.4f,1,-1.4f));
            Rail("CAU back rail",p+new Vector3(-2.4f,1,1.4f),p+new Vector3(2.4f,1,1.4f));
            Rail("CAU left rail",p+new Vector3(-2.4f,1,-1.4f),p+new Vector3(-2.4f,1,1.4f));
            Block("CAU stair landing",p+new Vector3(3.4f,-.15f,0),new Vector3(3.2f,.3f,1.5f),FactoryRules.Grey);
            var stairs=new GameObject("CAU access stairs").transform; stairs.SetParent(transform);
            for(int i=0;i<16;i++) {
                var step=Block("Stair tread",p+new Vector3(4.4f,(i+1)*.2f-p.y-.1f,4-(i+.5f)*.25f),new Vector3(1.5f,.2f,.25f),FactoryRules.Grey);
                step.transform.SetParent(stairs);
            }
            foreach(float x in new[]{3.65f,5.15f})
                Rail("Stair handrail",p+new Vector3(x,1-p.y,4),p+new Vector3(x,1,0));
        }
        float left=-(next.route.Length-1)*2.7f-2.4f, right=-left;
        Block("Pedestrian aisle",new Vector3(0,-.035f,-9.5f),new Vector3(right-left+15,.012f,1.5f),new Color(.12f,.4f,.3f));
        Block("Maintenance aisle",new Vector3((left-6.3f+9.65f)*.5f,-.035f,5.6f),new Vector3(9.65f-left+6.3f,.012f,1.5f),new Color(.12f,.4f,.3f));
        Block("Aisle connection",new Vector3(left-6.3f,-.035f,-1.95f),new Vector3(1.5f,.012f,16.6f),new Color(.12f,.4f,.3f));
        Block("Stair approach",new Vector3(9.2f,-.035f,9.175f),new Vector3(1.5f,.012f,8.65f),new Color(.12f,.4f,.3f));
        Block("Stair entrance",new Vector3(8.3f,-.035f,12.85f),new Vector3(3.3f,.012f,1.5f),new Color(.12f,.4f,.3f));
        Block("Incoming staging",new Vector3(left-2,-.025f,0),new Vector3(3,.012f,3),FactoryRules.Amber);
        Block("Outgoing staging",new Vector3(right+2,-.025f,0),new Vector3(3,.012f,3),FactoryRules.Amber);
        if(next.route.Length>0) {
            string first=next.route[0],last=next.route[next.route.Length-1];
            if(equipment[first].activeSelf && equipment[last].activeSelf) {
                var inlet=Anchor(first,"InputAnchor_").position;
                var outlet=Anchor(last,"OutputAnchor_").position;
                RollerBed("Inlet roller bed",inlet-Vector3.right*4.8f,inlet,first);
                RollerBed("Outlet roller bed",outlet,outlet+Vector3.right*4.8f,last);
            }
        }
        if(next.equipment.Any(e=>e.code=="CV-02" && e.active)) {
            var p=EquipmentPosition(next,"CV-02")+new Vector3(0,0,-3.4f);
            Block("Scrap collection bin",p+Vector3.up*.2f,new Vector3(2,.15f,1.6f),FactoryRules.Grey);
            foreach(float x in new[]{-1f,1f}) Block("Scrap bin wall",p+new Vector3(x,.6f,0),new Vector3(.08f,.8f,1.6f),FactoryRules.Amber);
            Block("Scrap bin rear",p+new Vector3(0,.6f,-.8f),new Vector3(2,.8f,.08f),FactoryRules.Amber);
        }
    }
    Vector3 EquipmentPosition(FactoryConfig next,string code)
    {
        return equipment[next.equipment.First(e=>e.code==code).equipment_id].transform.position;
    }
    void RollerBed(string name,Vector3 start,Vector3 end,string speedId)
    {
        var source=equipment.Values.Where(e=>e.activeSelf).SelectMany(e=>e.GetComponentsInChildren<Transform>()).FirstOrDefault(t=>t.name=="Roller_01" && t.childCount>0);
        if(source==null) return;
        var bed=new GameObject(name).transform; bed.SetParent(auxiliaryBeds);
        float length=Vector3.Distance(start,end);
        int count=Mathf.Max(2,Mathf.CeilToInt(length/.4f));
        var bearings=source.parent.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("BearingBlock")).GroupBy(t=>Mathf.Sign(t.position.z)).Select(g=>g.First()).ToArray();
        for(int i=0;i<count;i++) {
            var top=Vector3.Lerp(start,end,(i+.5f)/count);
            var roller=Instantiate(source.gameObject,bed).transform; roller.name="Auxiliary roller_"+(i+1).ToString("00");
            roller.position=top-Vector3.up*.12f; roller.rotation=source.rotation; roller.localScale=source.lossyScale;
            rotating.Add(Tuple.Create(speedId,roller,Vector3.forward,.12f));
            foreach(var template in bearings) {
                var bearing=Instantiate(template.gameObject,bed).transform;
                bearing.position=new Vector3(top.x,template.position.y,template.position.z); bearing.rotation=template.rotation; bearing.localScale=template.lossyScale;
            }
        }
        foreach(float z in new[]{-.85f,.85f}) {
            var frame=Block("Roller bed frame",(start+end)*.5f+new Vector3(0,-.4f,z),new Vector3(length,.18f,.12f),new Color(.12f,.3f,.42f)); frame.transform.SetParent(bed);
            int supports=Mathf.Max(2,Mathf.CeilToInt(length/1.6f));
            for(int i=0;i<supports;i++) {
                var point=Vector3.Lerp(start,end,(i+.5f)/supports);
                var leg=Block("Roller bed leg",new Vector3(point.x,.4f,z),new Vector3(.12f,.8f,.12f),FactoryRules.Grey); leg.transform.SetParent(bed);
                var foot=Block("Roller bed foot",new Vector3(point.x,.04f,z),new Vector3(.26f,.08f,.26f),FactoryRules.Grey); foot.transform.SetParent(bed);
            }
        }
    }
    public void Build(FactoryConfig next,Dictionary<string,GameObject> nodes)
    {
        config=next; equipment=nodes;
        auxiliaryBeds=new GameObject("Auxiliary roller beds").transform; auxiliaryBeds.SetParent(transform);
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
        AccessAndLogistics(next);
        var relations=(next.relations??new RelationSpec[0]).Concat((next.branches??new BranchSpec[0]).Select(br=>new RelationSpec {from_id=br.from_id,to_id=br.to_id,relation_type="material_flow"}));
        var drivePorts=new HashSet<string>();
        foreach(var rel in relations.GroupBy(r=>r.relation_type+":"+r.from_id+":"+r.to_id).Select(g=>g.First())) {
            if(!nodes.ContainsKey(rel.from_id) || !nodes.ContainsKey(rel.to_id)) continue;
            if(!nodes[rel.from_id].activeSelf || !nodes[rel.to_id].activeSelf) continue;
            Vector3 a=nodes[rel.from_id].transform.position,b=nodes[rel.to_id].transform.position;
            int utilityLane=relations.Where(r=>r.from_id==rel.from_id && r.relation_type==rel.relation_type).Select(r=>r.to_id).Distinct().OrderBy(id=>id).ToList().IndexOf(rel.to_id);
            if(rel.relation_type=="material_flow") {
                bool branch=Array.IndexOf(next.route,rel.to_id)<0;
                var start=Anchor(rel.from_id,branch ? "ScrapOutputAnchor_" : "OutputAnchor_").position; var end=Anchor(rel.to_id,"InputAnchor_").position;
                if(nodes[rel.to_id].transform.localRotation!=Quaternion.identity) {
                    var chute=Asset("Connection_ScrapChute",transform); chute.transform.position=(start+end)*.5f-Vector3.up*.2f;
                    chute.transform.rotation=Quaternion.FromToRotation(Vector3.right,(end-start).normalized); chute.transform.localScale=new Vector3((end-start).magnitude,1,1);
                } else {
                    RollerBed("Transfer roller bed "+rel.from_id+" to "+rel.to_id,start,end,rel.from_id);
                }
            } else if(rel.relation_type=="drive") {
                var output=nodes[rel.from_id].GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("OutputShaft") && t.childCount>0);
                var start=output.position+Vector3.right*.25f;
                var input=nodes[rel.to_id].GetComponentsInChildren<Transform>().FirstOrDefault(t=>t.name.StartsWith("DriveInput"));
                if(input==null) input=nodes[rel.to_id].GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("HeadDrum") && t.childCount>0);
                var end=input.position;
                // Each target gets a distinct shaft lane behind the transport line.
                float lane=a.z+(Array.IndexOf(next.route,rel.to_id)%2==0 ? -.35f : .35f);
                var rear=new Vector3(start.x,start.y,lane);
                var junction=new Vector3(end.x,start.y,lane);
                GuardedShaft(start,rear,rel.from_id);
                GuardedShaft(rear,junction,rel.from_id);
                Block("Assumed right-angle distributor",junction,new Vector3(.3f,.3f,.3f),FactoryRules.Grey);
                var side=new Vector3(end.x,start.y,end.z);
                GuardedShaft(junction,side,rel.from_id);
                // Both driven targets share this one gearbox output port.
                if(drivePorts.Add(rel.from_id)) {
                    var coupling=Asset("Connection_FlexibleCoupling",transform); coupling.transform.position=start-Vector3.up*.15f;
                    rotating.Add(Tuple.Create(rel.from_id,coupling.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("RotationPivot")),Vector3.right,.12f));
                    var guard=Asset("Connection_ShaftGuard",transform); guard.transform.position=start-Vector3.up*.17f;
                }
                var bearing=Asset("Connection_BearingPedestal",transform); bearing.transform.position=(start+junction)*.5f-Vector3.up*.23f;
                Block("Guarded chain drive",(side+end)*.5f,new Vector3(.3f,Mathf.Max(.2f,Mathf.Abs(end.y-side.y)),.2f),FactoryRules.Amber);
            } else if(rel.relation_type=="hydraulic_supply") {
                var start=a+new Vector3(1,.6f,utilityLane*.18f); var end=b+new Vector3(1.2f,1.6f,.94f);
                if(next.equipment.First(e=>e.equipment_id==rel.to_id).profile_id=="cv") end=b+new Vector3(-1.8f,.8f,-1);
                float supplyHeight=2.8f+utilityLane*.18f,returnHeight=supplyHeight+.08f;
                Pipe("Hydraulic supply "+rel.to_id,new[]{start,new Vector3(start.x,supplyHeight,6.7f),new Vector3(end.x,supplyHeight,6.7f),new Vector3(end.x,supplyHeight,1.7f),end},new Color(.1f,.6f,.7f));
                Pipe("Assumed hydraulic return "+rel.to_id,new[]{end+Vector3.forward*.1f,new Vector3(end.x,returnHeight,1.8f),new Vector3(end.x,returnHeight,6.8f),new Vector3(start.x,returnHeight,6.8f),start+Vector3.forward*.1f},FactoryRules.Grey);
            } else if(rel.relation_type=="power_supply") {
                float offset=(utilityLane-1)*.12f;
                Pipe("Power cable "+rel.to_id,new[]{a+new Vector3(offset,.91f,.4f),new Vector3(a.x+offset,4,7+offset),new Vector3(b.x,4,7+offset),b+new Vector3(-.68f,4,1.3f),b+new Vector3(-.68f,.91f,.6f)},Color.black);
            } else if(rel.relation_type=="pneumatic_supply") {
                Pipe("CAU air riser",new[]{a+new Vector3(-1.6f,1.8f,0),new Vector3(a.x-1.6f,5.8f,7.4f),new Vector3(b.x+.7f,5.8f,7.4f),new Vector3(b.x+.7f,5.8f,1.7f),b+new Vector3(.7f,.45f,1.06f)},new Color(.2f,.5f,.9f));
            }
        }
        var powered=relations.Where(r=>r.relation_type=="power_supply" && nodes.ContainsKey(r.to_id)).Select(r=>nodes[r.to_id].transform.position.x).ToArray();
        if(powered.Length>0) {
            float left=Mathf.Min(powered.Min(),-2), right=Mathf.Max(powered.Max(),-2);
            for(float x=left;x<right+.5f;x+=1) { var tray=Asset("Connection_CableTray",transform); tray.transform.position=new Vector3(x,3.92f,7); }
            foreach(float x in new[]{left,right}) Block("Cable tray support",new Vector3(x,2,7),new Vector3(.1f,4,.1f),FactoryRules.Grey);
        }
    }
    public Vector3 MaterialPosition(string id,float position)
    {
        var start=Anchor(id,"InputAnchor_").position; var end=Anchor(id,"OutputAnchor_").position;
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
    public static float TransportSpeed(MesSnapshot snapshot,string id)
    {
        var speed=(snapshot.measurements??new MeasurementReading[0]).FirstOrDefault(m=>m.equipment_id==id && (m.signal=="rt_speed" || m.signal=="cv_speed") && m.unit=="m_min" && m.quality=="good" && !float.IsNaN(m.value) && !float.IsInfinity(m.value));
        return speed==null ? 0 : Mathf.Max(0,speed.value)/60;
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
