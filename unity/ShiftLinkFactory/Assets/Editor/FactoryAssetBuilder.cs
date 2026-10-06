using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class FactoryAssetBuilder
{
    static FactoryAssetBuilder() { EditorApplication.delayCall += AutoPrepare; }
    static void AutoPrepare()
    {
        if(EditorApplication.isCompiling || EditorApplication.isUpdating) { EditorApplication.delayCall+=AutoPrepare; return; }
        Prepare();
    }
    public static void Prepare()
    {
        Directory.CreateDirectory("Assets/Resources/Factory");
        AssetDatabase.Refresh();
        foreach(var path in AssetDatabase.FindAssets("t:Model",new[]{"Assets/Models"}).Select(AssetDatabase.GUIDToAssetPath)) {
            string name=Path.GetFileNameWithoutExtension(path);
            if(!(name.StartsWith("Equipment_") || name.StartsWith("Connection_") || name=="Material_Coil")) continue;
            if(!path.Contains("EquipmentTypes/") && !path.Contains("Connections/")) continue;
            string destination="Assets/Resources/Factory/"+name+".prefab";
            if(File.Exists(destination) && name!="Equipment_RT") continue;
            var source=AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if(source==null) throw new Exception("FBX not imported: "+path);
            var wrapper=new GameObject(name);
            var model=UnityEngine.Object.Instantiate(source,wrapper.transform);
            model.name="Model";
            // Normalize transport direction without changing moving-part origins.
            var anchors=model.GetComponentsInChildren<Transform>();
            var input=anchors.FirstOrDefault(t=>t.name.StartsWith("InputAnchor_"));
            var output=anchors.FirstOrDefault(t=>t.name.StartsWith("OutputAnchor_"));
            if(input!=null && output!=null) {
                float span=Mathf.Abs(output.position.x-input.position.x);
                if(span<.001f) throw new Exception("Unexpected FBX transport axes: "+path);
                model.transform.localScale*=4.8f/span;
                if(output.position.x<input.position.x) model.transform.localRotation=Quaternion.Euler(0,180,0)*model.transform.localRotation;
            }
            PrefabUtility.SaveAsPrefabAsset(wrapper,destination);
            if(name=="Equipment_RT") {
                var moving=wrapper.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("MovingParts_RT"));
                var platform=wrapper.GetComponentsInChildren<Transform>().First(t=>t.name.StartsWith("RollerAssembly"));
                platform.name="LiftPlatform";
                var rollers=platform.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("Roller_") && t.childCount>0).ToArray();
                var prototype=UnityEngine.Object.Instantiate(rollers[0].gameObject); prototype.SetActive(false);
                var bearings=platform.GetComponentsInChildren<Transform>().Where(t=>t.name.StartsWith("BearingBlock")).ToArray();
                var bearingTemplates=bearings.GroupBy(t=>Mathf.Sign(t.localPosition.z)).Select(g=>UnityEngine.Object.Instantiate(g.First().gameObject)).ToArray();
                foreach(var template in bearingTemplates) template.SetActive(false);
                foreach(var bearing in bearings) UnityEngine.Object.DestroyImmediate(bearing.gameObject);
                foreach(var roller in rollers) UnityEngine.Object.DestroyImmediate(roller.gameObject);
                for(int i=0;i<16;i++) {
                    var roller=UnityEngine.Object.Instantiate(prototype,platform); roller.name="Roller_"+(i+1).ToString("00"); roller.SetActive(true);
                    var pos=roller.transform.localPosition; pos.x=-2.18f+i*4.36f/15; roller.transform.localPosition=pos;
                    foreach(var template in bearingTemplates) {
                        var bearing=UnityEngine.Object.Instantiate(template,platform); bearing.SetActive(true); var bearingPosition=bearing.transform.localPosition; bearingPosition.x=pos.x; bearing.transform.localPosition=bearingPosition;
                    }
                }
                foreach(var template in bearingTemplates) UnityEngine.Object.DestroyImmediate(template);
                UnityEngine.Object.DestroyImmediate(prototype);
                PrefabUtility.SaveAsPrefabAsset(wrapper,"Assets/Resources/Factory/Equipment_RT02.prefab");
            }
            UnityEngine.Object.DestroyImmediate(wrapper);
        }
        AssetDatabase.SaveAssets();
    }
}
