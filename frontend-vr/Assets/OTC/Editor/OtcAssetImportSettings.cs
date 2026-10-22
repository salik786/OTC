using UnityEditor;

/// <summary>
/// Import settings for the generated OTC assets, applied automatically whenever they are (re)imported:
/// lightmap UVs for the pharmacy model, normal-map flags for *_nor textures, and mobile-friendly
/// texture sizes for Quest 2.
/// </summary>
public class OtcAssetImportSettings : AssetPostprocessor
{
    const string EnvironmentDir = "Assets/OTC/Environment/";
    const string PepperDir = "Assets/OTC/Pepper/";

    void OnPreprocessModel()
    {
        if (!assetPath.StartsWith(EnvironmentDir) && !assetPath.StartsWith(PepperDir))
            return;

        var importer = (ModelImporter)assetImporter;
        importer.importCameras = false;
        importer.importLights = false;
        importer.importAnimation = false;
        importer.importNormals = ModelImporterNormals.Import;
        importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;

        // Baked lighting needs non-overlapping lightmap UVs; Pepper is lit by light probes instead.
        importer.generateSecondaryUV = assetPath.StartsWith(EnvironmentDir);
    }

    void OnPreprocessTexture()
    {
        if (!assetPath.StartsWith(EnvironmentDir) && !assetPath.StartsWith(PepperDir))
            return;

        var importer = (TextureImporter)assetImporter;
        if (assetPath.Contains("_nor."))
            importer.textureType = TextureImporterType.NormalMap;

        importer.maxTextureSize = assetPath.Contains("atlas") || assetPath.Contains("sign") ? 2048 : 1024;
        importer.mipmapEnabled = true;
        importer.anisoLevel = 4;
    }
}
