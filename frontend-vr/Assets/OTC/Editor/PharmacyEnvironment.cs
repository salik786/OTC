using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Places the Blender-built pharmacy (Assets/OTC/Environment/Pharmacy.fbx, from
/// Tools/pharmacy/build_pharmacy.py) and sets up its URP materials and baked lighting.
///
/// Lighting is fully baked for Quest 2: rectangular area lights under each ceiling panel, emissive
/// panels and sign, light probes so the (dynamic) Pepper picks up the room's light, and a box-projected
/// reflection probe for the glossy counter, floor and Pepper's shell.
/// </summary>
public static class PharmacyEnvironment
{
    const string ModelPath = "Assets/OTC/Environment/Pharmacy.fbx";
    const string TextureDir = "Assets/OTC/Environment/Textures";
    const string MaterialDir = "Assets/OTC/Environment/Materials";
    const string LightingSettingsPath = "Assets/OTC/Environment/PharmacyLighting.lighting";

    // Must match build_pharmacy.py.
    static readonly Vector2 RoomX = new Vector2(-3.5f, 3.5f);
    static readonly Vector2 RoomZ = new Vector2(-2f, 6f);
    const float RoomHeight = 3f;
    static readonly float[] PanelX = { -2f, 0f, 2f };
    static readonly float[] PanelZ = { -0.6f, 1.4f, 3.4f, 5.2f };

    public static bool Available => File.Exists(ModelPath);

    public static GameObject Place()
    {
        ReimportGeneratedAssets();
        var model = AssetDatabase.LoadAssetAtPath<GameObject>(ModelPath);
        if (model == null)
            return null;

        // Container keeps the FBX root's axis conversion intact (see PepperModel).
        var root = new GameObject("Pharmacy");
        var instance = (GameObject)PrefabUtility.InstantiatePrefab(model);
        instance.transform.SetParent(root.transform, false);

        var materials = CreateMaterials();
        foreach (var renderer in root.GetComponentsInChildren<MeshRenderer>())
        {
            var shared = renderer.sharedMaterials;
            for (int i = 0; i < shared.Length; i++)
            {
                string name = shared[i] != null ? shared[i].name : "";
                if (materials.TryGetValue(name, out var mat))
                    shared[i] = mat;
                else
                    Debug.LogWarning($"[OTC] No URP material for '{name}' on {renderer.name}");
            }
            renderer.sharedMaterials = shared;
            renderer.shadowCastingMode = ShadowCastingMode.On; // shadows are baked, never realtime
            renderer.receiveGI = ReceiveGI.Lightmaps;
        }

        foreach (var t in root.GetComponentsInChildren<Transform>())
            GameObjectUtility.SetStaticEditorFlags(t.gameObject,
                StaticEditorFlags.ContributeGI | StaticEditorFlags.BatchingStatic |
                StaticEditorFlags.ReflectionProbeStatic | StaticEditorFlags.OccluderStatic |
                StaticEditorFlags.OccludeeStatic);

        return root;
    }

    /// <summary>Area lights, probes and lightmap settings. Call after Place().</summary>
    public static void BuildLighting()
    {
        var lights = new GameObject("Lighting");

        foreach (float x in PanelX)
        foreach (float z in PanelZ)
        {
            var go = new GameObject($"PanelLight ({x}, {z})");
            go.transform.SetParent(lights.transform);
            go.transform.SetPositionAndRotation(new Vector3(x, RoomHeight - 0.02f, z), Quaternion.Euler(90f, 0f, 0f));
            var light = go.AddComponent<Light>();
            light.type = LightType.Rectangle;
            light.areaSize = new Vector2(0.58f, 0.58f);
            light.lightmapBakeType = LightmapBakeType.Baked;
            light.color = new Color(1f, 0.97f, 0.92f); // ~4000K, typical retail LED panel
            light.intensity = 4.5f;
            light.range = 8f;
        }

        // Light probes in a grid over the floor area, so Pepper (not static) is lit like the room.
        var probes = new GameObject("Light Probes").AddComponent<LightProbeGroup>();
        probes.transform.SetParent(lights.transform);
        var positions = new List<Vector3>();
        for (float x = RoomX.x + 0.5f; x <= RoomX.y - 0.5f; x += 1f)
        for (float z = RoomZ.x + 0.5f; z <= RoomZ.y - 0.5f; z += 1f)
        foreach (float y in new[] { 0.3f, 1.2f, 2.4f })
            positions.Add(new Vector3(x, y, z));
        probes.probePositions = positions.ToArray();

        // Box-projected reflection probe covering the room.
        var reflection = new GameObject("Reflection Probe").AddComponent<ReflectionProbe>();
        reflection.transform.SetParent(lights.transform);
        reflection.transform.position = new Vector3(0f, 1.3f, 2f);
        reflection.mode = ReflectionProbeMode.Baked;
        reflection.boxProjection = true;
        reflection.size = new Vector3(RoomX.y - RoomX.x, RoomHeight, RoomZ.y - RoomZ.x);
        reflection.center = new Vector3(0f, RoomHeight / 2f - 1.3f, 0f);
        reflection.resolution = 256;

        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.32f, 0.33f, 0.35f);
        RenderSettings.ambientEquatorColor = new Color(0.26f, 0.26f, 0.27f);
        RenderSettings.ambientGroundColor = new Color(0.18f, 0.18f, 0.18f);
        RenderSettings.skybox = null;
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;

        Lightmapping.lightingSettings = LightmapSettingsAsset();
    }

    static LightingSettings LightmapSettingsAsset()
    {
        var settings = AssetDatabase.LoadAssetAtPath<LightingSettings>(LightingSettingsPath);
        if (settings == null)
        {
            settings = new LightingSettings { name = "PharmacyLighting" };
            AssetDatabase.CreateAsset(settings, LightingSettingsPath);
        }
        settings.bakedGI = true;
        settings.realtimeGI = false;
        settings.mixedBakeMode = MixedLightingMode.IndirectOnly;
        settings.lightmapper = LightingSettings.Lightmapper.ProgressiveGPU;
        settings.lightmapResolution = 16f;   // texels per metre - plenty for a room this size
        settings.lightmapPadding = 4;
        settings.lightmapMaxSize = 2048;
        settings.directionalityMode = LightmapsMode.NonDirectional; // cheapest to sample on Quest
        settings.maxBounces = 3;
        settings.directSampleCount = 32;
        settings.indirectSampleCount = 256;
        settings.environmentSampleCount = 128;
        settings.filteringMode = LightingSettings.FilterMode.Auto;
        settings.lightmapCompression = LightmapCompression.NormalQuality;
        settings.ao = true;
        settings.aoMaxDistance = 0.6f;
        settings.aoExponentDirect = 0f;
        settings.aoExponentIndirect = 1f;
        EditorUtility.SetDirty(settings);
        return settings;
    }

    static Dictionary<string, Material> CreateMaterials()
    {
        Directory.CreateDirectory(MaterialDir);
        AssetDatabase.Refresh();

        return new Dictionary<string, Material>
        {
            ["Env_Floor"] = Lit("Env_Floor", new Color(1f, 0.98f, 0.95f), 0.55f, "interior_tiles_diff.jpg", "interior_tiles_nor.jpg"),
            ["Env_Wall"] = Lit("Env_Wall", new Color(1f, 1f, 0.98f), 0.1f, "painted_plaster_wall_diff.jpg", "painted_plaster_wall_nor.jpg"),
            ["Env_WallGreen"] = Lit("Env_WallGreen", new Color(0f, 0.36f, 0.28f), 0.2f, null, "painted_plaster_wall_nor.jpg"),
            ["Env_Ceiling"] = Lit("Env_Ceiling", new Color(0.96f, 0.96f, 0.95f), 0.05f),
            ["Env_GlossWhite"] = Lit("Env_GlossWhite", new Color(0.95f, 0.95f, 0.95f), 0.8f),
            ["Env_Melamine"] = Lit("Env_Melamine", new Color(0.93f, 0.93f, 0.91f), 0.35f),
            ["Env_Plinth"] = Lit("Env_Plinth", new Color(0.12f, 0.12f, 0.12f), 0.3f),
            ["Env_Oak"] = Lit("Env_Oak", new Color(1f, 0.95f, 0.88f), 0.45f, "oak_veneer_01_diff.jpg", "oak_veneer_01_nor.jpg"),
            ["Env_Accent"] = Lit("Env_Accent", new Color(0f, 0.55f, 0.4f), 0.7f),
            ["Env_Metal"] = Lit("Env_Metal", new Color(0.72f, 0.73f, 0.74f), 0.6f, metallic: 0.8f),
            ["Env_BlackPlastic"] = Lit("Env_BlackPlastic", new Color(0.03f, 0.03f, 0.03f), 0.5f),
            ["Env_Screen"] = Lit("Env_Screen", new Color(0.03f, 0.08f, 0.12f), 0.9f, emission: new Color(0.05f, 0.2f, 0.35f)),
            ["Env_Acrylic"] = Lit("Env_Acrylic", new Color(0.88f, 0.92f, 0.94f), 0.95f),
            ["Env_LightPanel"] = Lit("Env_LightPanel", Color.white, 0.2f, emission: new Color(2.2f, 2.15f, 2.05f)),
            ["Env_DoorFrame"] = Lit("Env_DoorFrame", new Color(0.25f, 0.26f, 0.27f), 0.5f, metallic: 0.6f),
            ["Env_DoorGlass"] = Lit("Env_DoorGlass", new Color(0.3f, 0.38f, 0.42f), 0.95f),
            ["Env_Products"] = Lit("Env_Products", Color.white, 0.35f, "medicine_atlas.png"),
            ["Env_Category"] = Lit("Env_Category", Color.white, 0.3f, "category_atlas.png"),
            ["Env_Sign"] = Lit("Env_Sign", Color.white, 0.6f, "pharmacy_sign.png",
                emission: new Color(1.3f, 1.3f, 1.3f), emissionFromBaseMap: true),
        };
    }

    static Material Lit(string name, Color color, float smoothness, string baseMap = null, string normalMap = null,
        Color? emission = null, float metallic = 0f, bool emissionFromBaseMap = false)
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
        mat.SetFloat("_Metallic", metallic);
        if (baseMap != null)
            mat.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TextureDir}/{baseMap}"));
        if (normalMap != null)
        {
            mat.SetTexture("_BumpMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"{TextureDir}/{normalMap}"));
            mat.SetFloat("_BumpScale", 0.6f);
            mat.EnableKeyword("_NORMALMAP");
        }
        if (emission.HasValue)
        {
            mat.EnableKeyword("_EMISSION");
            mat.SetColor("_EmissionColor", emission.Value);
            if (emissionFromBaseMap)
                mat.SetTexture("_EmissionMap", mat.GetTexture("_BaseMap"));
            // Emissive panels and the sign contribute light to the bake.
            mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.BakedEmissive;
        }
        EditorUtility.SetDirty(mat);
        return mat;
    }

    /// <summary>
    /// The import postprocessor (OtcAssetImportSettings) only applies on import, so force a reimport of
    /// the generated assets - textures imported before it existed would otherwise keep old settings.
    /// </summary>
    static void ReimportGeneratedAssets()
    {
        foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { TextureDir }))
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            var importer = AssetImporter.GetAtPath(path) as TextureImporter;
            bool isNormal = path.Contains("_nor.");
            if (importer != null && isNormal && importer.textureType != TextureImporterType.NormalMap)
                AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
        }
        if (AssetImporter.GetAtPath(ModelPath) is ModelImporter model && !model.generateSecondaryUV)
            AssetDatabase.ImportAsset(ModelPath, ImportAssetOptions.ForceUpdate);
    }
}
