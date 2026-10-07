using System.Linq;
using System.Text;
using UnityEngine;

// The display reuses the accepted MES snapshot; it never polls a second data source.
public class FactoryMonitor : MonoBehaviour
{
    TextMesh text;
    Transform screen;
    Material frameMaterial, screenMaterial;
    Font font;
    bool expanded;
    Vector2 scroll;
    public string Content { get; private set; }

    public static void RefreshFor(FactoryDemo factory,FactoryConfig config,MesSnapshot state,bool online)
    {
        var monitor=factory.GetComponent<FactoryMonitor>();
        if(monitor==null) monitor=factory.gameObject.AddComponent<FactoryMonitor>();
        monitor.Refresh(config,state,online);
    }
    public void Refresh(FactoryConfig config,MesSnapshot state,bool online)
    {
        EnsureDisplay();
        bool live=online && FactoryRules.Matches(config,state);
        var result=new StringBuilder("SHIFTLINK / 코일 이송 현황\n");
        result.AppendLine(live ? "MES 연결됨 | "+Label(state.line_mode)+" | 갱신 "+state.sequence : "MES 연결 끊김 | 실시간 값 확인 불가");
        result.AppendLine("가상 공정 시연");
        if(config!=null) {
            System.Func<string,string> code=id=>config.equipment.FirstOrDefault(e=>e.equipment_id==id)?.code??id;
            result.AppendLine("주경로: "+string.Join(" → ",config.route.Select(code)));
            if(config.branches!=null) foreach(var branch in config.branches)
                result.AppendLine("분기: "+code(branch.from_id)+" → "+code(branch.to_id));
        }
        if(live) {
            result.AppendLine("코일 "+state.coils.Length+" | 경고 "+state.equipment.Count(e=>e.fault_level=="warning")+
                " | 심각 "+state.equipment.Count(e=>e.fault_level=="critical"));
        } else result.AppendLine("코일 -- | 경고 -- | 심각 --");
        result.AppendLine("────────────────────────");
        if(config!=null) foreach(var e in config.equipment.Where(e=>e.active)) {
            var reading=live ? state.equipment.FirstOrDefault(r=>r.equipment_id==e.equipment_id) : null;
            string status=reading==null ? "확인 불가" : Label(reading.operating_state)+" / "+Label(reading.fault_level);
            var color=reading==null ? FactoryRules.Grey : FactoryRules.StateColor(reading.operating_state,reading.fault_level);
            result.AppendLine("<color=#"+ColorUtility.ToHtmlStringRGB(color)+">"+e.code+"   "+status+"</color>");
        }
        Content=result.ToString().TrimEnd();
        text.text=Content;
        FaceCamera();
    }
    static string Label(string value)
    {
        switch(value) {
            case "running": return "가동";
            case "paused": return "일시정지";
            case "waiting": return "대기";
            case "stopped": return "정지";
            case "idle": return "대기";
            case "normal": return "정상";
            case "warning": return "경고";
            case "critical": return "심각";
            default: return value??"--";
        }
    }
    void EnsureDisplay()
    {
        if(text!=null) return;
        if(font==null) font=Font.CreateDynamicFontFromOSFont(new[]{"Malgun Gothic","Arial"},32);
        screen=new GameObject("Factory status display").transform;
        screen.SetParent(transform,false); screen.localPosition=new Vector3(-19,5.5f,2);
        if(frameMaterial==null) { frameMaterial=new Material(Shader.Find("Unlit/Color")); frameMaterial.color=new Color(.18f,.25f,.32f); }
        if(screenMaterial==null) { screenMaterial=new Material(Shader.Find("Unlit/Color")); screenMaterial.color=new Color(.025f,.04f,.065f); }
        Panel("Monitor frame",new Vector3(0,0,.12f),new Vector3(13.2f,10.7f,.25f),frameMaterial);
        Panel("Monitor screen",Vector3.zero,new Vector3(13,10.5f,.08f),screenMaterial);
        text=new GameObject("Live status text").AddComponent<TextMesh>();
        text.transform.SetParent(screen,false); text.transform.localPosition=new Vector3(-6.1f,4.1f,-.08f);
        text.font=font; text.GetComponent<Renderer>().sharedMaterial=font.material;
        text.fontSize=32; text.characterSize=.11f; text.lineSpacing=1.15f;
        text.anchor=TextAnchor.UpperLeft; text.richText=true; text.color=Color.white;
    }
    void Panel(string name,Vector3 position,Vector3 size,Material material)
    {
        var panel=GameObject.CreatePrimitive(PrimitiveType.Cube); panel.name=name;
        panel.transform.SetParent(screen,false); panel.transform.localPosition=position; panel.transform.localScale=size;
        panel.GetComponent<Renderer>().sharedMaterial=material;
    }
    void FaceCamera() { if(screen!=null && Camera.main!=null) screen.rotation=Camera.main.transform.rotation; }
    void LateUpdate() { FaceCamera(); }
    Rect ButtonRect { get { return new Rect(Mathf.Max(18,Screen.width-200),18,182,34); } }
    Rect ExpandedRect { get { return new Rect(Mathf.Max(18,Screen.width-420),62,Mathf.Min(402,Screen.width-36),Mathf.Min(540,Screen.height-80)); } }
    public bool ContainsPointer(Vector2 pointer) { return ButtonRect.Contains(pointer) || (expanded && ExpandedRect.Contains(pointer)); }
    void OnGUI()
    {
        if(GetComponent<FactoryWorker>()?.IsWorkerMode==true) return;
        var button=new GUIStyle(GUI.skin.button) {font=font,fontSize=17};
        if(GUI.Button(ButtonRect,expanded ? "현황 디스플레이 닫기" : "현황 디스플레이 확대",button)) expanded=!expanded;
        if(!expanded) return;
        GUILayout.BeginArea(ExpandedRect,GUI.skin.box);
        scroll=GUILayout.BeginScrollView(scroll);
        GUILayout.Label(Content,new GUIStyle(GUI.skin.label) {font=font,fontSize=18,richText=true,wordWrap=true});
        GUILayout.EndScrollView(); GUILayout.EndArea();
    }
    void OnDestroy()
    {
        foreach(var asset in new UnityEngine.Object[]{frameMaterial,screenMaterial,font})
            if(asset!=null) { if(Application.isPlaying) Destroy(asset); else DestroyImmediate(asset); }
    }
}
