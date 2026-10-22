using TMPro;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// Tiny world-space UI kit: panels, text and buttons built from quads + TextMeshPro. Materials are
    /// passed in from the scene (assigned by the Editor builder) so their shaders are included in builds.
    /// </summary>
    public static class Ui
    {
        public static Material PanelMaterial;  // URP Unlit, tinted per instance
        public static Material ButtonMaterial;

        public static readonly Color PanelColor = new Color(0.06f, 0.09f, 0.1f, 1f);
        public static readonly Color TextColor = new Color(0.96f, 0.97f, 0.97f);
        public static readonly Color MutedText = new Color(0.7f, 0.76f, 0.78f);
        public static readonly Color Accent = new Color(0.2f, 0.75f, 0.6f);
        public static readonly Color Danger = new Color(0.75f, 0.12f, 0.1f);

        static readonly int BaseColor = Shader.PropertyToID("_BaseColor");

        /// <summary>A panel facing <paramref name="viewer"/>. Children are laid out in its local space
        /// (x right, y up, metres), with z slightly negative to sit in front of the background.</summary>
        public static Transform Panel(string name, Transform parent, Vector3 position, Vector3 viewer, Vector2 size,
            Color? color = null)
        {
            var root = new GameObject(name).transform;
            root.SetParent(parent, false);
            root.position = position;
            Face(root, viewer);

            var bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
            bg.name = "Background";
            Object.Destroy(bg.GetComponent<Collider>());
            bg.transform.SetParent(root, false);
            bg.transform.localScale = new Vector3(size.x, size.y, 1f);
            Tint(bg.GetComponent<Renderer>(), PanelMaterial, color ?? PanelColor);
            return root;
        }

        /// <summary>Turns a panel so its front faces the viewer, staying upright.</summary>
        public static void Face(Transform t, Vector3 viewer)
        {
            Vector3 away = t.position - viewer;
            away.y *= 0.35f; // mostly upright, slight tilt towards the viewer's eyes
            if (away.sqrMagnitude > 1e-4f)
                t.rotation = Quaternion.LookRotation(away.normalized, Vector3.up);
        }

        public static TextMeshPro Text(Transform parent, string text, Vector2 localPos, Vector2 size, float fontSize,
            TextAlignmentOptions align = TextAlignmentOptions.Center, Color? color = null)
        {
            var go = new GameObject("Text");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = new Vector3(localPos.x, localPos.y, -0.004f);
            var tmp = go.AddComponent<TextMeshPro>();
            tmp.rectTransform.sizeDelta = size;
            tmp.text = text;
            tmp.fontSize = fontSize;
            tmp.alignment = align;
            tmp.color = color ?? TextColor;
            tmp.textWrappingMode = TextWrappingModes.Normal;
            tmp.overflowMode = TextOverflowModes.Ellipsis;
            return tmp;
        }

        public static VRButton Button(Transform parent, string label, Vector2 localPos, Vector2 size, float fontSize = 0.6f,
            Color? color = null)
        {
            var go = new GameObject($"Button ({label})");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = new Vector3(localPos.x, localPos.y, -0.006f);

            var bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
            bg.name = "Background";
            Object.Destroy(bg.GetComponent<Collider>());
            bg.transform.SetParent(go.transform, false);
            bg.transform.localScale = new Vector3(size.x, size.y, 1f);
            Tint(bg.GetComponent<Renderer>(), ButtonMaterial, color ?? new Color(0.16f, 0.45f, 0.38f));

            var collider = go.AddComponent<BoxCollider>();
            collider.size = new Vector3(size.x, size.y, 0.03f);
            collider.center = new Vector3(0f, 0f, -0.01f);

            var button = go.AddComponent<VRButton>();
            button.background = bg.GetComponent<Renderer>();
            if (color.HasValue) button.normalColor = color.Value;
            button.label = Text(go.transform, label, Vector2.zero, size * 0.92f, fontSize);
            button.label.transform.localPosition = new Vector3(0f, 0f, -0.003f);
            button.Interactable = true;
            return button;
        }

        public static void Tint(Renderer renderer, Material material, Color color)
        {
            renderer.sharedMaterial = material;
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            renderer.receiveShadows = false;
            var mpb = new MaterialPropertyBlock();
            mpb.SetColor(BaseColor, color);
            renderer.SetPropertyBlock(mpb);
        }

        public static float FontScale(CaptionSize size) => size switch
        {
            CaptionSize.Small => 0.8f,
            CaptionSize.Large => 1.35f,
            _ => 1f,
        };
    }
}
