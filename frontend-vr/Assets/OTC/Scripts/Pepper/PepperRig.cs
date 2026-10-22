using System.Collections.Generic;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// Drives the imported Pepper model's joints by NAOqi joint name and angle (radians), the same
    /// convention the real robot and its .qianim animations use.
    ///
    /// Each joint in the FBX is "&lt;Joint&gt;_origin" (fixed) -> "&lt;Joint&gt;" (rotates about its URDF axis) and
    /// was exported already posed in StandInit. Blender -> FBX -> Unity changes handedness, so instead of
    /// assuming how the axes came through, Awake() tests the candidate axis mappings against the
    /// StandInit pose baked into the model and keeps the one that reproduces it.
    /// </summary>
    public class PepperRig : MonoBehaviour
    {
        struct Spec
        {
            public Vector3 Axis;   // URDF axis in the joint frame
            public float Stand;    // StandInit angle (the pose the model was exported in)
            public float Min, Max; // NAOqi joint limits
            public Spec(Vector3 axis, float stand, float min, float max) { Axis = axis; Stand = stand; Min = min; Max = max; }
        }

        static readonly Dictionary<string, Spec> Specs = new Dictionary<string, Spec>
        {
            ["HeadYaw"] = new Spec(Vector3.forward, 0f, -2.0857f, 2.0857f),
            ["HeadPitch"] = new Spec(Vector3.up, -0.2f, -0.7068f, 0.6371f),
            ["HipRoll"] = new Spec(Vector3.right, 0f, -0.5149f, 0.5149f),
            ["HipPitch"] = new Spec(Vector3.up, -0.04f, -1.0385f, 1.0385f),
            ["KneePitch"] = new Spec(Vector3.up, -0.01f, -0.5149f, 0.5149f),
            ["LShoulderPitch"] = new Spec(Vector3.up, 1.57f, -2.0857f, 2.0857f),
            ["LShoulderRoll"] = new Spec(Vector3.forward, 0.12f, 0.0087f, 1.5620f),
            ["LElbowYaw"] = new Spec(Vector3.right, -1.2217f, -2.0857f, 2.0857f),
            ["LElbowRoll"] = new Spec(Vector3.forward, -0.5235f, -1.5620f, -0.0087f),
            ["LWristYaw"] = new Spec(Vector3.right, 0f, -1.8239f, 1.8239f),
            ["RShoulderPitch"] = new Spec(Vector3.up, 1.57f, -2.0857f, 2.0857f),
            ["RShoulderRoll"] = new Spec(Vector3.forward, -0.12f, -1.5620f, -0.0087f),
            ["RElbowYaw"] = new Spec(Vector3.right, 1.2217f, -2.0857f, 2.0857f),
            ["RElbowRoll"] = new Spec(Vector3.forward, 0.5235f, 0.0087f, 1.5620f),
            ["RWristYaw"] = new Spec(Vector3.right, 0f, -1.8239f, 1.8239f),
        };

        public static float StandAngle(string joint) => Specs.TryGetValue(joint, out var s) ? s.Stand : 0f;

        class Joint
        {
            public Transform T;
            public Quaternion Rest;
            public Spec Spec;
            public float Current, Target, Velocity;
        }

        [Tooltip("Smoothing time for joint motion (s). Lower = snappier.")]
        public float smoothTime = 0.18f;

        readonly Dictionary<string, Joint> _joints = new Dictionary<string, Joint>();
        Vector3 _axisMirror = new Vector3(1, -1, -1);
        float _angleSign = 1f;

        public bool Ready => _joints.Count > 0;

        void Awake()
        {
            var byName = new Dictionary<string, Transform>();
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (!byName.ContainsKey(t.name)) byName[t.name] = t;

            foreach (var kv in Specs)
            {
                if (!byName.TryGetValue(kv.Key, out var t)) continue;
                _joints[kv.Key] = new Joint
                {
                    T = t, Rest = t.localRotation, Spec = kv.Value,
                    Current = kv.Value.Stand, Target = kv.Value.Stand,
                };
            }

            if (_joints.Count == 0)
                Debug.LogWarning("[OTC] PepperRig found no joints - is this the Pepper model?");
            else
                Calibrate();
        }

        /// <summary>Picks the axis mirroring / angle sign that reproduces the exported StandInit pose.</summary>
        void Calibrate()
        {
            Vector3[] mirrors = { new Vector3(1, -1, -1), new Vector3(-1, 1, 1), new Vector3(1, 1, 1), new Vector3(-1, -1, 1) };
            float best = float.MaxValue;
            foreach (var mirror in mirrors)
            foreach (float sign in new[] { 1f, -1f })
            {
                float error = 0f;
                int count = 0;
                foreach (var j in _joints.Values)
                {
                    if (Mathf.Abs(j.Spec.Stand) < 0.1f) continue;
                    var expected = Quaternion.AngleAxis(sign * j.Spec.Stand * Mathf.Rad2Deg, Vector3.Scale(j.Spec.Axis, mirror));
                    error += Quaternion.Angle(expected, j.Rest);
                    count++;
                }
                if (count > 0 && error / count < best)
                {
                    best = error / count;
                    _axisMirror = mirror;
                    _angleSign = sign;
                }
            }
            if (best > 5f)
                Debug.LogWarning($"[OTC] PepperRig calibration is approximate (mean error {best:F1} deg) - motions are applied relative to the exported pose.");
        }

        public bool Has(string joint) => _joints.ContainsKey(joint);

        /// <summary>Sets a joint's target angle in radians (NAOqi convention), clamped to its limits.</summary>
        public void Set(string joint, float radians)
        {
            if (_joints.TryGetValue(joint, out var j))
                j.Target = Mathf.Clamp(radians, j.Spec.Min, j.Spec.Max);
        }

        public float Get(string joint) => _joints.TryGetValue(joint, out var j) ? j.Current : 0f;

        void LateUpdate()
        {
            foreach (var j in _joints.Values)
            {
                j.Current = Mathf.SmoothDamp(j.Current, j.Target, ref j.Velocity, smoothTime);
                // Relative to the exported (StandInit) pose: rotations about one axis commute, so this
                // equals the absolute rotation when the calibration is exact, and degrades gracefully if not.
                float delta = (j.Current - j.Spec.Stand) * _angleSign * Mathf.Rad2Deg;
                j.T.localRotation = j.Rest * Quaternion.AngleAxis(delta, Vector3.Scale(j.Spec.Axis, _axisMirror));
            }
        }
    }
}
