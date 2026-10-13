using System;
using System.Collections.Generic;
using UnityEngine;

// One layout and skin for the factory overlays; world simulation remains independent.
public sealed class FactoryUi : MonoBehaviour
{
    public static readonly Color Surface = new Color32(27, 35, 54, 255);
    public static readonly Color Text = new Color32(248, 250, 252, 255);
    public static readonly Color Muted = new Color32(180, 193, 210, 255);
    public static readonly Color Accent = new Color32(125, 211, 252, 255);
    GUISkin skin;
    Font font;
    readonly List<Texture2D> textures = new List<Texture2D>();
    public GUIStyle Heading { get; private set; }
    public GUIStyle Caption { get; private set; }
    public GUIStyle Primary { get; private set; }

    public struct Layout
    {
        public Rect Controls, Alert, Switcher, Details, Selection, Pda;
        public Layout(float width, float height)
        {
            float left = Mathf.Min(320, (width - 48) * .44f);
            float right = Mathf.Min(380, (width - 48) * .48f);
            Controls = new Rect(16, 16, left, Mathf.Min(374, height * .57f));
            Alert = new Rect(16, Controls.yMax + 12, left, Mathf.Max(40, Mathf.Min(176, height - Controls.yMax - 28)));
            Switcher = new Rect(width - right - 16, 16, right, 40);
            Selection = new Rect(width - right - 16, height - 174, right, 158);
            Details = new Rect(width - right - 16, 68, right, Mathf.Max(60, Selection.y - 80));
            Pda = new Rect(Mathf.Max(16, (width - 640) / 2), 16, Mathf.Min(640, width - 32), height - 32);
        }
    }
    public static Layout ScreenLayout { get { return new Layout(Screen.width, Screen.height); } }
    public static FactoryUi For(Component owner)
    {
        var demo = owner.GetComponentInParent<FactoryDemo>();
        var host = demo != null ? demo.gameObject : owner.gameObject;
        return host.GetComponent<FactoryUi>() ?? host.AddComponent<FactoryUi>();
    }
    Texture2D Fill(Color color)
    {
        var texture = new Texture2D(1, 1) {hideFlags=HideFlags.HideAndDontSave};
        texture.SetPixel(0, 0, color); texture.Apply(); textures.Add(texture); return texture;
    }
    void Ensure()
    {
        if(skin != null) return;
        skin = Instantiate(GUI.skin); skin.hideFlags = HideFlags.HideAndDontSave;
        font = Font.CreateDynamicFontFromOSFont(new[]{"Malgun Gothic", "Arial"}, 16);
        skin.font = font;
        skin.label.fontSize=15; skin.label.wordWrap=true;
        skin.label.normal.textColor=Text; skin.label.padding=new RectOffset(0,0,3,3);
        skin.box.normal.background=Fill(Surface); skin.box.normal.textColor=Text;
        skin.box.border=new RectOffset(); skin.box.padding=new RectOffset(16,16,14,14);
        skin.button.fontSize=14; skin.button.wordWrap=true; skin.button.fixedHeight=40;
        skin.button.margin=new RectOffset(0,0,4,4); skin.button.padding=new RectOffset(10,10,6,6);
        skin.button.border=new RectOffset();
        skin.button.normal.background=Fill(new Color32(51,65,85,255)); skin.button.normal.textColor=Text;
        skin.button.hover.background=Fill(new Color32(71,85,105,255)); skin.button.hover.textColor=Text;
        skin.button.active.background=Fill(new Color32(14,116,144,255)); skin.button.active.textColor=Text;
        skin.button.focused.background=Fill(new Color32(3,105,161,255)); skin.button.focused.textColor=Text;
        skin.toggle.fontSize=14; skin.toggle.wordWrap=true; skin.toggle.normal.textColor=Text;
        skin.toggle.onNormal.textColor=Text; skin.toggle.hover.textColor=Text; skin.toggle.onHover.textColor=Text;
        skin.toggle.margin=new RectOffset(0,0,8,8);
        Heading=new GUIStyle(skin.label) {fontSize=20,fontStyle=FontStyle.Bold};
        Caption=new GUIStyle(skin.label) {fontSize=13}; Caption.normal.textColor=Muted;
        Primary=new GUIStyle(skin.button);
        Primary.normal.background=Fill(new Color32(14,116,144,255));
    }
    public Scope Use() { Ensure(); return new Scope(skin); }
    public struct Scope : IDisposable
    {
        readonly GUISkin previous;
        readonly Color color, background, content;
        readonly bool enabled;
        public Scope(GUISkin next)
        {
            previous=GUI.skin; color=GUI.color; background=GUI.backgroundColor; content=GUI.contentColor; enabled=GUI.enabled;
            GUI.skin=next; GUI.color=GUI.backgroundColor=GUI.contentColor=Color.white;
        }
        public void Dispose() { GUI.skin=previous; GUI.color=color; GUI.backgroundColor=background; GUI.contentColor=content; GUI.enabled=enabled; }
    }
    public static string StateLabel(string state)
    {
        switch(state) {
            case "running": return "운전 중";
            case "paused": return "일시정지";
            case "stopped": return "정지";
            case "idle": return "대기";
            case "normal": return "정상";
            case "warning": return "경고";
            case "critical": return "비상";
            default: return state ?? "미확인";
        }
    }
    void OnDestroy()
    {
        foreach(var texture in textures) Release(texture);
        Release(skin); Release(font);
    }
    static void Release(UnityEngine.Object value) { if(value==null) return; if(Application.isPlaying) Destroy(value); else DestroyImmediate(value); }
}
