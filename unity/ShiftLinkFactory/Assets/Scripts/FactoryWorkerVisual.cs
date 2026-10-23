using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Drives the imported Generic skeleton directly; no downloaded clips or Animator controller.
public sealed class FactoryWorkerVisual : MonoBehaviour
{
    public enum MotionState { Idle, Walking, Running, Jumping, Photographing }
    public MotionState CurrentState { get; private set; }
    public Transform Pda { get; private set; }
    public Transform PhotoLens { get; private set; }
    public bool IsShutterActive { get { return shutterTime > 0; } }
    public float RunSpeedThreshold = 3.3f;
    sealed class Bone
    {
        public Transform transform;
        public Quaternion rotation;
        public Vector3 direction, position;
    }
    readonly Dictionary<string, Bone> bones = new Dictionary<string, Bone>();
    bool initialized;
    float phase, idleTime, shutterTime;
    float blend;
    Vector3 pdaScale;

    public void Initialize()
    {
        if (initialized) return;
        var nodes = GetComponentsInChildren<Transform>(true);
        foreach (string name in new[] { "Hips", "Spine", "Chest", "Head" }) Add(nodes, name, null);
        foreach (string side in new[] { "Left", "Right" }) {
            Add(nodes, side+"UpperLeg", side+"LowerLeg"); Add(nodes, side+"LowerLeg", side+"Foot");
            Add(nodes, side+"Foot", side+"Toes"); Add(nodes, side+"UpperArm", side+"LowerArm");
            Add(nodes, side+"LowerArm", side+"Hand"); Add(nodes, side+"Hand", null);
            bones[side+"Hand"].direction = bones[side+"UpperArm"].direction;
        }
        Pda = nodes.Single(t => t.name == "PDA");
        PhotoLens = nodes.Single(t => t.name == "PhotoLens");
        pdaScale = Pda.localScale;
        initialized = true;
        Advance(0, 0, true, 0, false);
    }
    void Add(Transform[] nodes, string name, string next)
    {
        var t = nodes.Single(n => n.name == name);
        var dir = next == null ? transform.InverseTransformDirection(t.up) :
            transform.InverseTransformDirection(nodes.Single(n=>n.name==next).position-t.position).normalized;
        bones.Add(name, new Bone { transform=t, rotation=Quaternion.Inverse(transform.rotation)*t.rotation,
            direction=dir, position=t.localPosition });
    }
    static bool Finite(float n) { return !float.IsNaN(n) && !float.IsInfinity(n); }
    public void Shutter() { shutterTime = .18f; }
    public void Advance(float seconds, float speed, bool grounded, float verticalSpeed, bool photographing)
    {
        if (!Finite(seconds) || seconds < 0 || !Finite(speed) || speed < 0 || !Finite(verticalSpeed)) return;
        if (!initialized) Initialize();
        blend = seconds == 0 ? 1 : 1-Mathf.Exp(-18*seconds);
        idleTime += seconds;
        shutterTime = Mathf.Max(0, shutterTime-seconds);
        CurrentState = photographing ? MotionState.Photographing : !grounded ? MotionState.Jumping :
            speed < .05f ? MotionState.Idle : speed > RunSpeedThreshold ? MotionState.Running : MotionState.Walking;
        bool moving = CurrentState == MotionState.Walking || CurrentState == MotionState.Running;
        bool running = CurrentState == MotionState.Running;
        if (moving) phase += seconds*(running ? 12 : 8);
        float swing = moving ? Mathf.Sin(phase)*(running ? 32 : 20) : 0;
        float bob = moving ? Mathf.Abs(Mathf.Sin(phase))*(running ? .018f : .01f) : Mathf.Sin(idleTime*2)*.003f;
        if (CurrentState == MotionState.Jumping) bob = 0;
        var hips = bones["Hips"];
        var up = hips.transform.parent.InverseTransformDirection(transform.up);
        hips.transform.localPosition = Vector3.Lerp(hips.transform.localPosition, hips.position+up*bob, blend);
        float recoil = shutterTime/.18f;
        Rotate("Spine", Quaternion.AngleAxis(running ? 6 : recoil*2, Vector3.right));
        Rotate("Chest", Quaternion.AngleAxis(running ? 6 : Mathf.Sin(idleTime*2)*.7f+recoil*2, Vector3.right));
        Rotate("Head", Quaternion.AngleAxis(photographing ? 3 : Mathf.Sin(idleTime*1.5f)*.7f, Vector3.right));
        foreach (string side in new[] { "Left", "Right" }) {
            float leg = side == "Left" ? swing : -swing;
            float bend = moving ? Mathf.Max(0,-leg)*.8f : 0;
            if (CurrentState == MotionState.Jumping) { leg = verticalSpeed > 0 ? 16 : 5; bend = verticalSpeed > 0 ? 40 : 15; }
            Rotate(side+"UpperLeg", Quaternion.AngleAxis(-leg, Vector3.right));
            Rotate(side+"LowerLeg", Quaternion.AngleAxis(-leg+bend, Vector3.right));
            Rotate(side+"Foot", Quaternion.AngleAxis(-leg*.15f, Vector3.right));
        }
        float rightSign = Mathf.Sign(bones["RightUpperArm"].direction.x);
        var tablet = new Vector3(rightSign*.075f, photographing ? 1.11f : .84f, photographing ? .335f : .22f);
        tablet.z -= recoil*.006f;
        Pda.localPosition = Vector3.Lerp(Pda.localPosition, tablet, blend);
        Pda.localRotation = Quaternion.Slerp(Pda.localRotation, Quaternion.Euler(photographing ? -5 : -10,0,0), blend);
        Pda.localScale = pdaScale;
        foreach (string side in new[] { "Left", "Right" }) {
            float sign = Mathf.Sign(bones[side+"UpperArm"].direction.x);
            if (photographing || side == "Right") {
                ArmTarget(side, new Vector3(sign*.12f, photographing ? 1.065f : .82f, photographing ? .28f : .155f),
                    new Vector3(sign*.38f, .72f, .03f));
                Aim(side+"Hand", new Vector3(-sign*.25f, .95f, .08f));
            } else {
                Vector3 direction = new Vector3(sign*.24f,-.97f,0);
                if (CurrentState == MotionState.Jumping) direction = new Vector3(sign*.65f,-.65f,.3f);
                else if (moving) direction = Quaternion.AngleAxis(swing*(running ? 1.05f : .75f),Vector3.right)*direction;
                Aim(side+"UpperArm",direction); Aim(side+"LowerArm",direction+new Vector3(0,0,.1f));
                Aim(side+"Hand",direction);
            }
        }
    }
    void Rotate(string name, Quaternion delta)
    {
        var b = bones[name];
        b.transform.rotation = Quaternion.Slerp(b.transform.rotation, transform.rotation*delta*b.rotation, blend);
    }
    void Aim(string name, Vector3 direction)
    { Rotate(name, Quaternion.FromToRotation(bones[name].direction,direction.normalized)); }
    void ArmTarget(string side, Vector3 target, Vector3 hint)
    {
        var upper = bones[side+"UpperArm"].transform;
        var lower = bones[side+"LowerArm"].transform;
        var hand = bones[side+"Hand"].transform;
        var start = transform.InverseTransformPoint(upper.position);
        float a = Vector3.Distance(upper.position,lower.position)/transform.lossyScale.x;
        float b = Vector3.Distance(lower.position,hand.position)/transform.lossyScale.x;
        var offset = target-start;
        float distance = Mathf.Clamp(offset.magnitude,Mathf.Abs(a-b)+.001f,a+b-.001f);
        var along = offset.normalized;
        var perpendicular = Vector3.ProjectOnPlane(hint-start,along).normalized;
        if (perpendicular.sqrMagnitude < .01f) perpendicular = Vector3.down;
        float cosine = Mathf.Clamp((a*a+distance*distance-b*b)/(2*a*distance),-1,1);
        var elbow = start+along*(a*cosine)+perpendicular*(a*Mathf.Sqrt(1-cosine*cosine));
        Aim(side+"UpperArm",elbow-start);
        Aim(side+"LowerArm",start+along*distance-elbow);
    }
}
