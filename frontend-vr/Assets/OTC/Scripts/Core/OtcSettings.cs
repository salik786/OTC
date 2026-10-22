using System;
using UnityEngine;

namespace Otc.VR
{
    public enum CaptionSize { Small, Medium, Large }

    public readonly struct LanguageOption
    {
        public readonly string Label;          // shown on buttons (Latin script, renders with the default font)
        public readonly string BackendName;    // sent to the backend as response_language; null = English default
        public readonly bool CaptionsSupported; // false where the default font can't render the script

        public LanguageOption(string label, string backendName, bool captionsSupported)
        {
            Label = label;
            BackendName = backendName;
            CaptionsSupported = captionsSupported;
        }
    }

    /// <summary>
    /// Backend location, study mode, and the participant-facing accessibility settings (persisted in
    /// PlayerPrefs so they survive between sessions on the same headset).
    /// </summary>
    public class OtcSettings : MonoBehaviour
    {
        public static OtcSettings Instance { get; private set; }

        [Header("Backend")]
        public string productionUrl = "https://otc-h81d.onrender.com";
        [Tooltip("Run the backend locally (uvicorn on port 8000) and tick this to test unreleased backend changes in the Editor.")]
        public string localUrl = "http://127.0.0.1:8000";
        public bool useLocalBackendInEditor;
        [Tooltip("Headset builds use the local backend through the USB cable (adb reverse tcp:8001 tcp:8001). " +
                 "Turn off once the VR backend changes are deployed to Render.")]
        public bool useLocalBackendOnDevice = true;

        [Header("Study")]
        [Tooltip("Research parity: English only, no extra spoken safety prompts, no product switching - " +
                 "so the VR condition matches the tablet and Pepper conditions. Visual safety panels still show.")]
        public bool studyParityMode;

        public string BaseUrl =>
            (Application.isEditor ? useLocalBackendInEditor : useLocalBackendOnDevice) ? localUrl.TrimEnd('/') : productionUrl.TrimEnd('/');

        // TextMeshPro's default font covers Latin, Greek and Vietnamese. Arabic, Hindi and Chinese need
        // extra fonts (and RTL shaping for Arabic) before captions can be shown; speech works already.
        public static readonly LanguageOption[] Languages =
        {
            new LanguageOption("English", null, true),
            new LanguageOption("Tieng Viet (Vietnamese)", "Vietnamese", true),
            new LanguageOption("Ellinika (Greek)", "Greek", true),
            new LanguageOption("Espanol (Spanish)", "Spanish", true),
            new LanguageOption("Arabic", "Arabic", false),
            new LanguageOption("Mandarin Chinese", "Mandarin Chinese", false),
            new LanguageOption("Hindi", "Hindi", false),
        };

        public event Action Changed;

        int _languageIndex;
        public LanguageOption Language => Languages[studyParityMode ? 0 : _languageIndex];
        public bool SlowSpeech { get; private set; }
        public CaptionSize CaptionSize { get; private set; } = CaptionSize.Medium;
        public bool Seated { get; private set; } = true;
        public bool TutorialSeen { get; private set; }

        void Awake()
        {
            Instance = this;
            _languageIndex = Mathf.Clamp(PlayerPrefs.GetInt("otc.language", 0), 0, Languages.Length - 1);
            SlowSpeech = PlayerPrefs.GetInt("otc.slow", 0) == 1;
            CaptionSize = (CaptionSize)Mathf.Clamp(PlayerPrefs.GetInt("otc.captions", 1), 0, 2);
            Seated = PlayerPrefs.GetInt("otc.seated", 1) == 1;
            TutorialSeen = PlayerPrefs.GetInt("otc.tutorial", 0) == 1;
        }

        public void CycleLanguage()
        {
            if (studyParityMode) return;
            _languageIndex = (_languageIndex + 1) % Languages.Length;
            Save();
        }

        public void ToggleSlowSpeech() { SlowSpeech = !SlowSpeech; Save(); }
        public void CycleCaptionSize() { CaptionSize = (CaptionSize)(((int)CaptionSize + 1) % 3); Save(); }
        public void ToggleSeated() { Seated = !Seated; Save(); }
        public void MarkTutorialSeen() { TutorialSeen = true; Save(); }

        void Save()
        {
            PlayerPrefs.SetInt("otc.language", _languageIndex);
            PlayerPrefs.SetInt("otc.slow", SlowSpeech ? 1 : 0);
            PlayerPrefs.SetInt("otc.captions", (int)CaptionSize);
            PlayerPrefs.SetInt("otc.seated", Seated ? 1 : 0);
            PlayerPrefs.SetInt("otc.tutorial", TutorialSeen ? 1 : 0);
            PlayerPrefs.Save();
            Changed?.Invoke();
        }
    }
}
