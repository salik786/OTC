using System.IO;
using Otc.VR;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Adds the interactive layer to the pharmacy scene: tracked hands and controller models on the camera
/// rig, hand interactors, Pepper's behaviour and voice, the product tray, and the OtcExperience that
/// runs the consultation. Called by PharmacySceneBuilder.
/// </summary>
public static class OtcRuntimeSetup
{
    const string UiMaterialDir = "Assets/OTC/Materials/UI";
    const string HandPrefab = "Packages/com.meta.xr.sdk.core/Prefabs/OVRHandPrefab.prefab";
    const string ControllerPrefab = "Packages/com.meta.xr.sdk.core/Prefabs/OVRRuntimeControllerPrefab.prefab";
    const string TmpSettingsPath = "Assets/TextMesh Pro/Resources/TMP Settings.asset";

    /// <summary>
    /// TextMeshPro needs its essential resources (default font, settings) in the project. Returns true if
    /// they're present; otherwise starts importing them and calls <paramref name="onImported"/> when done.
    /// </summary>
    public static bool EnsureTextMeshPro(System.Action onImported)
    {
        if (File.Exists(TmpSettingsPath)) return true;

        var ugui = UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/com.unity.ugui");
        string package = ugui != null
            ? Path.Combine(ugui.resolvedPath, "Package Resources", "TMP Essential Resources.unitypackage")
            : null;
        if (package == null || !File.Exists(package))
        {
            Debug.LogError("[OTC] Couldn't find TMP Essential Resources - import them via Window > TextMeshPro.");
            return true; // continue anyway; text just won't render until imported
        }

        void Done(string _)
        {
            AssetDatabase.importPackageCompleted -= Done;
            EditorApplication.delayCall += () => onImported();
        }
        AssetDatabase.importPackageCompleted += Done;
        Debug.Log("[OTC] Importing TextMeshPro essential resources (one-time)...");
        AssetDatabase.ImportPackage(package, false);
        return false;
    }

    public static void Build(GameObject pepper, GameObject rig)
    {
        Directory.CreateDirectory(UiMaterialDir);
        AssetDatabase.Refresh();

        var settingsGo = new GameObject("OTC Experience");
        var settings = settingsGo.AddComponent<OtcSettings>();
        // The VR additions to the backend (vr_quest platform, reply language, sources, slow speech) aren't
        // deployed to Render yet, so Editor testing uses a local backend:
        //   cd backend && ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
        // Untick "Use Local Backend In Editor" on this object once the backend changes are live.
        settings.localUrl = "http://127.0.0.1:8001";
        settings.useLocalBackendInEditor = true;
        var mic = settingsGo.AddComponent<MicRecorder>();
        var speech = settingsGo.AddComponent<SpeechPlayer>();
        var experience = settingsGo.AddComponent<OtcExperience>();

        // Pepper's voice comes from its head.
        Transform head = Find(pepper != null ? pepper.transform : null, "HeadPitch");
        var voiceGo = new GameObject("Pepper Voice");
        voiceGo.transform.SetParent(head != null ? head : settingsGo.transform, false);
        voiceGo.transform.localPosition = Vector3.zero;
        var audio = voiceGo.AddComponent<AudioSource>();
        audio.playOnAwake = false;
        audio.spatialBlend = 0.85f;  // mostly positional, so it sounds like it comes from Pepper
        audio.minDistance = 1.5f;
        audio.maxDistance = 12f;
        audio.dopplerLevel = 0f;
        speech.source = audio;

        // Pepper behaviour.
        Transform eye = Find(rig.transform, "CenterEyeAnchor");
        if (pepper != null)
        {
            pepper.AddComponent<PepperRig>();
            var behaviour = pepper.AddComponent<PepperBehaviour>();
            behaviour.lookTarget = eye;
            behaviour.speech = speech;
            behaviour.mic = mic;
            experience.pepper = behaviour;
        }

        // Product tray.
        var trayGo = new GameObject("Product Tray");
        trayGo.transform.SetParent(settingsGo.transform, false);
        var tray = trayGo.AddComponent<ProductTray>();
        tray.boxMaterial = AssetDatabase.LoadAssetAtPath<Material>("Assets/OTC/Environment/Materials/Env_Products.mat");
        tray.tableMaterial = AssetDatabase.LoadAssetAtPath<Material>("Assets/OTC/Environment/Materials/Env_GlossWhite.mat");
        tray.legMaterial = AssetDatabase.LoadAssetAtPath<Material>("Assets/OTC/Environment/Materials/Env_Metal.mat");

        // UI materials (assets, so the Unlit shader is included in Quest builds).
        var panelMat = Unlit("UI_Panel", new Color(0.06f, 0.09f, 0.1f));
        var buttonMat = Unlit("UI_Button", new Color(0.16f, 0.45f, 0.38f));
        var rayMat = Unlit("UI_Ray", new Color(0.55f, 0.9f, 1f));

        experience.settings = settings;
        experience.speech = speech;
        experience.mic = mic;
        experience.tray = tray;
        experience.cameraRig = rig.transform;
        experience.panelMaterial = panelMat;
        experience.buttonMaterial = buttonMat;

        // Hands, controllers and interactors.
        var leftHand = AddHandAndController(rig, settingsGo, rayMat, left: true);
        var rightHand = AddHandAndController(rig, settingsGo, rayMat, left: false);

        // Look-to-select (hands-free, and mouse-look clicking in the simulator).
        var gaze = settingsGo.AddComponent<GazeSelector>();
        gaze.head = eye;
        gaze.material = rayMat;
        gaze.hands = new[] { leftHand, rightHand };
    }

