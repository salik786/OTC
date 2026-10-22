using System.Collections;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// The VR consultation, mirroring the tablet/Pepper study flow (frontend-app/src/screens):
    /// setup -> (first-time tutorial) -> core info -> voice Q&amp;A -> closing.
    ///
    /// On top of that flow: captions and answer sources, pick-up-and-ask product boxes, language /
    /// caption size / speech speed / seated-standing settings, red-flag safety prompts, and a
    /// "talk to a pharmacist" option. Study parity mode turns the VR-only extras off.
    /// </summary>
    public class OtcExperience : MonoBehaviour
    {
        [Header("Scene references (wired by the Editor builder)")]
        public OtcSettings settings;
        public PepperBehaviour pepper;
        public SpeechPlayer speech;
        public MicRecorder mic;
        public ProductTray tray;
        public Transform cameraRig;   // OVRCameraRig root
        public Material panelMaterial;
        public Material buttonMaterial;

        // Layout (participant seated at the origin, facing +Z). Kept in code rather than serialized so
        // layout changes apply to already-built scenes.
        static readonly Vector3 seatEye = new Vector3(0f, 1.2f, 0f);
        static readonly Vector3 mainPanelPos = new Vector3(0f, 1.3f, 0.95f);
        static readonly Vector3 captionPos = new Vector3(0.82f, 1.33f, 1.4f);
        static readonly Vector3 leafletPos = new Vector3(-0.82f, 1.25f, 1.05f);
        static readonly Vector3 toolbarPos = new Vector3(-0.45f, 0.95f, 0.55f);
        static readonly Vector3 micPos = new Vector3(0f, 0.98f, 0.62f);
        static readonly Vector3 trayPos = new Vector3(0.5f, 0f, 0.45f);

        enum Phase { Setup, Tutorial, Consultation, Closing }

        Phase _phase;
        List<OtcApi.Product> _products = new List<OtcApi.Product>();
        OtcApi.Product _selected;
        OtcApi.Session _session;
        int _errors;
        bool _busy;              // a request (session switch / question) is in flight
        Coroutine _answer;

        Transform _main, _captions, _leaflet, _toolbar, _settingsPanel, _modal;
        TextMeshPro _captionText, _questionText, _sourceText, _statusText, _leafletText;
        VRButton _micButton, _pharmacistButton;

        // ------------------------------------------------------------------ lifecycle

        void Start()
        {
            Ui.PanelMaterial = panelMaterial;
            Ui.ButtonMaterial = buttonMaterial;

            mic.Finished += OnRecordingFinished;
            speech.SentenceStarted += OnSentenceStarted;
            speech.Finished += OnSpeechFinished;
            tray.ProductPickedUp += OnProductPickedUp;
            settings.Changed += OnSettingsChanged;

            EnsureGazeSelector();
            BuildConsultationUi();
            ApplySeatMode();
            ShowSetup();
        }

        void Update()
        {
#if ENABLE_INPUT_SYSTEM
            // Desk testing: Space = talk, Escape = settings.
            var kb = UnityEngine.InputSystem.Keyboard.current;
            if (kb != null && _phase == Phase.Consultation && kb.spaceKey.wasPressedThisFrame) OnMicPressed();
            if (kb != null && kb.escapeKey.wasPressedThisFrame) ToggleSettings();
#endif
            // Controller shortcut: A / X toggles the microphone.
            if (_phase == Phase.Consultation &&
                (OVRInput.GetDown(OVRInput.Button.One, OVRInput.Controller.RTouch) ||
                 OVRInput.GetDown(OVRInput.Button.One, OVRInput.Controller.LTouch)))
                OnMicPressed();
        }

        // ------------------------------------------------------------------ setup

        void ShowSetup()
        {
            _phase = Phase.Setup;
            SetConsultationUiVisible(false);
            ReplaceMain(Ui.Panel("Setup", transform, mainPanelPos, seatEye, new Vector2(0.95f, 0.66f)));
            Ui.Text(_main, "Welcome to the pharmacy", new Vector2(0f, 0.25f), new Vector2(0.85f, 0.08f), 0.55f);
            var status = Ui.Text(_main, "Connecting to the pharmacy assistant...", new Vector2(0f, 0.17f),
                new Vector2(0.85f, 0.06f), 0.32f, color: Ui.MutedText);

            StartCoroutine(OtcApi.ListProducts(products =>
            {
                _products = products;
                if (_phase != Phase.Setup) return;
                status.text = products.Count > 0
                    ? "Which medicine would you like to ask about?"
                    : "No medicines are set up yet - add one in the admin panel.";
                BuildSetupChoices();
            }, error =>
            {
                _errors++;
                status.text = "Couldn't reach the pharmacy assistant. Check the internet connection.";
                var retry = Ui.Button(_main, "Try again", new Vector2(0f, -0.2f), new Vector2(0.3f, 0.09f), 0.4f);
                retry.Clicked += ShowSetup;
                Debug.LogWarning($"[OTC] product list failed: {error}");
            }));
        }

        void BuildSetupChoices()
        {
            var buttons = new List<VRButton>();
            int n = _products.Count;
            for (int i = 0; i < n; i++)
            {
                var product = _products[i];
                float x = (i - (n - 1) / 2f) * 0.3f;
                var b = Ui.Button(_main, product.display_name, new Vector2(x, 0.06f), new Vector2(0.27f, 0.1f), 0.38f);
                b.Clicked += () =>
                {
                    _selected = product;
                    foreach (var other in buttons) other.Selected = other == b;
                };
                buttons.Add(b);
            }
            if (n > 0) { _selected = _products[0]; buttons[0].Selected = true; }

            if (!settings.studyParityMode)
            {
                var lang = Ui.Button(_main, LanguageLabel(), new Vector2(0f, -0.08f), new Vector2(0.6f, 0.08f), 0.32f,
                    new Color(0.2f, 0.25f, 0.28f));
                lang.Clicked += () => { settings.CycleLanguage(); lang.SetText(LanguageLabel()); };
            }

            var start = Ui.Button(_main, "Start", new Vector2(0f, -0.22f), new Vector2(0.32f, 0.1f), 0.48f);
            start.Clicked += () => { if (_selected != null && !_busy) StartCoroutine(StartConsultation()); };
        }

        IEnumerator StartConsultation()
        {
            _busy = true;
            string error = null;
            yield return OtcApi.StartSession(_selected.slug, s => _session = s, e => error = e);
            _busy = false;
            if (error != null)
            {
                _errors++;
                Debug.LogWarning($"[OTC] session start failed: {error}");
                Ui.Text(_main, "Couldn't start - please try again.", new Vector2(0f, -0.3f), new Vector2(0.8f, 0.05f),
                    0.28f, color: new Color(1f, 0.6f, 0.5f));
                yield break;
            }
            Debug.Log($"[OTC] session {_session.session_id} ({_session.condition}) for {_session.product_display_name}");

            if (!settings.TutorialSeen && !settings.studyParityMode)
                ShowTutorial(0);
            else
                BeginConsultation();
        }

        // ------------------------------------------------------------------ tutorial

        static readonly (string title, string body)[] TutorialPages =
        {
            ("Talking to Pepper",
                "Tap the green <b>Tap to talk</b> button in front of you (or press <b>A</b>), then ask your question out loud.\n\n" +
                "Pepper listens until you pause, then answers. Tap again any time to interrupt."),
            ("Looking at medicines",
                "There are medicine boxes on the small table to your right.\n\n" +
                "Reach out and <b>squeeze the grip</b> (or <b>pinch</b> with your fingers) to pick one up, then ask " +
                "<i>\"What's this for?\"</i>"),
            ("Getting help",
                "Pepper answers from the official medicine leaflet only.\n\n" +
                "For personal advice, use <b>Talk to a pharmacist</b>. The <b>Settings</b> button changes language, " +
                "caption size and speech speed."),
        };

        void ShowTutorial(int page)
        {
            _phase = Phase.Tutorial;
            ReplaceMain(Ui.Panel("Tutorial", transform, mainPanelPos, seatEye, new Vector2(0.95f, 0.66f)));
            var (title, body) = TutorialPages[page];
            Ui.Text(_main, $"{page + 1} / {TutorialPages.Length}", new Vector2(0f, 0.28f), new Vector2(0.8f, 0.04f), 0.24f, color: Ui.MutedText);
            Ui.Text(_main, title, new Vector2(0f, 0.21f), new Vector2(0.85f, 0.08f), 0.5f);
            Ui.Text(_main, body, new Vector2(0f, 0.0f), new Vector2(0.82f, 0.3f), 0.32f, TextAlignmentOptions.Top);

            bool last = page == TutorialPages.Length - 1;
            var next = Ui.Button(_main, last ? "Let's start" : "Next", new Vector2(0.15f, -0.24f), new Vector2(0.28f, 0.09f), 0.4f);
            next.Clicked += () =>
            {
                if (last) { settings.MarkTutorialSeen(); BeginConsultation(); }
                else ShowTutorial(page + 1);
            };
            var skip = Ui.Button(_main, "Skip", new Vector2(-0.15f, -0.24f), new Vector2(0.2f, 0.09f), 0.36f, new Color(0.25f, 0.28f, 0.3f));
            skip.Clicked += () => { settings.MarkTutorialSeen(); BeginConsultation(); };
        }

        // ------------------------------------------------------------------ consultation

        void BuildConsultationUi()
        {
            _captions = Ui.Panel("Captions", transform, captionPos, seatEye, new Vector2(0.8f, 0.46f));
            _questionText = Ui.Text(_captions, "", new Vector2(0f, 0.17f), new Vector2(0.74f, 0.08f), 0.26f,
                TextAlignmentOptions.TopLeft, Ui.MutedText);
            _captionText = Ui.Text(_captions, "", new Vector2(0f, 0.0f), new Vector2(0.74f, 0.25f), 0.36f, TextAlignmentOptions.TopLeft);
            _sourceText = Ui.Text(_captions, "", new Vector2(0f, -0.15f), new Vector2(0.74f, 0.05f), 0.22f,
                TextAlignmentOptions.Left, Ui.Accent);
            _statusText = Ui.Text(_captions, "", new Vector2(0f, -0.2f), new Vector2(0.74f, 0.04f), 0.22f,
                TextAlignmentOptions.Left, Ui.MutedText);

            _leaflet = Ui.Panel("Leaflet", transform, leafletPos, seatEye, new Vector2(0.55f, 0.62f), new Color(0.97f, 0.97f, 0.95f));
            _leafletText = Ui.Text(_leaflet, "", new Vector2(0f, 0f), new Vector2(0.49f, 0.56f), 0.24f,
                TextAlignmentOptions.TopLeft, new Color(0.12f, 0.12f, 0.12f));

            var micRoot = new GameObject("Mic").transform;
            micRoot.SetParent(transform, false);
            micRoot.position = micPos;
            Ui.Face(micRoot, seatEye);
            _micButton = Ui.Button(micRoot, "Tap to talk", Vector2.zero, new Vector2(0.34f, 0.14f), 0.5f, new Color(0.1f, 0.55f, 0.4f));
            _micButton.Clicked += OnMicPressed;

            _toolbar = Ui.Panel("Toolbar", transform, toolbarPos, seatEye, new Vector2(0.3f, 0.38f));
            var settingsButton = Ui.Button(_toolbar, "Settings", new Vector2(0f, 0.12f), new Vector2(0.26f, 0.09f), 0.3f, new Color(0.22f, 0.27f, 0.3f));
            settingsButton.Clicked += ToggleSettings;
            _pharmacistButton = Ui.Button(_toolbar, "Talk to a pharmacist", new Vector2(0f, 0f), new Vector2(0.26f, 0.09f), 0.24f, new Color(0.15f, 0.4f, 0.65f));
            _pharmacistButton.Clicked += ShowPharmacistHelp;
            var end = Ui.Button(_toolbar, "I'm done", new Vector2(0f, -0.12f), new Vector2(0.26f, 0.09f), 0.3f, new Color(0.45f, 0.2f, 0.2f));
            end.Clicked += () => StartCoroutine(Finish());

            tray.transform.position = trayPos;
            ApplyCaptionSize();
        }

        void SetConsultationUiVisible(bool visible)
        {
            _captions.gameObject.SetActive(visible);
            _leaflet.gameObject.SetActive(visible);
            _toolbar.gameObject.SetActive(visible);
            _micButton.transform.parent.gameObject.SetActive(visible);
            tray.gameObject.SetActive(visible);
        }

        void BeginConsultation()
        {
            _phase = Phase.Consultation;
            ReplaceMain(null);
            SetConsultationUiVisible(true);

            // Study parity: only the session's medicine is on the table; otherwise all of them.
            var onTable = settings.studyParityMode
                ? _products.Where(p => p.slug == _session.product_slug).ToList()
                : _products;
            tray.Build(onTable, seatEye);

            _captionText.text = "";
            _questionText.text = "";
            _sourceText.text = "";
            pepper.Wave();
            StartCoroutine(DeliverCoreInfo(speak: true));
        }

        /// <summary>Screen 3 of the study flow: the medicine's core facts, spoken by Pepper and shown on the leaflet card.</summary>
        IEnumerator DeliverCoreInfo(bool speak)
        {
            _busy = true;
            SetStatus("Pepper is getting the leaflet...");
            pepper.SetState(PepperState.Thinking);
            OtcApi.CoreInfo info = null;
            string error = null;
            yield return OtcApi.GetCoreInfo(_session.session_id, settings.Language.BackendName, i => info = i, e => error = e);
            _busy = false;

            if (error != null)
            {
                _errors++;
                Debug.LogWarning($"[OTC] core info failed: {error}");
                pepper.SetState(PepperState.Idle);
                SetStatus("Couldn't load the leaflet - you can still ask Pepper questions.");
                yield break;
            }

            ShowLeaflet(info);
            if (speak)
            {
                pepper.SetState(PepperState.Speaking);
                speech.Say(info.full_text);
                _sourceText.text = "Source: patient information leaflet";
            }
            else
            {
                pepper.SetState(PepperState.Idle);
                SetStatus(TapPrompt());
            }
        }

        void ShowLeaflet(OtcApi.CoreInfo info)
        {
            var lines = new List<string> { $"<b><size=140%>{info.product_name}</size></b>", "<color=#555>From the patient leaflet</color>\n" };
            void Add(string label, string value) { if (!string.IsNullOrWhiteSpace(value)) lines.Add($"<b>{label}</b>\n{value}\n"); }
            Add("Used for", info.used_for);
            Add("Dose", info.dose);
            Add("How often", info.frequency);
            Add("Maximum in 24 hours", info.max_dose_24h);
            if (info.warnings != null && info.warnings.Count > 0)
                lines.Add("<b>Warnings</b>\n" + string.Join("\n", info.warnings.Take(4).Select(w => "• " + w)));
            _leafletText.text = settings.Language.CaptionsSupported
                ? string.Join("\n", lines)
                : $"<b>{info.product_name}</b>\n\n(The leaflet card can't be shown in {settings.Language.Label} yet.)";
        }

        void OnMicPressed()
        {
            Debug.Log($"[OTC] Talk pressed (phase {_phase}, modal {_modal != null}, busy {_busy}, " +
                      $"speaking {speech.IsSpeaking}, recording {mic.IsRecording})");
            if (_phase != Phase.Consultation || _modal != null) return;

            if (mic.IsRecording)
            {
                mic.Stop(); // participant tapped again: they're done talking
                return;
            }
            if (_busy && !speech.IsSpeaking) return; // still waiting for a reply

            // Barge-in: interrupting Pepper stops its speech and starts listening.
            if (_answer != null) { StopCoroutine(_answer); _answer = null; }
            speech.Stop();
            _busy = false;

            if (!mic.Begin())
            {
                SetStatus("No microphone found - check the headset/Mac microphone permission.");
                return;
            }
            pepper.Alert = false;
            pepper.SetState(PepperState.Listening);
            _micButton.SetText("Listening...");
            _micButton.Selected = true;
            SetStatus("Listening - ask your question, then pause.");
        }

        void OnRecordingFinished(byte[] wav)
        {
            Debug.Log(wav == null ? "[OTC] Recording finished: no speech detected" : $"[OTC] Recording finished: {wav.Length} bytes");
            _micButton.SetText("Tap to talk");
            _micButton.Selected = false;
            if (wav == null)
            {
                pepper.SetState(PepperState.Idle);
                SetStatus("I didn't catch that - tap to try again.");
                return;
            }
            _answer = StartCoroutine(TranscribeAndAsk(wav));
        }

        IEnumerator TranscribeAndAsk(byte[] wav)
        {
            _busy = true;
            pepper.SetState(PepperState.Thinking);
            SetStatus("Pepper is thinking...");
            string transcript = null, error = null;
            yield return OtcApi.Transcribe(wav, t => transcript = t, e => error = e);
            if (error != null || string.IsNullOrWhiteSpace(transcript))
            {
                if (error != null) { _errors++; Debug.LogWarning($"[OTC] STT failed: {error}"); }
                _busy = false;
                pepper.SetState(PepperState.Idle);
                SetStatus(error != null ? "Connection problem - please try again." : "I didn't catch that - tap to try again.");
                yield break;
            }
            yield return Ask(transcript, "voice");
        }

        IEnumerator Ask(string question, string inputMethod)
        {
            _busy = true;
            _questionText.text = $"You: {question}";
            _captionText.text = "";
            _sourceText.text = "";

            // Safety screen first: it can add a prompt, never block the leaflet answer.
            var safety = SafetyCheck.Assess(question);
            if (safety == SafetyLevel.Emergency)
            {
                ShowSafety(SafetyCheck.EmergencyTitle, SafetyCheck.EmergencyBody, Ui.Danger);
                pepper.Alert = true;
                if (!settings.studyParityMode)
                {
                    // Urgent: Pepper gives the safety message instead of a leaflet answer.
                    pepper.SetState(PepperState.Speaking);
                    speech.Say(SafetyCheck.EmergencySpoken);
                    _busy = false;
                    _answer = null;
                    yield break;
                }
            }
            else if (safety == SafetyLevel.SeePharmacist)
            {
                ShowSafety(SafetyCheck.PharmacistTitle, SafetyCheck.PharmacistBody, new Color(0.15f, 0.35f, 0.6f));
            }

            pepper.SetState(PepperState.Thinking);
            speech.Begin();
            bool first = true;
            OtcApi.AnswerDone done = null;
            string error = null;
            yield return OtcApi.AskStream(_session.session_id, question, inputMethod, settings.Language.BackendName,
                delta =>
                {
                    if (first) { first = false; pepper.SetState(PepperState.Speaking); SetStatus(""); }
                    speech.AddText(delta);
                },
                d => done = d, e => error = e);

            _busy = false;
            _answer = null;
            if (error != null)
            {
                _errors++;
                Debug.LogWarning($"[OTC] question failed: {error}");
                speech.Stop();
                pepper.SetState(PepperState.Idle);
                SetStatus("Connection problem - please ask again.");
                yield break;
            }

            speech.EndOfText();
            if (done.in_scope)
            {
                _sourceText.text = done.sources != null && done.sources.Count > 0
                    ? "Source: leaflet - " + string.Join(", ", done.sources.Take(3))
                    : "Source: patient information leaflet";
                _pharmacistButton.Selected = false;
            }
            else
            {
                _sourceText.text = "Not covered by the leaflet - please ask a pharmacist.";
                _pharmacistButton.Selected = true; // draw attention to the human option
            }
        }

        void OnSentenceStarted(string sentence)
        {
            _captionText.text = settings.Language.CaptionsSupported
                ? sentence
                : $"(Captions aren't available in {settings.Language.Label} yet.)";
        }

        void OnSpeechFinished()
        {
            if (_phase != Phase.Consultation || mic.IsRecording) return;
            pepper.SetState(PepperState.Idle);
            SetStatus(TapPrompt());
        }

        string TapPrompt() => "Tap to talk (or press A) to ask a question.";

        // ------------------------------------------------------------------ products

        void OnProductPickedUp(OtcApi.Product product)
        {
            if (_phase != Phase.Consultation || _session == null) return;

            if (product.slug == _session.product_slug)
            {
                SetStatus($"You're holding {product.display_name}. Ask Pepper anything about it.");
                return;
            }
            if (settings.studyParityMode || _busy || mic.IsRecording) return;
            StartCoroutine(SwitchProduct(product));
        }

        /// <summary>Picking up a different medicine starts a new session for it, so questions like
        /// "what's this for?" are answered from that medicine's leaflet.</summary>
        IEnumerator SwitchProduct(OtcApi.Product product)
        {
            _busy = true;
            speech.Stop();
            pepper.SetState(PepperState.Thinking);
            SetStatus($"Switching to {product.display_name}...");

            var old = _session;
            OtcApi.Session next = null;
            string error = null;
            yield return OtcApi.StartSession(product.slug, s => next = s, e => error = e);
            if (error != null)
            {
                _errors++;
                _busy = false;
                pepper.SetState(PepperState.Idle);
                SetStatus("Couldn't switch medicine - please try again.");
                yield break;
            }
            StartCoroutine(OtcApi.EndSession(old.session_id, _errors));
            _session = next;
            _errors = 0;
            _questionText.text = "";
            _captionText.text = settings.Language.CaptionsSupported ? $"That's {product.display_name}." : "";
            _busy = false;

            yield return DeliverCoreInfo(speak: false);
            if (settings.Language.BackendName == null)
            {
                pepper.SetState(PepperState.Speaking);
                speech.Say($"That's {product.display_name}. What would you like to know about it?");
            }
        }

        // ------------------------------------------------------------------ panels: help, safety, settings

        void ShowPharmacistHelp()
        {
            ShowModal("Talk to a pharmacist",
                "Please ask a pharmacist or a member of staff - they can give advice for your personal situation.\n\n" +
                "You can show them this screen, or take off the headset and ask in person.",
                new Color(0.12f, 0.3f, 0.5f));
        }

        void ShowSafety(string title, string body, Color color) => ShowModal(title, body, color);

        void ShowModal(string title, string body, Color color)
        {
            CloseModal();
            _modal = Ui.Panel("Modal", transform, mainPanelPos + new Vector3(0f, 0f, -0.1f), seatEye, new Vector2(0.9f, 0.62f), color);
            Ui.Text(_modal, title, new Vector2(0f, 0.23f), new Vector2(0.82f, 0.08f), 0.5f);
            Ui.Text(_modal, body, new Vector2(0f, 0.0f), new Vector2(0.8f, 0.32f), 0.3f, TextAlignmentOptions.Top);
            var ok = Ui.Button(_modal, "OK", new Vector2(0f, -0.23f), new Vector2(0.24f, 0.09f), 0.42f, new Color(0.1f, 0.1f, 0.1f));
            ok.Clicked += CloseModal;
        }

        void CloseModal()
        {
            if (_modal != null) Destroy(_modal.gameObject);
            _modal = null;
            pepper.Alert = false;
        }

        void ToggleSettings()
        {
            if (_settingsPanel != null)
            {
                Destroy(_settingsPanel.gameObject);
                _settingsPanel = null;
                return;
            }
            _settingsPanel = Ui.Panel("Settings", transform, mainPanelPos + new Vector3(-0.15f, -0.02f, -0.15f), seatEye,
                new Vector2(0.62f, 0.72f));
            Ui.Text(_settingsPanel, "Settings", new Vector2(0f, 0.3f), new Vector2(0.55f, 0.07f), 0.46f);

            float y = 0.19f;
            VRButton Row(string text)
            {
                var b = Ui.Button(_settingsPanel, text, new Vector2(0f, y), new Vector2(0.54f, 0.08f), 0.28f, new Color(0.2f, 0.25f, 0.28f));
                y -= 0.095f;
                return b;
            }

            var lang = Row(LanguageLabel());
            lang.Interactable = !settings.studyParityMode;
            lang.Clicked += () => { settings.CycleLanguage(); lang.SetText(LanguageLabel()); };
            var size = Row($"Caption size: {settings.CaptionSize}");
            size.Clicked += () => { settings.CycleCaptionSize(); size.SetText($"Caption size: {settings.CaptionSize}"); };
            var speed = Row($"Speech: {(settings.SlowSpeech ? "Slower" : "Normal")}");
            speed.Clicked += () => { settings.ToggleSlowSpeech(); speed.SetText($"Speech: {(settings.SlowSpeech ? "Slower" : "Normal")}"); };
            var seat = Row($"Position: {(settings.Seated ? "Seated" : "Standing")}");
            seat.Clicked += () => { settings.ToggleSeated(); seat.SetText($"Position: {(settings.Seated ? "Seated" : "Standing")}"); };
            var recenter = Row("Recenter view");
            recenter.Clicked += () => OVRManager.display?.RecenterPose();
            var close = Ui.Button(_settingsPanel, "Close", new Vector2(0f, -0.3f), new Vector2(0.24f, 0.08f), 0.34f);
            close.Clicked += ToggleSettings;

            if (settings.studyParityMode)
                Ui.Text(_settingsPanel, "Study mode: language fixed to English", new Vector2(0f, -0.38f + 0.04f),
                    new Vector2(0.55f, 0.04f), 0.2f, color: Ui.MutedText);
        }

        string LanguageLabel()
        {
            var lang = settings.Language;
            return lang.CaptionsSupported ? $"Language: {lang.Label}" : $"Language: {lang.Label} (speech only)";
        }

        void OnSettingsChanged()
        {
            ApplyCaptionSize();
            ApplySeatMode();
        }

        void ApplyCaptionSize()
        {
            float s = Ui.FontScale(settings.CaptionSize);
            if (_captionText != null) _captionText.fontSize = 0.36f * s;
            if (_questionText != null) _questionText.fontSize = 0.26f * s;
            if (_leafletText != null) _leafletText.fontSize = 0.24f * s;
        }

        /// <summary>Seated: fixed eye height so every participant sees the scene from the same place.
        /// Standing: real floor-level tracking.</summary>
        void ApplySeatMode()
        {
            var manager = OVRManager.instance;
            if (manager != null)
                manager.trackingOriginType = settings.Seated ? OVRManager.TrackingOrigin.EyeLevel : OVRManager.TrackingOrigin.FloorLevel;
            if (cameraRig != null)
                cameraRig.position = new Vector3(cameraRig.position.x, settings.Seated ? seatEye.y : 0f, cameraRig.position.z);
        }

        // ------------------------------------------------------------------ closing

        IEnumerator Finish()
        {
            if (_phase != Phase.Consultation) yield break;
            _phase = Phase.Closing;
            if (_answer != null) StopCoroutine(_answer);
            mic.Cancel();
            speech.Stop();
            CloseModal();
            if (_settingsPanel != null) ToggleSettings();
            SetConsultationUiVisible(false);
            pepper.SetState(PepperState.Idle);
            pepper.Wave();

            if (_session != null)
            {
                yield return OtcApi.EndSession(_session.session_id, _errors);
                _session = null;
                _errors = 0;
            }

            ReplaceMain(Ui.Panel("Closing", transform, mainPanelPos, seatEye, new Vector2(0.95f, 0.6f)));
            Ui.Text(_main, "Thank you!", new Vector2(0f, 0.18f), new Vector2(0.85f, 0.1f), 0.6f);
            Ui.Text(_main, "You can take off the headset now.\nThe researcher will give you a short survey.",
                new Vector2(0f, 0.02f), new Vector2(0.85f, 0.18f), 0.34f);
            var again = Ui.Button(_main, "Start a new session", new Vector2(0f, -0.2f), new Vector2(0.42f, 0.09f), 0.34f,
                new Color(0.22f, 0.27f, 0.3f));
            again.Clicked += ShowSetup;
        }

        // ------------------------------------------------------------------ helpers

        /// <summary>Scenes built before look-to-select existed don't have it; add it at runtime.</summary>
        void EnsureGazeSelector()
        {
            if (GetComponent<GazeSelector>() != null || cameraRig == null) return;
            var gaze = gameObject.AddComponent<GazeSelector>();
            gaze.head = cameraRig.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "CenterEyeAnchor");
            gaze.material = buttonMaterial;
            gaze.hands = FindObjectsByType<OVRHand>(FindObjectsSortMode.None);
        }

        void ReplaceMain(Transform panel)
        {
            if (_main != null) Destroy(_main.gameObject);
            _main = panel;
        }

        void SetStatus(string text)
        {
            if (_statusText != null) _statusText.text = text;
        }
    }
}
