using UnityEngine;

// Physical building envelopes stay active when the observation view hides their meshes.
public static class FactoryWalkGeometry
{
    public static void Prepare(Transform factory)
    {
        var physicsRoot = new GameObject("Employee building collisions").transform;
        physicsRoot.SetParent(factory, false);
        foreach (var box in factory.GetComponentsInChildren<BoxCollider>(true)) {
            if (!HasEnvelopeAncestor(box.transform)) continue;
            var proxy = new GameObject("Collision / " + box.name).transform;
            proxy.SetParent(physicsRoot, false);
            proxy.SetPositionAndRotation(box.transform.position, box.transform.rotation);
            proxy.localScale = box.transform.lossyScale;
            var collider = proxy.gameObject.AddComponent<BoxCollider>();
            collider.center = box.center; collider.size = box.size;
        }
        var campus = factory.Find("Virtual process campus");
        if (campus == null) return;
        foreach (var renderer in campus.GetComponentsInChildren<MeshRenderer>(true)) {
            if (renderer.GetComponent<TextMesh>() != null || renderer.GetComponent<Collider>() != null) continue;
            // Floor paint, screens and light fittings are visual details, not walking obstacles.
            if (renderer.bounds.size.y < .1f && !renderer.name.Contains("floor") && !renderer.name.Contains("apron")) continue;
            if (HasEnvelopeAncestor(renderer.transform)) {
                var proxy = new GameObject("Collision / " + renderer.name).transform;
                proxy.SetParent(physicsRoot, false);
                proxy.position = renderer.bounds.center;
                proxy.gameObject.AddComponent<BoxCollider>().size = renderer.bounds.size;
            } else {
                // Local mesh bounds keep moving truck geometry and its collider together.
                var mesh = renderer.GetComponent<MeshFilter>();
                if (mesh == null || mesh.sharedMesh == null) continue;
                var collider = renderer.gameObject.AddComponent<BoxCollider>();
                collider.center = mesh.sharedMesh.bounds.center; collider.size = mesh.sharedMesh.bounds.size;
            }
        }
    }
    static bool HasEnvelopeAncestor(Transform node)
    {
        for (var current = node; current != null; current = current.parent)
            if (current.name == "Exterior envelope" || current.name == "Finishing hall envelope") return true;
        return false;
    }
}