    static OVRHand AddHandAndController(GameObject rig, GameObject parent, Material rayMat, bool left)
    {
        string side = left ? "Left" : "Right";
        Transform handAnchor = Find(rig.transform, side + "HandAnchor");
        Transform controllerAnchor = Find(rig.transform, side + "ControllerAnchor");

        OVRHand hand = null;
        var handPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(HandPrefab);
        if (handPrefab != null && handAnchor != null)
        {
            var handGo = (GameObject)PrefabUtility.InstantiatePrefab(handPrefab, handAnchor);
            handGo.name = side + " Hand";
            // OpenXR hand skeleton/mesh types (OVRPlugin XRHandLeft = 4, XRHandRight = 5).
            SetInt(handGo.GetComponent<OVRHand>(), "HandType", left ? 0 : 1);
            SetInt(handGo.GetComponent<OVRSkeleton>(), "_skeletonType", left ? 4 : 5);
            SetInt(handGo.GetComponent<OVRMesh>(), "_meshType", left ? 4 : 5);
            hand = handGo.GetComponent<OVRHand>();
        }

        var controllerPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(ControllerPrefab);
        if (controllerPrefab != null && controllerAnchor != null)
        {
            var controllerGo = (GameObject)PrefabUtility.InstantiatePrefab(controllerPrefab, controllerAnchor);
            controllerGo.name = side + " Controller";
            var runtime = controllerGo.GetComponent<OVRRuntimeController>();
            if (runtime != null) runtime.m_controller = left ? OVRInput.Controller.LTouch : OVRInput.Controller.RTouch;
        }

        var interactorGo = new GameObject(side + " Interactor");
        interactorGo.transform.SetParent(parent.transform, false);
        var interactor = interactorGo.AddComponent<HandInteractor>();
        interactor.controller = left ? OVRInput.Controller.LTouch : OVRInput.Controller.RTouch;
        interactor.controllerAnchor = controllerAnchor;
        interactor.hand = hand;

        var line = interactorGo.AddComponent<LineRenderer>();
        line.sharedMaterial = rayMat;
        line.widthMultiplier = 0.004f;
        line.numCapVertices = 2;
        line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        line.receiveShadows = false;
        interactor.ray = line;
        return hand;
    }

    static void SetInt(Object target, string property, int value)
    {
        if (target == null) return;
        var so = new SerializedObject(target);
        var prop = so.FindProperty(property);
        if (prop == null)
        {
            Debug.LogWarning($"[OTC] {target.GetType().Name}.{property} not found - hand may need manual setup");
            return;
        }
        prop.intValue = value;
        so.ApplyModifiedPropertiesWithoutUndo();
    }

    static Material Unlit(string name, Color color)
    {
        string path = $"{UiMaterialDir}/{name}.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (mat == null)
        {
            mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            AssetDatabase.CreateAsset(mat, path);
        }
        mat.SetColor("_BaseColor", color);
        EditorUtility.SetDirty(mat);
        return mat;
    }

    static Transform Find(Transform root, string name)
    {
        if (root == null) return null;
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
            if (t.name == name) return t;
        return null;
    }
}
