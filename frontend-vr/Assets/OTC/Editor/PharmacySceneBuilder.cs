using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// Builds the first-pass pharmacy scene from primitives: room, counter, shelves of medicine boxes,
/// a life-size Pepper placeholder, lighting, and Meta's OVRCameraRig. Generated in code (rather
/// than hand-placed in the Editor) so the layout is reproducible and can be tweaked from scripts.
///
/// Layout (metres): the participant sits at the origin facing +Z. Pepper stands 1.5 m in front,
/// the counter is behind Pepper, and the shelves line the back wall.
/// </summary>
public static class PharmacySceneBuilder
{
    const string ScenePath = "Assets/OTC/Scenes/Pharmacy.unity";
    const string MaterialDir = "Assets/OTC/Materials";
    const string CameraRigPrefab = "Packages/com.meta.xr.sdk.core/Prefabs/OVRCameraRig.prefab";

    // Seated eye height. The rig uses eye-level tracking, so every participant sees Pepper from
    // the same height regardless of how tall they are - keeps the condition consistent.
    const float SeatedEyeHeight = 1.2f;

    // Real Pepper is 1.2 m tall.
    static readonly Vector3 PepperPosition = new Vector3(0f, 0f, 1.5f);

    const string SimulatorActivateMenu = "Window/Meta/Meta XR Simulator/Activate";

    /// <summary>
    /// One-click test on the laptop: builds the scene if it doesn't exist yet, opens it, switches
    /// Play mode to the Meta XR Simulator, and enters Play mode.
    /// </summary>
    [MenuItem("OTC/Play in Simulator", false, 0)]
    public static void PlayInSimulator()
    {
        if (!File.Exists(ScenePath))
            Build(confirmOverwrite: false);
        if (!File.Exists(ScenePath))
            return;

        if (SceneManagerActivePath() != ScenePath)
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                return;
            EditorSceneManager.OpenScene(ScenePath);
        }

        // Returns false when the item is disabled, i.e. the simulator is already active.
        EditorApplication.ExecuteMenuItem(SimulatorActivateMenu);

