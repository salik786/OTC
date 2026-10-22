using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// A small table within reach of the seated participant holding one box of each study medicine.
    /// Boxes are real objects you can pick up and turn over; their packaging comes from the same label
    /// atlas as the shelves (Tools/pharmacy/make_textures.py).
    /// </summary>
    public class ProductTray : MonoBehaviour
    {
        public Material boxMaterial;    // Env_Products (medicine_atlas.png)
        public Material tableMaterial;  // Env_GlossWhite
        public Material legMaterial;    // Env_Metal

        public event Action<OtcApi.Product> ProductPickedUp;
        public event Action<OtcApi.Product> ProductReleased;

        // Atlas tile per product name (order of PRODUCTS in make_textures.py).
        static readonly string[] AtlasNames =
        {
            "paracetamol", "multivitamin", "ibuprofen", "vitamin c", "cetirizine", "loratadine", "aspirin", "antacid",
            "vitamin d", "zinc", "omega", "lozenge", "saline", "antiseptic", "hayfever", "cold",
        };

        static readonly Vector3 BoxSize = new Vector3(0.095f, 0.14f, 0.04f);
        const float TableHeight = 0.7f;

        readonly Dictionary<Grabbable, OtcApi.Product> _products = new Dictionary<Grabbable, OtcApi.Product>();

        /// <summary>Builds the table at this transform (front edge facing the participant) and its boxes.</summary>
        public void Build(IList<OtcApi.Product> products, Vector3 viewer)
        {
            foreach (Transform child in transform) Destroy(child.gameObject);
            _products.Clear();

            Vector3 away = transform.position - viewer;
            away.y = 0f;
            transform.rotation = Quaternion.LookRotation(away.normalized, Vector3.up);

            float width = Mathf.Max(0.45f, products.Count * 0.14f + 0.12f);
            Part("Top", new Vector3(0f, TableHeight - 0.015f, 0f), new Vector3(width, 0.03f, 0.36f), tableMaterial, true);
            foreach (float x in new[] { -width / 2 + 0.03f, width / 2 - 0.03f })
            foreach (float z in new[] { -0.15f, 0.15f })
                Part("Leg", new Vector3(x, (TableHeight - 0.03f) / 2f, z), new Vector3(0.025f, TableHeight - 0.03f, 0.025f), legMaterial, false);

            for (int i = 0; i < products.Count; i++)
            {
                float x = (i - (products.Count - 1) / 2f) * 0.14f;
                var box = MakeBox(products[i], new Vector3(x, TableHeight + BoxSize.y / 2f + 0.002f, 0.02f));
                _products[box] = products[i];
            }
        }

        void Part(string name, Vector3 localPos, Vector3 size, Material mat, bool collider)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(transform, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = size;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            if (!collider) Destroy(go.GetComponent<Collider>());
        }

        Grabbable MakeBox(OtcApi.Product product, Vector3 localPos)
        {
            var go = new GameObject($"Box ({product.display_name})");
            go.transform.SetParent(transform, false);
            go.transform.localPosition = localPos;
            // Label faces the participant: box front is its local -Z, and the tray's -Z points at them.
            go.AddComponent<MeshFilter>().sharedMesh = BoxMesh(TileFor(product));
            go.AddComponent<MeshRenderer>().sharedMaterial = boxMaterial;
            go.AddComponent<BoxCollider>().size = BoxSize;
            var body = go.AddComponent<Rigidbody>();
            body.mass = 0.05f;
            body.interpolation = RigidbodyInterpolation.Interpolate;
            body.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;

            if (TileFor(product) < 0)
            {
                // Product not in the atlas (added later via the admin panel): print its name on the box.
                var label = new GameObject("Label").AddComponent<TextMeshPro>();
                label.transform.SetParent(go.transform, false);
                label.transform.localPosition = new Vector3(0f, 0f, -BoxSize.z / 2f - 0.001f);
                label.rectTransform.sizeDelta = new Vector2(BoxSize.x * 0.9f, BoxSize.y * 0.8f);
                label.text = product.display_name;
                label.fontSize = 0.12f;
                label.color = new Color(0.1f, 0.1f, 0.1f);
                label.alignment = TextAlignmentOptions.Center;
            }

            var grab = go.AddComponent<Grabbable>();
            grab.SetHome(go.transform.position, go.transform.rotation);
            grab.PickedUp += g => ProductPickedUp?.Invoke(_products[g]);
            grab.Released += g => ProductReleased?.Invoke(_products[g]);
            return grab;
        }

        static int TileFor(OtcApi.Product product)
        {
            string key = $"{product.slug} {product.display_name}".ToLowerInvariant();
            for (int i = 0; i < AtlasNames.Length; i++)
                if (key.Contains(AtlasNames[i])) return i;
            return -1;
        }

        /// <summary>Box mesh with the atlas tile's label on front and back, its brand colour elsewhere.</summary>
        static Mesh BoxMesh(int tile)
        {
            Vector3 h = BoxSize / 2f;
            float u0 = 0.5f, u1 = 0.5f, fv0 = 0.5f, fv1 = 0.5f, sv = 0.5f, su = 0.5f;
            if (tile >= 0)
            {
                int col = tile % 4, row = tile / 4;
                u0 = col / 4f; u1 = (col + 1) / 4f;
                float top = 1f - row / 4f;
                fv1 = top; fv0 = top - 320f / 2048f;           // label region of the tile
                sv = top - 416f / 2048f; su = (u0 + u1) / 2f;    // middle of the side-colour region
            }

            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();

            void Face(Vector3 a, Vector3 b, Vector3 c, Vector3 d, bool label, bool mirror)
            {
                int i = verts.Count;
                verts.AddRange(new[] { a, b, c, d });
                if (label)
                {
                    float l = mirror ? u1 : u0, r = mirror ? u0 : u1;
                    uvs.AddRange(new[] { new Vector2(l, fv0), new Vector2(l, fv1), new Vector2(r, fv1), new Vector2(r, fv0) });
                }
                else
                {
                    uvs.AddRange(new[] { new Vector2(su, sv), new Vector2(su, sv), new Vector2(su, sv), new Vector2(su, sv) });
                }
                tris.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
            }

            // Front (-Z, faces the participant): bottom-left, top-left, top-right, bottom-right as seen from the front.
            Face(new Vector3(-h.x, -h.y, -h.z), new Vector3(-h.x, h.y, -h.z), new Vector3(h.x, h.y, -h.z), new Vector3(h.x, -h.y, -h.z), true, false);
            // Back (+Z): same label, read from behind.
            Face(new Vector3(h.x, -h.y, h.z), new Vector3(h.x, h.y, h.z), new Vector3(-h.x, h.y, h.z), new Vector3(-h.x, -h.y, h.z), true, false);
            // Sides, top, bottom.
            Face(new Vector3(-h.x, -h.y, h.z), new Vector3(-h.x, h.y, h.z), new Vector3(-h.x, h.y, -h.z), new Vector3(-h.x, -h.y, -h.z), false, false);
            Face(new Vector3(h.x, -h.y, -h.z), new Vector3(h.x, h.y, -h.z), new Vector3(h.x, h.y, h.z), new Vector3(h.x, -h.y, h.z), false, false);
            Face(new Vector3(-h.x, h.y, -h.z), new Vector3(-h.x, h.y, h.z), new Vector3(h.x, h.y, h.z), new Vector3(h.x, h.y, -h.z), false, false);
            Face(new Vector3(-h.x, -h.y, h.z), new Vector3(-h.x, -h.y, -h.z), new Vector3(h.x, -h.y, -h.z), new Vector3(h.x, -h.y, h.z), false, false);

            var mesh = new Mesh { name = $"MedicineBox_{tile}" };
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
