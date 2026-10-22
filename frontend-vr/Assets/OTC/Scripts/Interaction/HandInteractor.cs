using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// One per hand. Works with either Touch controllers or tracked hands, switching automatically:
    ///  - point at a button and pull the trigger / pinch to press it (laser ray shown while aiming)
    ///  - touch a button with the controller tip or index fingertip to press it
    ///  - squeeze the grip / pinch near a medicine box to pick it up, let go to drop it
    /// </summary>
    public class HandInteractor : MonoBehaviour
    {
        public OVRInput.Controller controller = OVRInput.Controller.RTouch;
        public Transform controllerAnchor;  // OVRCameraRig Left/RightControllerAnchor
        public OVRHand hand;                // optional, for hand tracking
        public LineRenderer ray;

        public float grabRadius = 0.09f;
        public float rayLength = 3f;
        public float pokeRadius = 0.015f;

        Grabbable _held;
        bool _selectWasDown, _grabWasDown;
        Transform _pokeTip;
        static readonly Collider[] Overlaps = new Collider[16];

        bool HandMode => hand != null && hand.IsTracked && hand.IsDataHighConfidence;

        void Start()
        {
            if (ray != null)
            {
                ray.positionCount = 2;
                ray.useWorldSpace = true;
                ray.enabled = false;
            }
            _pokeTip = FindIndexTip();
        }

        void Update()
        {
            bool handMode = HandMode;
            // Hand bones are created by OVRSkeleton once tracking starts, so look again until found.
            if (handMode && _pokeTip == null && Time.frameCount % 30 == 0) _pokeTip = FindIndexTip();
            Transform pointer = handMode && hand.IsPointerPoseValid ? hand.PointerPose : controllerAnchor;
            if (pointer == null) return;

            bool selectDown, grabDown;
            Vector3 grabPoint;
            if (handMode)
            {
                float pinch = hand.GetFingerPinchStrength(OVRHand.HandFinger.Index);
                grabPoint = _pokeTip != null ? _pokeTip.position : pointer.position;
                bool nearGrabbable = _held != null || NearestGrabbable(grabPoint) != null;
                // A pinch grabs when a box is within reach, otherwise it acts as a ray "click".
                grabDown = nearGrabbable && pinch > 0.75f;
                selectDown = !nearGrabbable && pinch > 0.85f;
            }
            else
            {
                selectDown = OVRInput.Get(OVRInput.Axis1D.PrimaryIndexTrigger, controller) > 0.6f;
                grabDown = OVRInput.Get(OVRInput.Axis1D.PrimaryHandTrigger, controller) > 0.6f;
                grabPoint = controllerAnchor.position + controllerAnchor.forward * 0.04f;
            }

            UpdateGrab(grabDown, grabPoint, handMode ? pointer : controllerAnchor);
            UpdatePointer(pointer, selectDown && _held == null);
            UpdatePoke(handMode ? _pokeTip : controllerAnchor);
        }

        void UpdateGrab(bool down, Vector3 point, Transform holder)
        {
            if (down && !_grabWasDown && _held == null)
            {
                var target = NearestGrabbable(point);
                if (target != null && !target.IsHeld)
                {
                    _held = target;
                    _held.Grab(holder);
                    OVRInput.SetControllerVibration(0.3f, 0.25f, controller);
                    Invoke(nameof(StopVibration), 0.08f);
                }
            }
            else if (!down && _held != null)
            {
                _held.Release();
                _held = null;
            }
            _grabWasDown = down;
        }

        void UpdatePointer(Transform pointer, bool selectDown)
        {
            VRButton target = null;
            Vector3 end = pointer.position + pointer.forward * 0.25f;
            if (_held == null && Physics.Raycast(pointer.position, pointer.forward, out var hit, rayLength,
                    ~0, QueryTriggerInteraction.Collide))
            {
                target = hit.collider.GetComponent<VRButton>();
                end = hit.point;
            }

            if (target != null)
            {
                target.Hover();
                if (selectDown && !_selectWasDown) target.Press();
            }

            if (ray != null)
            {
                // The ray only shows while it is useful: aiming at a button.
                ray.enabled = target != null;
                ray.SetPosition(0, pointer.position);
                ray.SetPosition(1, end);
            }
            _selectWasDown = selectDown;
        }

        void UpdatePoke(Transform tip)
        {
            if (tip == null || _held != null) return;
            int n = Physics.OverlapSphereNonAlloc(tip.position, pokeRadius, Overlaps, ~0, QueryTriggerInteraction.Collide);
            for (int i = 0; i < n; i++)
            {
                var button = Overlaps[i].GetComponent<VRButton>();
                if (button == null) continue;
                button.Hover();
                button.Press();
            }
        }

        Grabbable NearestGrabbable(Vector3 point)
        {
            int n = Physics.OverlapSphereNonAlloc(point, grabRadius, Overlaps, ~0, QueryTriggerInteraction.Ignore);
            Grabbable best = null;
            float bestDist = float.MaxValue;
            for (int i = 0; i < n; i++)
            {
                var g = Overlaps[i].GetComponentInParent<Grabbable>();
                if (g == null || g.IsHeld) continue;
                float d = (Overlaps[i].ClosestPoint(point) - point).sqrMagnitude;
                if (d < bestDist) { bestDist = d; best = g; }
            }
            return best;
        }

        Transform FindIndexTip()
        {
            if (hand == null) return null;
            foreach (var t in hand.GetComponentsInChildren<Transform>(true))
                if (t.name.Contains("IndexTip")) return t;
            return null;
        }

        void StopVibration() => OVRInput.SetControllerVibration(0f, 0f, controller);
    }
}