        // Entering Play mode would cancel a lighting bake in progress - wait for it instead.
        if (Lightmapping.isRunning)
        {
            _playAfterBake = true;
            Debug.Log("[OTC] Waiting for the lighting bake to finish before entering Play mode...");
            return;
        }
        EditorApplication.EnterPlaymode();
    }

    static string SceneManagerActivePath() => EditorSceneManager.GetActiveScene().path;

    [MenuItem("OTC/Build Pharmacy Scene", false, 1)]
    public static void BuildFromMenu() => Build(confirmOverwrite: true);

    public static void Build(bool confirmOverwrite)
    {
        if (confirmOverwrite && File.Exists(ScenePath) &&
            !EditorUtility.DisplayDialog("Rebuild Pharmacy scene?",
                $"{ScenePath} already exists and will be replaced.", "Rebuild", "Cancel"))
            return;

        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
            return;

        // Captions and panels need TextMeshPro's resources; import them first (one-time) and resume.
        if (!OtcRuntimeSetup.EnsureTextMeshPro(() => Build(confirmOverwrite: false)))
            return;

        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
        Directory.CreateDirectory(MaterialDir);
        AssetDatabase.Refresh(); // AssetDatabase.CreateAsset needs the new folders imported first

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // Blender-built pharmacy with baked lighting if it has been imported, otherwise the greybox.
        bool detailed = PharmacyEnvironment.Available && PharmacyEnvironment.Place() != null;
        if (!detailed)
        {
            BuildRoom();
            BuildCounter();
            BuildShelves();
        }

        // Official Pepper model if it has been imported, otherwise the primitive stand-in.
        GameObject pepper = PepperModel.Available
            ? PepperModel.Place(PepperPosition, new Vector3(0f, SeatedEyeHeight, 0f))
            : null;
        if (pepper == null)
            BuildPepperPlaceholder();

        if (detailed)
            PharmacyEnvironment.BuildLighting();
        else
            BuildLighting();
        var rig = BuildCameraRig();
        if (rig != null)
            OtcRuntimeSetup.Build(pepper, rig);

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();

        if (detailed)
        {
            // Baking runs in the background (progress bar, bottom-right of the Editor); the lightmaps
            // are saved alongside the scene when it finishes.
            Lightmapping.bakeCompleted -= OnBakeCompleted;
            Lightmapping.bakeCompleted += OnBakeCompleted;
            Lightmapping.BakeAsync();
            Debug.Log("[OTC] Pharmacy scene built - baking lighting (this takes a few minutes)...");
        }
        else
        {
            Debug.Log($"[OTC] Pharmacy scene built and saved to {ScenePath}");
        }
    }

    static bool _playAfterBake;

    static void OnBakeCompleted()
    {
        Lightmapping.bakeCompleted -= OnBakeCompleted;
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene());
        Debug.Log($"[OTC] Lighting baked and saved to {ScenePath}");
        if (_playAfterBake)
        {
            _playAfterBake = false;
            EditorApplication.EnterPlaymode();
        }
    }

    static void BuildRoom()
    {
        var root = new GameObject("Room");
        var floor = Mat("Floor", new Color(0.78f, 0.80f, 0.82f));
        var wall = Mat("Wall", new Color(0.93f, 0.95f, 0.96f));
        var accent = Mat("WallAccent", new Color(0.16f, 0.55f, 0.47f)); // pharmacy green

        // Room spans x -4..4, z -2..6, 3.2 m high.
        Box("Floor", root, new Vector3(0f, -0.05f, 2f), new Vector3(8f, 0.1f, 8f), floor);
        Box("Ceiling", root, new Vector3(0f, 3.25f, 2f), new Vector3(8f, 0.1f, 8f), wall);
        Box("BackWall", root, new Vector3(0f, 1.6f, 6.05f), new Vector3(8f, 3.2f, 0.1f), wall);
        Box("FrontWall", root, new Vector3(0f, 1.6f, -2.05f), new Vector3(8f, 3.2f, 0.1f), wall);
        Box("LeftWall", root, new Vector3(-4.05f, 1.6f, 2f), new Vector3(0.1f, 3.2f, 8f), wall);
        Box("RightWall", root, new Vector3(4.05f, 1.6f, 2f), new Vector3(0.1f, 3.2f, 8f), wall);
        Box("BackWallStripe", root, new Vector3(0f, 2.55f, 5.99f), new Vector3(8f, 0.3f, 0.02f), accent);

        MarkStatic(root);
    }

    static void BuildCounter()
    {
        var root = new GameObject("Counter");
        var body = Mat("CounterBody", new Color(0.95f, 0.95f, 0.95f));
        var top = Mat("CounterTop", new Color(0.35f, 0.27f, 0.20f));

        Box("Body", root, new Vector3(0f, 0.475f, 3.2f), new Vector3(2.6f, 0.95f, 0.6f), body);
        Box("Top", root, new Vector3(0f, 0.97f, 3.2f), new Vector3(2.7f, 0.04f, 0.7f), top);

        MarkStatic(root);
    }

    static void BuildShelves()
    {
        var root = new GameObject("Shelves");
        var wood = Mat("Shelf", new Color(0.55f, 0.42f, 0.30f));
        Color[] boxColors =
        {
            new Color(0.85f, 0.25f, 0.25f), new Color(0.20f, 0.45f, 0.80f),
            new Color(0.95f, 0.75f, 0.20f), new Color(0.30f, 0.65f, 0.40f),
            new Color(0.95f, 0.95f, 0.95f), new Color(0.60f, 0.35f, 0.70f),
        };
        var boxMats = new Material[boxColors.Length];
        for (int i = 0; i < boxColors.Length; i++)
            boxMats[i] = Mat($"MedicineBox{i}", boxColors[i]);

        float[] shelfHeights = { 0.5f, 1.0f, 1.5f, 2.0f };
        const float shelfZ = 5.8f, shelfWidth = 3.4f;

        for (int s = 0; s < shelfHeights.Length; s++)
        {
            float y = shelfHeights[s];
            Box($"Shelf{s}", root, new Vector3(0f, y, shelfZ), new Vector3(shelfWidth, 0.03f, 0.4f), wood);

            // A row of medicine boxes standing on each shelf.
            for (int b = 0; b < 12; b++)
            {
                float x = -shelfWidth / 2f + 0.2f + b * 0.27f;
                var size = new Vector3(0.16f, 0.2f + (b % 3) * 0.03f, 0.08f);
                Box($"Box{s}_{b}", root, new Vector3(x, y + 0.015f + size.y / 2f, shelfZ - 0.05f), size,
                    boxMats[(s * 5 + b) % boxMats.Length]);
            }
        }

        MarkStatic(root);
    }

    /// <summary>
    /// Rough, correctly-scaled stand-in for Pepper until the real 3D model is imported. Built facing
    /// -Z so it looks at the participant.
    /// </summary>
    static void BuildPepperPlaceholder()
    {
        var root = new GameObject("Pepper (placeholder)");
        root.transform.position = PepperPosition;

        var white = Mat("PepperWhite", new Color(0.96f, 0.96f, 0.96f));
        var dark = Mat("PepperTablet", new Color(0.08f, 0.08f, 0.10f));
        var eyes = Mat("PepperEyes", new Color(0.15f, 0.55f, 1f), emission: new Color(0.1f, 0.5f, 1.4f));

        Part(PrimitiveType.Cylinder, "Base", root, new Vector3(0f, 0.175f, 0f), new Vector3(0.48f, 0.175f, 0.48f), white);
        Part(PrimitiveType.Cylinder, "Hips", root, new Vector3(0f, 0.5f, 0f), new Vector3(0.3f, 0.15f, 0.3f), white);
        Part(PrimitiveType.Cylinder, "Torso", root, new Vector3(0f, 0.8f, 0f), new Vector3(0.38f, 0.175f, 0.32f), white);
        Part(PrimitiveType.Cube, "Tablet", root, new Vector3(0f, 0.8f, -0.165f), new Vector3(0.25f, 0.17f, 0.02f), dark);
        Part(PrimitiveType.Sphere, "Head", root, new Vector3(0f, 1.07f, 0f), Vector3.one * 0.26f, white);
        Part(PrimitiveType.Sphere, "EyeLeft", root, new Vector3(-0.055f, 1.09f, -0.115f), Vector3.one * 0.05f, eyes);
        Part(PrimitiveType.Sphere, "EyeRight", root, new Vector3(0.055f, 1.09f, -0.115f), Vector3.one * 0.05f, eyes);

        var armL = Part(PrimitiveType.Capsule, "ArmLeft", root, new Vector3(-0.24f, 0.72f, 0f), new Vector3(0.08f, 0.22f, 0.08f), white);
        var armR = Part(PrimitiveType.Capsule, "ArmRight", root, new Vector3(0.24f, 0.72f, 0f), new Vector3(0.08f, 0.22f, 0.08f), white);
        armL.transform.localRotation = Quaternion.Euler(0f, 0f, -8f);
        armR.transform.localRotation = Quaternion.Euler(0f, 0f, 8f);
    }

    static void BuildLighting()
    {
        // One unshadowed directional light plus flat ambient - cheap enough for Quest 2's mobile GPU.
        var lightGo = new GameObject("Directional Light");
        var light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.1f;
        light.color = new Color(1f, 0.97f, 0.92f);
        light.shadows = LightShadows.None;
        lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(0.75f, 0.78f, 0.82f);
        RenderSettings.ambientEquatorColor = new Color(0.55f, 0.57f, 0.60f);
        RenderSettings.ambientGroundColor = new Color(0.35f, 0.35f, 0.36f);
        RenderSettings.skybox = null;
    }

    static GameObject BuildCameraRig()
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(CameraRigPrefab);
        if (prefab == null)
        {
            Debug.LogError($"[OTC] Could not find {CameraRigPrefab} - is com.meta.xr.sdk.core installed?");
            return null;
        }

        var rig = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        rig.transform.position = new Vector3(0f, SeatedEyeHeight, 0f);
        rig.transform.rotation = Quaternion.identity; // facing +Z, toward Pepper
        return rig;
    }

    // --- helpers -------------------------------------------------------------------------------

    static GameObject Box(string name, GameObject parent, Vector3 position, Vector3 size, Material mat) =>
        Part(PrimitiveType.Cube, name, parent, position, size, mat, worldSpace: true);

    static GameObject Part(PrimitiveType type, string name, GameObject parent, Vector3 position, Vector3 scale,
        Material mat, bool worldSpace = false)
    {
        var go = GameObject.CreatePrimitive(type);
        go.name = name;
        go.transform.SetParent(parent.transform, worldSpace);
        if (worldSpace) go.transform.position = position;
        else go.transform.localPosition = position;
        go.transform.localScale = scale;

        var renderer = go.GetComponent<MeshRenderer>();
        renderer.sharedMaterial = mat;
        renderer.shadowCastingMode = ShadowCastingMode.Off;
        renderer.receiveShadows = false;
        return go;
    }

    /// <summary>Creates (or updates) a URP Lit material asset so rebuilds reuse the same files.</summary>
    static Material Mat(string name, Color color, Color? emission = null)
    {
        string path = $"{MaterialDir}/{name}.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (mat == null)
        {
            mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
            AssetDatabase.CreateAsset(mat, path);
        }

        mat.SetColor("_BaseColor", color);
        mat.SetFloat("_Smoothness", 0.2f);
        if (emission.HasValue)
        {
            mat.EnableKeyword("_EMISSION");
            mat.SetColor("_EmissionColor", emission.Value);
            mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
        }
        EditorUtility.SetDirty(mat);
        return mat;
    }

    static void MarkStatic(GameObject root)
    {
        foreach (var t in root.GetComponentsInChildren<Transform>())
            GameObjectUtility.SetStaticEditorFlags(t.gameObject, StaticEditorFlags.BatchingStatic);
    }
}
