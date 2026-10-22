using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Places the official Pepper model (Assets/OTC/Pepper/Pepper.fbx, rebuilt from the SoftBank SDK by
/// Tools/pepper/build_pepper.py) into the open scene with URP materials.
///
/// The FBX keeps the Ogre material names from the SDK (shiny_white, face_tex, ...); this swaps each
/// one for a URP Lit material so the look is controlled here rather than by the FBX importer.
/// </summary>
public static class PepperModel
{
    const string ModelPath = "Assets/OTC/Pepper/Pepper.fbx";
    const string TextureDir = "Assets/OTC/Pepper/Textures";
    const string MaterialDir = "Assets/OTC/Pepper/Materials";

    // Real Pepper is 1.21 m tall; used to correct any unit-scale mismatch on import.
    const float PepperHeight = 1.21f;

    // FBX material name of the chest tablet, used to work out which way the model faces.
    const string TabletMaterial = "transparent";

    public static bool Available => File.Exists(ModelPath);

    /// <summary>Instantiates Pepper standing at <paramref name="position"/>, facing <paramref name="lookAt"/>.</summary>
    public static GameObject Place(Vector3 position, Vector3 lookAt)
    {
        var model = AssetDatabase.LoadAssetAtPath<GameObject>(ModelPath);
        if (model == null)
            return null;

        // Wrap the model in a container and only ever move the container: the model's own root
        // carries the FBX Z-up -> Y-up axis conversion, and resetting it lays Pepper on its back.
        var pepper = new GameObject("Pepper");
        var instance = (GameObject)PrefabUtility.InstantiatePrefab(model);
        instance.transform.SetParent(pepper.transform, false);

        Vector3 tabletCenter = ApplyMaterials(pepper);
        NormalizeHeight(pepper);

        // Turn the model so its tablet (its front) points at the participant.
        var bounds = RendererBounds(pepper);
        Vector3 facing = tabletCenter - new Vector3(bounds.center.x, tabletCenter.y, bounds.center.z);
        Vector3 wanted = lookAt - position;
        facing.y = wanted.y = 0f;
        if (facing.sqrMagnitude > 1e-6f)
            pepper.transform.rotation = Quaternion.FromToRotation(facing.normalized, wanted.normalized) *
                                        pepper.transform.rotation;

        // Stand on the floor at the requested spot.
        bounds = RendererBounds(pepper);
        pepper.transform.position += new Vector3(position.x - bounds.center.x, position.y - bounds.min.y,
            position.z - bounds.center.z);
        return pepper;
    }

    /// <summary>Assigns URP materials by FBX material name. Returns the tablet's world-space centre.</summary>
    static Vector3 ApplyMaterials(GameObject pepper)
    {
        var materials = CreateMaterials();
        var tabletPoints = new List<Vector3>();

        foreach (var renderer in pepper.GetComponentsInChildren<MeshRenderer>())
        {
            var shared = renderer.sharedMaterials;
            for (int i = 0; i < shared.Length; i++)
            {
                string name = shared[i] != null ? shared[i].name : "";
                if (name == TabletMaterial)
                    tabletPoints.Add(SubmeshCenter(renderer, i));
                shared[i] = materials.TryGetValue(name, out var mat) ? mat : materials["milky_white"];
            }
            renderer.sharedMaterials = shared;
            renderer.shadowCastingMode = ShadowCastingMode.Off;
        }

        if (tabletPoints.Count == 0)
            return RendererBounds(pepper).center + Vector3.forward; // fall back to the model's +Z
        var sum = Vector3.zero;
        foreach (var p in tabletPoints) sum += p;
        return sum / tabletPoints.Count;
    }

    static Dictionary<string, Material> CreateMaterials()
    {
        Directory.CreateDirectory(MaterialDir);
        AssetDatabase.Refresh();

        return new Dictionary<string, Material>
        {
            ["shiny_white"] = Lit("Pepper_ShinyWhite", new Color(0.93f, 0.93f, 0.93f), smoothness: 0.8f),
            ["milky_white"] = Lit("Pepper_MilkyWhite", new Color(0.86f, 0.86f, 0.85f), smoothness: 0.5f),
            ["black"] = Lit("Pepper_Black", new Color(0.03f, 0.03f, 0.03f), smoothness: 0.6f),
            ["blue_led"] = Lit("Pepper_BlueLED", new Color(0.05f, 0.38f, 0.64f), smoothness: 0.6f,
                emission: new Color(0.1f, 0.6f, 1.5f)),
            ["transparent"] = Lit("Pepper_Tablet", Color.white, smoothness: 0.95f, texture: "juliette_tab.jpg"),
            // Eye LED rings: emission masked by juliette_face_glow.png, tinted at runtime by PepperBehaviour.
            ["face_tex"] = Lit("Pepper_Face", Color.white, smoothness: 0.5f, texture: "juliette_face.png",
                emission: new Color(0.3f, 0.45f, 0.6f), emissionMap: "juliette_face_glow.png"),
            ["ear_tex"] = Lit("Pepper_Ear", new Color(0.75f, 0.75f, 0.75f), smoothness: 0.3f, texture: "juliette_ear.png"),
            ["head_speaker_tex"] = Lit("Pepper_HeadSpeaker", Color.white, smoothness: 0.3f,
                texture: "juliette_head_speaker.png"),
        };
    }

    static Material Lit(string name, Color color, float smoothness, Color? emission = null, string texture = null,
        string emissionMap = null)
    {
        string path = $"{MaterialDir}/{name}.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (mat == null)
        {
            mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            AssetDatabase.CreateAsset(mat, path);
        }

        mat.SetColor("_BaseColor", color);
        mat.SetFloat("_Smoothness", smoothness);
        if (texture != null)
            mat.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TextureDir}/{texture}"));
        if (emission.HasValue)
        {
            mat.EnableKeyword("_EMISSION");
            mat.SetColor("_EmissionColor", emission.Value);
            if (emissionMap != null)
                mat.SetTexture("_EmissionMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TextureDir}/{emissionMap}"));
            mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
        }
        EditorUtility.SetDirty(mat);
        return mat;
    }

    static void NormalizeHeight(GameObject pepper)
    {
        float height = RendererBounds(pepper).size.y;
        if (height > 0.01f && Mathf.Abs(height - PepperHeight) / PepperHeight > 0.05f)
            pepper.transform.localScale *= PepperHeight / height;
    }

    static Vector3 SubmeshCenter(MeshRenderer renderer, int submesh)
    {
        var mesh = renderer.GetComponent<MeshFilter>().sharedMesh;
        if (mesh == null || submesh >= mesh.subMeshCount)
            return renderer.bounds.center;
        return renderer.transform.TransformPoint(mesh.GetSubMesh(submesh).bounds.center);
    }

    static Bounds RendererBounds(GameObject go)
    {
        var renderers = go.GetComponentsInChildren<Renderer>();
        var b = renderers[0].bounds;
        foreach (var r in renderers) b.Encapsulate(r.bounds);
        return b;
    }
}
