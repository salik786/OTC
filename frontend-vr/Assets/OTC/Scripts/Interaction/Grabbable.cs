using System;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// An object the participant can pick up with a controller grip or a hand pinch. Falls back to its
    /// home spot if dropped out of reach.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class Grabbable : MonoBehaviour
    {
        public event Action<Grabbable> PickedUp;
        public event Action<Grabbable> Released;

        public bool IsHeld => _holder != null;

        Rigidbody _body;
        Transform _holder;
        Vector3 _homePos;
        Quaternion _homeRot;
        Pose _offset;
        Vector3 _lastPos, _velocity;

        void Awake()
        {
            _body = GetComponent<Rigidbody>();
            _homePos = transform.position;
            _homeRot = transform.rotation;
        }

        public void SetHome(Vector3 position, Quaternion rotation)
        {
            _homePos = position;
            _homeRot = rotation;
        }

        public void Grab(Transform holder)
        {
            if (_holder != null) return;
            _holder = holder;
            _body.isKinematic = true;
            _offset = new Pose(holder.InverseTransformPoint(transform.position),
                Quaternion.Inverse(holder.rotation) * transform.rotation);
            _lastPos = transform.position;
            PickedUp?.Invoke(this);
        }

        public void Release()
        {
            if (_holder == null) return;
            _holder = null;
            _body.isKinematic = false;
            _body.linearVelocity = Vector3.ClampMagnitude(_velocity, 3f);
            Released?.Invoke(this);
        }

        public void ReturnHome()
        {
            _body.isKinematic = true;
            transform.SetPositionAndRotation(_homePos, _homeRot);
            _body.isKinematic = false;
            _body.linearVelocity = Vector3.zero;
            _body.angularVelocity = Vector3.zero;
        }

        void LateUpdate()
        {
            if (_holder != null)
            {
                transform.SetPositionAndRotation(_holder.TransformPoint(_offset.position), _holder.rotation * _offset.rotation);
                _velocity = (transform.position - _lastPos) / Mathf.Max(Time.deltaTime, 1e-4f);
                _lastPos = transform.position;
            }
            else if (transform.position.y < 0.15f || (transform.position - _homePos).sqrMagnitude > 9f)
            {
                ReturnHome(); // dropped on the floor or thrown away
            }
        }
    }
}
