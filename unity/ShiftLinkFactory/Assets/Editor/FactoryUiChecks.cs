using System;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class FactoryUiChecks
{
    static int checks;
    static void Check(bool value, string message) { checks++; if(!value) throw new Exception(message); }
    [MenuItem("ShiftLink/Checks/UI layout")]
    public static void Run()
    {
        checks=0;
        foreach(var size in new[]{new Vector2(640,480),new Vector2(800,600),new Vector2(1024,768),new Vector2(1280,720),new Vector2(1920,1080),new Vector2(2560,1440)}) {
            var layout=new FactoryUi.Layout(size.x,size.y);
            var panels=new[]{layout.Controls,layout.Alert,layout.Switcher,layout.Details,layout.Selection};
            foreach(var panel in panels)
                Check(panel.width>0 && panel.height>0 && panel.xMin>=16 && panel.yMin>=16 &&
                    panel.xMax<=size.x-16 && panel.yMax<=size.y-16,"Panel outside viewport "+size+" / "+panel);
            for(int i=0;i<panels.Length;i++)
                for(int j=i+1;j<panels.Length;j++)
                    Check(!panels[i].Overlaps(panels[j]),"Panels overlap at "+size+" / "+i+" and "+j);
            Check(layout.Pda.xMin>=16 && layout.Pda.yMin>=16 && layout.Pda.xMax<=size.x-16 &&
                layout.Pda.yMax<=size.y-16,"PDA outside viewport "+size);
            Check(layout.Controls.Contains(layout.Controls.center) && !layout.Controls.Contains(layout.Details.center),
                "Pointer regions must separate controls and details");
        }
        Check(Contrast(FactoryUi.Text,FactoryUi.Surface)>=4.5f,"Body text contrast");
        Check(Contrast(FactoryUi.Muted,FactoryUi.Surface)>=4.5f,"Secondary text contrast");
        Check(Contrast(FactoryUi.Text,new Color32(14,116,144,255))>=4.5f,"Primary button contrast");
        Check(FactoryUi.StateLabel("critical")=="비상","Critical status includes a text label");
        Check(FactoryUi.StateLabel("unknown-state")=="unknown-state","Unknown states must not be fabricated");
        var dir=Path.GetFullPath(Path.Combine(Application.dataPath,"../Checks"));
        Directory.CreateDirectory(dir);
        var result="PASS: "+checks+" UI layout, pointer-region, contrast and state-label assertions; 640x480 through 2560x1440.";
        File.WriteAllText(Path.Combine(dir,"ui-layout-result.txt"),result);
        Debug.Log(result);
    }
    static float Luminance(Color c)
    {
        return .2126f*Linear(c.r)+.7152f*Linear(c.g)+.0722f*Linear(c.b);
    }
    static float Linear(float value) { return value<=.04045f ? value/12.92f : Mathf.Pow((value+.055f)/1.055f,2.4f); }
    static float Contrast(Color a,Color b) { var x=Luminance(a); var y=Luminance(b); return (Mathf.Max(x,y)+.05f)/(Mathf.Min(x,y)+.05f); }
}
