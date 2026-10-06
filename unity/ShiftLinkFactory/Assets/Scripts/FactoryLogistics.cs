using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// A session-only virtual finishing line. These objects are not MES assets or inventory records.
public class FactoryLogistics : MonoBehaviour
{
    class Journey { public Transform load; public Queue<Vector3> path; public bool truck; public int slot=-1; }
    readonly List<Journey> journeys=new List<Journey>();
    readonly Dictionary<int,Transform> stored=new Dictionary<int,Transform>(), truck=new Dictionary<int,Transform>();
    readonly List<Transform> rollers=new List<Transform>();
    readonly Dictionary<Color,Material> materials=new Dictionary<Color,Material>();
    Transform campus,envelope,loads,shippingVehicle,incomingCarrier;
    readonly List<Transform> departing=new List<Transform>();
    float departureTime,feedTime;
    public bool SendToTruck { get; set; }
    public int StoredCount { get { return stored.Count; } }
    public int TruckCount { get { return truck.Count; } }
    public int InTransitCount { get { return journeys.Count; } }
    public string Summary { get { return "Virtual / session: warehouse "+StoredCount+"/24 | truck "+TruckCount+"/8 | transit "+InTransitCount; } }
    GameObject Shape(string name,Vector3 p,Vector3 s,Color c,PrimitiveType kind=PrimitiveType.Cube,Transform parent=null)
    {
        var obj=GameObject.CreatePrimitive(kind); obj.name=name; obj.transform.SetParent(parent??campus,false);
        obj.transform.localPosition=p; obj.transform.localScale=s;
        Material mat; if(!materials.TryGetValue(c,out mat)) { mat=new Material(Shader.Find("Standard")); mat.color=c; materials[c]=mat; }
        obj.GetComponent<Renderer>().sharedMaterial=mat; DestroyImmediate(obj.GetComponent<Collider>()); return obj;
    }
    void Label(string text,Vector3 p)
    {
        var t=new GameObject(text+" label").AddComponent<TextMesh>(); t.transform.SetParent(campus,false); t.transform.localPosition=p;
        t.text=text; t.anchor=TextAnchor.MiddleCenter; t.fontSize=48; t.characterSize=.16f; t.color=Color.white;
        t.transform.rotation=Quaternion.Euler(65,0,0);
    }
    public void Build()
    {
        campus=new GameObject("Virtual process campus").transform; campus.SetParent(transform,false);
        loads=new GameObject("Virtual dispatched coils").transform; loads.SetParent(campus,false);
        envelope=new GameObject("Finishing hall envelope").transform; envelope.SetParent(campus,false);
        var blue=new Color(.13f,.32f,.43f); var grey=FactoryRules.Grey; var yellow=FactoryRules.Amber;
        Shape("Expanded site apron",new Vector3(6,-.65f,0),new Vector3(100,.3f,54),new Color(.22f,.25f,.28f));
        Shape("Finishing hall floor",new Vector3(38,-.22f,0),new Vector3(32,.35f,34),new Color(.28f,.32f,.36f));
        Shape("Incoming yard floor",new Vector3(-32,-.22f,0),new Vector3(20,.35f,34),new Color(.28f,.32f,.36f));
        Shape("Annex roof",new Vector3(38,8.5f,0),new Vector3(32.4f,.2f,34.4f),blue,parent:envelope);
        foreach(float z in new[]{-17f,17f}) Shape("Annex wall",new Vector3(38,4,z),new Vector3(32,8,.25f),grey,parent:envelope);
        foreach(var segment in new[]{new Vector2(-12.25f,9.5f),new Vector2(7.25f,19.5f)})
            Shape("Annex end wall",new Vector3(54,4,segment.x),new Vector3(.25f,8,segment.y),grey,parent:envelope);
        Shape("Shipping door lintel",new Vector3(54,6,-5),new Vector3(.25f,4,5),grey,parent:envelope);
        foreach(float x in new[]{27f,33f,39f,45f,51f}) Shape("Annex window",new Vector3(x,5.5f,-17.16f),new Vector3(3,1.4f,.06f),new Color(.2f,.45f,.6f),parent:envelope);
        foreach(float x in new[]{25f,33f,41f,51f}) foreach(float z in new[]{-16f,16f}) {
            Shape("Annex column",new Vector3(x,4,z),new Vector3(.25f,8,.25f),blue);
            Shape("Annex LED housing",new Vector3(x,7,z*.55f),new Vector3(1.4f,.1f,.4f),Color.white);
            var light=new GameObject("Annex LED").AddComponent<Light>(); light.transform.SetParent(campus,false); light.transform.localPosition=new Vector3(x,6.9f,z*.55f);
            light.type=LightType.Spot; light.spotAngle=110; light.range=16; light.intensity=2; light.transform.localRotation=Quaternion.Euler(90,0,0);
        }
        Shape("Extended pedestrian aisle",new Vector3(35.25f,-.035f,-9.5f),new Vector3(34.5f,.012f,1.5f),new Color(.12f,.4f,.3f));
        Shape("Warehouse access aisle",new Vector3(38,-.035f,15),new Vector3(28,.012f,1.5f),new Color(.12f,.4f,.3f));
        // Side door joins the original hall to this line; all floor logistics stay above z=-8.
        for(float x=15.5f;x<50;x+=.4f) {
            var r=Shape("Finishing roller",new Vector3(x,1.1f,0),new Vector3(.24f,.85f,.24f),grey,PrimitiveType.Cylinder);
            r.transform.localRotation=Quaternion.Euler(90,0,0); rollers.Add(r.transform);
        }
        foreach(float z in new[]{-.95f,.95f}) {
            Shape("Finishing conveyor frame",new Vector3(32.65f,.75f,z),new Vector3(34.7f,.2f,.15f),blue);
            for(float x=18;x<50;x+=3) Shape("Finishing conveyor support",new Vector3(x,.35f,z),new Vector3(.16f,.7f,.16f),grey);
        }
        string[] stations={"Decoiler","Leveler","Slitter","Recoiler","Inspection","Packaging"};
        float[] xs={26,30,34,38,43,47};
        for(int i=0;i<stations.Length;i++) {
            var station=new GameObject(stations[i]).transform; station.SetParent(campus,false);
            foreach(float z in new[]{-1.5f,1.5f}) Shape("Machine pedestal",new Vector3(xs[i],1,z),new Vector3(1.7f,2,.4f),blue,parent:station);
            Shape("Machine crosshead",new Vector3(xs[i],2.6f,0),new Vector3(1.7f,.35f,3.4f),blue,parent:station);
            Shape("Safety enclosure",new Vector3(xs[i],1.8f,-1.8f),new Vector3(1.6f,.08f,.08f),yellow,parent:station);
            Shape("Control cabinet",new Vector3(xs[i]-.7f,.9f,-2.4f),new Vector3(.5f,1.8f,.6f),grey,parent:station);
            Shape("HMI screen",new Vector3(xs[i]-.7f,1.3f,-2.72f),new Vector3(.35f,.3f,.03f),new Color(.1f,.65f,.8f),parent:station);
            Label(stations[i]+" / VIRTUAL",new Vector3(xs[i],3.2f,0));
            if(i==0 || i==3) {
                var mandrel=Shape("Winding mandrel",new Vector3(xs[i],1.65f,0),new Vector3(.4f,1.4f,.4f),grey,PrimitiveType.Cylinder,station);
                mandrel.transform.localRotation=Quaternion.Euler(90,0,0); rollers.Add(mandrel.transform);
                var reel=FactoryRig.CreateLoad("Station reel",station,false); reel.position=new Vector3(xs[i],1.24f,0);
            }
            if(i==2) for(float z=-.65f;z<=.65f;z+=.26f) {
                var knife=Shape("Slitter knife",new Vector3(xs[i],1.6f,z),new Vector3(.7f,.025f,.7f),grey,PrimitiveType.Cylinder,station);
                knife.transform.localRotation=Quaternion.Euler(90,0,0); rollers.Add(knife.transform);
            }
            if(i==4) Shape("Inspection scanner",new Vector3(xs[i],2.25f,0),new Vector3(.5f,.2f,.5f),new Color(.2f,.65f,.7f),parent:station);
            if(i==5) Shape("Strapping arch",new Vector3(xs[i],2.15f,0),new Vector3(.2f,.15f,2.8f),yellow,parent:station);
        }
        Shape("Steel strip through leveler and slitter",new Vector3(32,1.245f,0),new Vector3(10,.015f,1.3f),new Color(.67f,.72f,.77f));
        Shape("Coil warehouse",new Vector3(36,.01f,10),new Vector3(26,.02f,8),blue);
        for(int i=0;i<24;i++) Saddle(Slot(false,i));
        Label("FINISHED COILS / 24 SADDLES",new Vector3(36,.06f,14));
        var warehouseCrane=new GameObject("Warehouse transfer crane").transform; warehouseCrane.SetParent(campus,false);
        foreach(float x in new[]{25f,51f}) foreach(float z in new[]{3f,14f}) Shape("Warehouse crane column",new Vector3(x,3.1f,z),new Vector3(.25f,6.2f,.25f),yellow,parent:warehouseCrane);
        foreach(float z in new[]{3f,14f}) Shape("Warehouse crane runway",new Vector3(38,6.2f,z),new Vector3(26,.25f,.25f),yellow,parent:warehouseCrane);
        Shape("Warehouse crane bridge",new Vector3(48,6.4f,8.5f),new Vector3(.7f,.3f,11.4f),yellow,parent:warehouseCrane);
        var shipping=new GameObject("Shipping truck").transform; shipping.SetParent(campus,false); shippingVehicle=shipping;
        Shape("Truck trailer",new Vector3(46,.9f,-5),new Vector3(10,.25f,3.6f),grey,parent:shipping);
        Shape("Truck cab",new Vector3(52,1.4f,-5),new Vector3(2.2f,2.5f,3),blue,parent:shipping);
        Shape("Truck windshield",new Vector3(53.12f,1.9f,-5),new Vector3(.02f,.7f,2.5f),new Color(.2f,.55f,.68f),parent:shipping);
        foreach(float x in new[]{42f,45f,49f,52f}) foreach(float z in new[]{-6.6f,-3.4f}) {
            var wheel=Shape("Truck wheel",new Vector3(x,.55f,z),new Vector3(.85f,.2f,.85f),Color.black,PrimitiveType.Cylinder,shipping); wheel.transform.localRotation=Quaternion.Euler(90,0,0);
        }
        for(int i=0;i<8;i++) Saddle(Slot(true,i));
        Label("SHIPPING / 8 COILS",new Vector3(46,.06f,-7.6f));
        var yard=new GameObject("Incoming coil yard").transform; yard.SetParent(campus,false);
        Shape("Incoming yard marking",new Vector3(-31,.01f,7),new Vector3(16,.02f,12),yellow,parent:yard);
        for(int i=0;i<12;i++) {
            var p=new Vector3(-37+(i%4)*4,.15f,3+(i/4)*4); Saddle(p);
            var coil=FactoryRig.CreateLoad("Incoming stock "+(i+1),yard,false); coil.position=p;
        }
        Label("INCOMING COIL YARD / VIRTUAL",new Vector3(-31,.06f,14));
        var crane=new GameObject("Overhead crane").transform; crane.SetParent(campus,false);
        foreach(float x in new[]{-39f,-24f}) foreach(float z in new[]{1f,13f}) Shape("Crane column",new Vector3(x,3.3f,z),new Vector3(.4f,6.6f,.4f),yellow,parent:crane);
        foreach(float z in new[]{1f,13f}) Shape("Crane runway",new Vector3(-31.5f,6.6f,z),new Vector3(16,.3f,.35f),yellow,parent:crane);
        Shape("Crane bridge",new Vector3(-30,6.8f,7),new Vector3(1,.4f,12.6f),yellow,parent:crane);
        Shape("Crane hoist",new Vector3(-30,6.2f,7),new Vector3(.8f,.8f,.8f),grey,parent:crane);
        Shape("Crane hook cable",new Vector3(-30,4.65f,7),new Vector3(.04f,2.3f,.04f),grey,parent:crane);
        // An overhead loader bridges the west pedestrian aisle through the open side door.
        Shape("Incoming loader beam",new Vector3(-20,4.6f,0),new Vector3(10,.2f,.4f),yellow);
        foreach(float x in new[]{-24.5f,-15.3f}) Shape("Incoming loader support",new Vector3(x,2.3f,2.6f),new Vector3(.25f,4.6f,.25f),yellow);
        incomingCarrier=FactoryRig.CreateLoad("Virtual incoming loader",campus,false); incomingCarrier.position=new Vector3(-24.5f,1.24f,0);
        Label("MES CORE  >  FINISHING  >  WAREHOUSE / SHIPPING",new Vector3(14,.06f,-13));
    }
    static Vector3 Slot(bool onTruck,int i) { return onTruck ? new Vector3(43+(i%4)*2,1.1f,-6+(i/4)*2) : new Vector3(26+(i%6)*4,.16f,7+(i/6)*2); }
    void Saddle(Vector3 p)
    {
        foreach(float x in new[]{-.4f,.4f}) { var support=Shape("Storage saddle",p+new Vector3(x,-.05f,0),new Vector3(.7f,.15f,1.2f),FactoryRules.Amber); support.transform.localRotation=Quaternion.Euler(0,0,x<0 ? -20 : 20); }
    }
    int FreeSlot(bool onTruck)
    {
        if(onTruck && departureTime>0) return -1;
        var occupied=onTruck ? truck : stored;
        for(int i=0;i<(onTruck ? 8 : 24);i++) if(!occupied.ContainsKey(i) && !journeys.Any(j=>j.slot==i && j.truck==onTruck)) return i;
        return -1;
    }
    public void Accept(Transform load)
    {
        load.SetParent(loads,true);
        journeys.Add(new Journey { load=load,truck=SendToTruck,path=new Queue<Vector3>(new[]{new Vector3(15.3f,1.24f,0),new Vector3(26,1.24f,0),new Vector3(38,1.24f,0),new Vector3(47,1.24f,0),new Vector3(50,1.24f,0)}) });
    }
    public void Advance(float dt,bool running)
    {
        if(!running || dt<=0 || float.IsNaN(dt) || float.IsInfinity(dt)) return;
        feedTime=Mathf.Repeat(feedTime+dt,24);
        Vector3[] feed={new Vector3(-24.5f,1.24f,0),new Vector3(-24.5f,3.1f,0),new Vector3(-15.3f,3.1f,0),new Vector3(-15.3f,1.24f,0),new Vector3(-24.5f,1.24f,0)};
        int leg=Mathf.Min(3,(int)(feedTime/6)); incomingCarrier.position=Vector3.Lerp(feed[leg],feed[leg+1],(feedTime%6)/6);
        foreach(var renderer in incomingCarrier.GetComponentsInChildren<Renderer>()) renderer.enabled=leg<3;
        if(departureTime>0) {
            float travel=Mathf.Min(dt,departureTime)*3; shippingVehicle.position+=Vector3.right*travel;
            foreach(var load in departing) load.position+=Vector3.right*travel;
            departureTime=Mathf.Max(0,departureTime-dt);
            if(departureTime==0) { foreach(var load in departing) Remove(load.gameObject); departing.Clear(); shippingVehicle.localPosition=Vector3.zero; }
        }
        foreach(var r in rollers) r.Rotate(Vector3.up,dt*180,Space.Self);
        foreach(var j in journeys.ToArray()) {
            if(j.path.Count==0 && j.slot<0) {
                j.slot=FreeSlot(j.truck);
                if(j.slot<0 && j.truck) { j.truck=false; j.slot=FreeSlot(false); }
                if(j.slot<0) continue; // Full warehouse holds material; nothing is discarded.
                j.path.Enqueue(new Vector3(52,4,0));
                j.path.Enqueue(new Vector3(52,4,j.truck ? -3 : 4));
                var end=Slot(j.truck,j.slot);
                j.path.Enqueue(new Vector3(end.x,4,j.truck ? -3 : 4));
                j.path.Enqueue(new Vector3(end.x,4,end.z)); j.path.Enqueue(end);
            }
            if(j.path.Count==0) continue;
            // A carrier waits behind the preceding coil on the shared finishing roller bed.
            int index=journeys.IndexOf(j);
            if(index>0 && j.load.position.z==0 && journeys[index-1].load.position.z==0 && journeys[index-1].load.position.x-j.load.position.x<2.4f) continue;
            j.load.position=Vector3.MoveTowards(j.load.position,j.path.Peek(),2*dt);
            bool stripZone=j.load.position.z==0 && j.load.position.x>26 && j.load.position.x<38;
            foreach(var renderer in j.load.GetComponentsInChildren<Renderer>()) renderer.enabled=!stripZone;
            if(Vector3.Distance(j.load.position,j.path.Peek())<.001f) j.path.Dequeue();
            if(j.path.Count==0 && j.slot>=0) { (j.truck ? truck : stored)[j.slot]=j.load; journeys.Remove(j); }
        }
        var camera=Camera.main; if(camera!=null) foreach(var text in campus.GetComponentsInChildren<TextMesh>()) text.transform.rotation=camera.transform.rotation;
    }
    public void DispatchStored()
    {
        foreach(var pair in stored.ToArray()) {
            int slot=FreeSlot(true); if(slot<0) break;
            var end=Slot(true,slot);
            journeys.Add(new Journey {load=pair.Value,truck=true,slot=slot,path=new Queue<Vector3>(new[]{pair.Value.position+Vector3.up*(4-pair.Value.position.y),new Vector3(pair.Value.position.x,4,4),new Vector3(52,4,4),new Vector3(52,4,-3),new Vector3(end.x,4,-3),new Vector3(end.x,4,end.z),end})});
            stored.Remove(pair.Key);
        }
    }
    public void DepartTruck() { if(departureTime>0 || truck.Count==0) return; departing.AddRange(truck.Values); truck.Clear(); departureTime=6; }
    public void ResetLoads() { journeys.Clear(); stored.Clear(); truck.Clear(); departing.Clear(); departureTime=0; feedTime=0; if(shippingVehicle!=null) shippingVehicle.localPosition=Vector3.zero; if(loads!=null) foreach(Transform child in loads.Cast<Transform>().ToArray()) { child.SetParent(null); Remove(child.gameObject); } }
    public void SetExterior(bool exterior) { if(envelope!=null) envelope.gameObject.SetActive(exterior); if(campus!=null) foreach(var label in campus.GetComponentsInChildren<TextMesh>(true)) label.gameObject.SetActive(!exterior); }
    static void Remove(Object obj) { if(Application.isPlaying) Destroy(obj); else DestroyImmediate(obj); }
    void OnDestroy() { foreach(var mat in materials.Values) Remove(mat); }
}
