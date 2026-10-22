using UnityEditor;
using UnityEditor.Build;

/// <summary>
/// Player settings the Quest build needs, applied whenever the Editor loads scripts:
/// - its own app identifier and display name (instead of the URP template's),
/// - plain-HTTP allowed, so a headset build can reach the local test backend through the USB cable
///   (adb reverse) while the VR backend changes aren't deployed yet. Production traffic is HTTPS.
/// </summary>
[InitializeOnLoad]
static class OtcPlayerSettings
{
    const string AppId = "com.otcresearch.vrpepper";
    const string AppName = "OTC VR Pharmacy";

    static OtcPlayerSettings()
    {
        EditorApplication.delayCall += Apply;
    }

    static void Apply()
    {
        bool changed = false;
        if (PlayerSettings.GetApplicationIdentifier(NamedBuildTarget.Android) != AppId)
        {
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, AppId);
            changed = true;
        }
        if (PlayerSettings.productName != AppName)
        {
            PlayerSettings.productName = AppName;
            changed = true;
        }
        if (PlayerSettings.insecureHttpOption != InsecureHttpOption.AlwaysAllowed)
        {
            PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
            changed = true;
        }
        if (changed)
        {
            AssetDatabase.SaveAssets();
            UnityEngine.Debug.Log($"[OTC] Player settings applied: {AppId}, \"{AppName}\", HTTP allowed for the local test backend");
        }
    }
}
