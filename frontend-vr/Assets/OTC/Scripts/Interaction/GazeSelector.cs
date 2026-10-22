using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// Look-to-select: a small reticle follows the participant's gaze; resting it on a button fills a ring
    /// and presses the button. Hands-free access for people who can't use controllers or pinch, and the
    /// way to click when testing in the Meta XR Simulator with the mouse. Active in the Editor, and on
    /// the headset whenever no controller or tracked hand is in use.
    /// </summary>
    public class GazeSelector : MonoBehaviour
    {
        public Transform head;               // CenterEyeAnchor
        public Material material;            // unlit, for the reticle
        public OVRHand[] hands;
        public float dwellSeconds = 1.1f;
        public float maxDistance = 4f;
        public bool alwaysOnInEditor = true;

        LineRenderer _ring;
        Transform _dot;
        VRButton _target;
        float _dwell;
        bool _pressedTarget;
        const int RingSegments = 40;

        void Start()
        {
            var ringGo = new GameObject("Gaze Ring");
            ringGo.transform.SetParent(transform, false);
            _ring = ringGo.AddComponent<LineRenderer>();
            _ring.sharedMaterial = material;
            _ring.useWorldSpace = true;
            _ring.widthMultiplier = 0.003f;
            _ring.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _ring.receiveShadows = false;

            var dot = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Destroy(dot.GetComponent<Collider>());
            dot.name = "Gaze Dot";
            dot.transform.SetParent(transform, false);
            dot.transform.localScale = Vector3.one * 0.008f;
            dot.GetComponent<Renderer>().sharedMaterial = material;
            _dot = dot.transform;
        }

        bool Active
        {
            get
            {
                if (Application.isEditor && alwaysOnInEditor) return true;
                if ((OVRInput.GetConnectedControllers() & OVRInput.Controller.Touch) != 0)
                    return false;
                foreach (var h in hands)
                    if (h != null && h.IsTracked) return false;
                return true;
            }
        }

        void Update()
        {
            bool active = head != null && Active;
            if (!active)
            {
                _dot.gameObject.SetActive(false);
                _ring.enabled = false;
                return;
            }

            VRButton hitButton = null;
            Vector3 point = head.position + head.forward * 1.5f;
            Vector3 normal = -head.forward;
            if (Physics.Raycast(head.position, head.forward, out var hit, maxDistance, ~0, QueryTriggerInteraction.Collide))
            {
                hitButton = hit.collider.GetComponent<VRButton>();
                point = hit.point;
                normal = hit.normal;
            }

            if (hitButton != _target)
            {
                if (Application.isEditor) Debug.Log($"[OTC] Gaze on: {(hitButton != null ? hitButton.name : hit.collider != null ? "(blocked by " + hit.collider.name + ")" : "nothing")}");
                _target = hitButton;
                _dwell = 0f;
                _pressedTarget = false;
            }

            if (_target != null && _target.Interactable && !_pressedTarget)
            {
                _target.Hover();
                _dwell += Time.deltaTime;
                if (_dwell >= dwellSeconds)
                {
                    _target.Press();
                    _pressedTarget = true; // look away (or at another button) before it can fire again
                }
            }

            // Reticle: a dot at the gaze point, and a ring that fills while dwelling on a button.
            _dot.gameObject.SetActive(true);
            _dot.position = point + normal * 0.004f;
            float progress = _target != null && !_pressedTarget ? Mathf.Clamp01(_dwell / dwellSeconds) : 0f;
            DrawRing(point + normal * 0.005f, normal, 0.018f, progress);
        }

        void DrawRing(Vector3 center, Vector3 normal, float radius, float progress)
        {
            if (progress <= 0f)
            {
                _ring.enabled = false;
                return;
            }
            _ring.enabled = true;
            int count = Mathf.Max(2, Mathf.CeilToInt(RingSegments * progress) + 1);
            _ring.positionCount = count;
            Vector3 up = Vector3.ProjectOnPlane(Vector3.up, normal).normalized;
            if (up.sqrMagnitude < 0.01f) up = Vector3.ProjectOnPlane(Vector3.forward, normal).normalized;
            Vector3 right = Vector3.Cross(normal, up);
            for (int i = 0; i < count; i++)
            {
                float a = progress * Mathf.PI * 2f * i / (count - 1);
                _ring.SetPosition(i, center + (up * Mathf.Cos(a) + right * Mathf.Sin(a)) * radius);
            }
        }
    }
}
