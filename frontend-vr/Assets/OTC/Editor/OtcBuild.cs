using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>
/// Builds the Quest APK (Builds/OTC-VR.apk) from the open Editor.
///
/// - Menu: OTC > Build APK for Quest.
/// - Or from a terminal while the Editor is open: create Temp/otc-build-request and focus Unity; the
///   build starts on its own and writes Temp/otc-build-result.txt when done (used by Claude Code to
///   build and then install with adb, without closing the Editor).
/// </summary>
[InitializeOnLoad]
public static class OtcBuild
{
    public const string ApkPath = "Builds/OTC-VR.apk";
    const string RequestFile = "Temp/otc-build-request";
    const string ResultFile = "Temp/otc-build-result.txt";

    static double _nextCheck;
    static bool _pending;

    static OtcBuild()
    {
        EditorApplication.update += Poll;
    }

    [MenuItem("OTC/Build APK for Quest", false, 20)]
    public static void BuildFromMenu() => Build();

    static void Poll()
    {
        if (EditorApplication.timeSinceStartup < _nextCheck) return;
        _nextCheck = EditorApplication.timeSinceStartup + 1.0;

        if (!_pending && File.Exists(RequestFile))
        {
            File.Delete(RequestFile);
            _pending = true;
            if (EditorApplication.isPlaying) EditorApplication.ExitPlaymode();
        }

        // Wait until Play mode, compilation and any lighting bake are finished.
        if (_pending && !EditorApplication.isPlayingOrWillChangePlaymode && !EditorApplication.isCompiling &&
            !EditorApplication.isUpdating && !Lightmapping.isRunning)
        {
            _pending = false;
            Build();
        }
    }

    public static bool Build()
    {
        if (File.Exists(ResultFile)) File.Delete(ResultFile);
        Directory.CreateDirectory(Path.GetDirectoryName(ApkPath));

        var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        if (scenes.Length == 0)
        {
            WriteResult(false, "No scenes in the build - run OTC > Build Pharmacy Scene first.");
            return false;
        }
        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

        Debug.Log($"[OTC] Building {ApkPath} ({string.Join(", ", scenes)})...");
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = ApkPath,
            target = BuildTarget.Android,
            options = BuildOptions.None,
        });

        var summary = report.summary;
        bool ok = summary.result == BuildResult.Succeeded;
        string errors = string.Join("\n", report.steps.SelectMany(s => s.messages)
            .Where(m => m.type == LogType.Error || m.type == LogType.Exception)
            .Select(m => m.content).Take(15));
        WriteResult(ok, $"{summary.result} in {summary.totalTime:mm\\:ss}, {summary.totalSize / (1024 * 1024)} MB, " +
                        $"{summary.totalErrors} errors\n{errors}");
        Debug.Log($"[OTC] Build {summary.result}: {Path.GetFullPath(ApkPath)}");
        return ok;
    }

    static void WriteResult(bool ok, string message)
    {
        File.WriteAllText(ResultFile, $"{(ok ? "SUCCESS" : "FAILED")}\n{DateTime.Now:O}\n{message}\n");
    }
}
