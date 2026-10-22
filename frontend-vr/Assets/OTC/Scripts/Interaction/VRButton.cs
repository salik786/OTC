using System;
using TMPro;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// A world-space button that can be pressed by pointing (controller ray / hand pinch ray) or by
    /// touching it with a fingertip or controller. Built by Ui.Button().
    /// </summary>
    [RequireComponent(typeof(BoxCollider))]
    public class VRButton : MonoBehaviour
    {
        public Renderer background;
        public TextMeshPro label;
        public Color normalColor = new Color(0.16f, 0.45f, 0.38f);
        public Color hoverColor = new Color(0.22f, 0.58f, 0.49f);
        public Color disabledColor = new Color(0.35f, 0.35f, 0.35f);
        public Color selectedColor = new Color(0.95f, 0.65f, 0.15f);

        public event Action Clicked;

        public bool Interactable { get => _interactable; set { _interactable = value; Refresh(); } }
        public bool Selected { get => _selected; set { _selected = value; Refresh(); } }

        bool _interactable = true, _selected, _hovered;
        float _hoverFrame = -1f, _lastClick = -10f;
        MaterialPropertyBlock _mpb;
        static readonly int BaseColor = Shader.PropertyToID("_BaseColor");

        void Awake()
        {
            _mpb = new MaterialPropertyBlock();
            Refresh();
        }

        public void SetText(string text)
        {
            if (label != null) label.text = text;
        }

        /// <summary>Called every frame something points at the button.</summary>
        public void Hover()
        {
            _hoverFrame = Time.frameCount;
            if (!_hovered) { _hovered = true; Refresh(); }
        }

        public void Press()
        {
            // Debounce: a poke and a ray select in the same moment must not double-fire.
            if (!_interactable || Time.unscaledTime - _lastClick < 0.35f) return;
            _lastClick = Time.unscaledTime;
            Clicked?.Invoke();
        }

        void LateUpdate()
        {
            if (_hovered && Time.frameCount - _hoverFrame > 1)
            {
                _hovered = false;
                Refresh();
            }
        }

        void Refresh()
        {
            if (background == null) return;
            _mpb ??= new MaterialPropertyBlock();
            Color c = !_interactable ? disabledColor : _selected ? selectedColor : _hovered ? hoverColor : normalColor;
            background.GetPropertyBlock(_mpb);
            _mpb.SetColor(BaseColor, c);
            background.SetPropertyBlock(_mpb);
            transform.localScale = _hovered && _interactable ? new Vector3(1.04f, 1.04f, 1f) : Vector3.one;
        }
    }
}
