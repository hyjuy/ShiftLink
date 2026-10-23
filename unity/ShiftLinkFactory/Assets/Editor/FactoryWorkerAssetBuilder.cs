using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Builds only the approved male worker/PDA prefab; FBX sources remain editable.
[InitializeOnLoad]
public static class FactoryWorkerAssetBuilder
{
    const string Source = "Assets/Models/Characters/ChibiWorkers_v2/";
    const string Destination = "Assets/Resources/Factory/WorkerMale.prefab";
    static FactoryWorkerAssetBuilder() { EditorApplication.delayCall += AutoPrepare; }
    static void AutoPrepare()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating) { EditorApplication.delayCall += AutoPrepare; return; }
        Prepare();
    }
    public static void Prepare()
    {
        string signature = string.Join(":", new[] { Source+"ChibiWorker_Male.fbx", Source+"ChibiWorker_PDA.fbx",
            Source+"WorkerToon.shader", "Assets/Scripts/FactoryWorkerVisual.cs", "Assets/Editor/FactoryWorkerAssetBuilder.cs" }
            .Select(p => AssetDatabase.GetAssetDependencyHash(p).ToString()));
        var previous = AssetImporter.GetAtPath(Destination);
        if (previous != null && previous.userData == signature && AssetDatabase.LoadAssetAtPath<GameObject>(Destination) != null) return;
        PrepareImport(Source+"ChibiWorker_Male.fbx"); PrepareImport(Source+"ChibiWorker_PDA.fbx");
        Directory.CreateDirectory(Source+"Materials"); Directory.CreateDirectory("Assets/Resources/Factory"); AssetDatabase.Refresh();
        var wrapper = new GameObject("WorkerMale");
        try {
            var source = AssetDatabase.LoadAssetAtPath<GameObject>(Source+"ChibiWorker_Male.fbx");
            var accessory = AssetDatabase.LoadAssetAtPath<GameObject>(Source+"ChibiWorker_PDA.fbx");
            if (source == null || accessory == null) throw new InvalidOperationException("Worker FBX sources not imported");
            var model = UnityEngine.Object.Instantiate(source,wrapper.transform); model.name="Male model";
            foreach (var animator in model.GetComponentsInChildren<Animator>()) UnityEngine.Object.DestroyImmediate(animator);
            var nodes = model.GetComponentsInChildren<Transform>();
            var toes = nodes.Single(t=>t.name=="LeftToes"); var foot = nodes.Single(t=>t.name=="LeftFoot");
            var forward = toes.position-foot.position; forward.y=0;
            model.transform.rotation = Quaternion.FromToRotation(forward.normalized, Vector3.forward)*model.transform.rotation;
            var skin = model.GetComponentInChildren<SkinnedMeshRenderer>();
            model.transform.localScale *= 1.72f/skin.bounds.size.y;
            model.transform.position -= new Vector3(skin.bounds.center.x,skin.bounds.min.y,skin.bounds.center.z);
            skin.updateWhenOffscreen=true;
            var pda = new GameObject("PDA").transform; pda.SetParent(wrapper.transform,false); pda.localPosition=new Vector3(.075f,.84f,.22f);
            var tablet = UnityEngine.Object.Instantiate(accessory,pda); tablet.name="PDA model";
            tablet.transform.localRotation = Quaternion.Euler(0,180,0)*tablet.transform.localRotation;
            var tabletRenderer=tablet.GetComponentInChildren<Renderer>();
            tablet.transform.localScale *= .238f/tabletRenderer.bounds.size.y;
            // Centre using world bounds, preserving the imported axis conversion.
            tablet.transform.position += pda.position-tabletRenderer.bounds.center;
            var lens = new GameObject("PhotoLens").transform; lens.SetParent(pda,false); lens.localPosition=new Vector3(0,.035f,.028f);
            var shader=Shader.Find("ShiftLink/WorkerToon");
            if(shader==null)throw new InvalidOperationException("Worker palette shader missing");
            foreach(var renderer in wrapper.GetComponentsInChildren<Renderer>())
                renderer.sharedMaterials=renderer.sharedMaterials.Select(m=>Palette(m,shader)).ToArray();
            wrapper.AddComponent<FactoryWorkerVisual>();
            PrefabUtility.SaveAsPrefabAsset(wrapper,Destination);
            AssetDatabase.SaveAssets();
            previous=AssetImporter.GetAtPath(Destination);
            previous.userData=string.Join(":",new[]{Source+"ChibiWorker_Male.fbx",Source+"ChibiWorker_PDA.fbx",Source+"WorkerToon.shader","Assets/Scripts/FactoryWorkerVisual.cs","Assets/Editor/FactoryWorkerAssetBuilder.cs"}.Select(p=>AssetDatabase.GetAssetDependencyHash(p).ToString()));
            previous.SaveAndReimport();
        } finally { UnityEngine.Object.DestroyImmediate(wrapper); }
    }
    static void PrepareImport(string path)
    {
        var importer=AssetImporter.GetAtPath(path) as ModelImporter;
        if(importer==null)throw new InvalidOperationException("Worker FBX missing: "+path);
        if(importer.animationType==ModelImporterAnimationType.Generic&&!importer.importAnimation&&!importer.optimizeGameObjects&&importer.isReadable)return;
        importer.animationType=ModelImporterAnimationType.Generic; importer.importAnimation=false;
        importer.optimizeGameObjects=false; importer.isReadable=true; importer.SaveAndReimport();
    }
    static Material Palette(Material source,Shader shader)
    {
        string name=source.name; string path=Source+"Materials/"+name.Replace('/','_')+".mat";
        var material=AssetDatabase.LoadAssetAtPath<Material>(path);
        if(material==null){material=new Material(shader);AssetDatabase.CreateAsset(material,path);}
        material.shader=shader;
        Color color=source.color;
        if(name.StartsWith("Workwear - deep"))color=new Color(.10f,.24f,.49f);
        else if(name.StartsWith("Workwear - turquoise"))color=new Color(.10f,.60f,.63f);
        else if(name.StartsWith("Safety"))color=new Color(1,.80f,.08f);
        else if(name.StartsWith("Face - warm peach"))color=new Color(1,.70f,.43f);
        else if(name.StartsWith("Face - warm ear"))color=new Color(.68f,.31f,.17f);
        else if(name.StartsWith("Details"))color=new Color(.02f,.04f,.09f);
        else if(name.StartsWith("Hair"))color=new Color(.07f,.09f,.14f);
        else if(name.StartsWith("Gloves")||name.StartsWith("Boots"))color=new Color(.12f,.14f,.18f);
        material.color=color; material.SetFloat("_OutlineWidth",.0025f); EditorUtility.SetDirty(material);
        return material;
    }
}
