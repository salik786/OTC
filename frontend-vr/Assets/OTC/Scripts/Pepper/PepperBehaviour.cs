using UnityEngine;

namespace Otc.VR
{
    public enum PepperState { Idle, Listening, Thinking, Speaking }

    /// <summary>
    /// Makes Pepper feel present: it keeps eye contact with the participant, breathes, gestures while it
    /// talks (energy follows its voice), looks away to "think", leans in to listen, and its eye LED rings
    /// and shoulder LEDs change colour with its state - as the physical robot's LEDs do.
    /// All motion goes through PepperRig in NAOqi joint angles.
    /// </summary>
    [RequireComponent(typeof(PepperRig))]
    public class PepperBehaviour : MonoBehaviour
    {
        public Transform lookTarget;     // participant's head (CenterEyeAnchor)
        public SpeechPlayer speech;
        public MicRecorder mic;

        [Header("LED colours")]
        public Color idleColor = new Color(0.55f, 0.75f, 1f);
        public Color listeningColor = new Color(0.1f, 0.45f, 1f);
        public Color thinkingColor = new Color(0.2f, 0.9f, 0.9f);
        public Color speakingColor = new Color(0.9f, 0.95f, 1f);
        public Color alertColor = new Color(1f, 0.55f, 0.1f);
        public float ledIntensity = 2.5f;

        public PepperState State { get; private set; } = PepperState.Idle;
        public bool Alert { get; set; }

        PepperRig _rig;
        Transform _head;
        Vector3 _forward;
        float _time, _stateTime, _emphasis, _waveUntil;
        Color _ledColor;

        Renderer[] _ledRenderers;
        int[] _ledSlots;
        MaterialPropertyBlock _mpb;
        static readonly int EmissionColor = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _rig = GetComponent<PepperRig>();
            foreach (var t in GetComponentsInChildren<Transform>(true))
                if (t.name == "HeadPitch") { _head = t; break; }
            CollectLeds();
            _mpb = new MaterialPropertyBlock();
        }

        void Start()
        {
            // Pepper is placed facing the participant's seat; that direction is "straight ahead" (HeadYaw 0).
            Vector3 toSeat = lookTarget != null ? lookTarget.position - transform.position : Vector3.back;
            toSeat.y = 0f;
            _forward = toSeat.sqrMagnitude > 0.01f ? toSeat.normalized : Vector3.back;
            if (speech != null) speech.SentenceStarted += _ => _emphasis = 1f;
        }

        public void SetState(PepperState state)
        {
            if (state == State) return;
            State = state;
            _stateTime = 0f;
        }

        /// <summary>Friendly wave, used when a session starts.</summary>
        public void Wave(float seconds = 2.2f) => _waveUntil = _time + seconds;

        void Update()
        {
            if (!_rig.Ready) return;
            float dt = Time.deltaTime;
            _time += dt;
            _stateTime += dt;
            _emphasis = Mathf.MoveTowards(_emphasis, 0f, dt * 1.4f);

            float voice = speech != null ? speech.Level : 0f;
            float micLevel = mic != null ? Mathf.Clamp01(mic.Level * 12f) : 0f;

            UpdateHead(voice, micLevel);
            UpdateBody();
            if (_time < _waveUntil) WaveArms();
            else UpdateArms(voice);
            UpdateLeds(voice, micLevel);
        }

        void UpdateHead(float voice, float micLevel)
        {
            float yaw = 0f, pitch = PepperRig.StandAngle("HeadPitch");
            if (lookTarget != null && _head != null)
            {
                Vector3 eye = _head.position + Vector3.up * 0.1f;
                Vector3 to = lookTarget.position - eye;
                Vector3 flat = new Vector3(to.x, 0f, to.z);
                // Unity's SignedAngle is positive toward Pepper's right; NAOqi HeadYaw is positive to its left.
                yaw = -Vector3.SignedAngle(_forward, flat, Vector3.up) * Mathf.Deg2Rad;
                pitch = -Mathf.Atan2(to.y, flat.magnitude); // NAOqi HeadPitch is positive looking down
            }

            // Tiny saccade-like drift so the gaze never looks frozen.
            yaw += (Mathf.PerlinNoise(_time * 0.35f, 1.7f) - 0.5f) * 0.08f;
            pitch += (Mathf.PerlinNoise(_time * 0.3f, 4.2f) - 0.5f) * 0.05f;

            switch (State)
            {
                case PepperState.Thinking:
                    float away = Mathf.Clamp01(_stateTime * 2f);
                    yaw += 0.35f * away;
                    pitch -= 0.25f * away;
                    break;
                case PepperState.Listening:
                    pitch += 0.06f + micLevel * 0.05f; // slight attentive nod
                    break;
                case PepperState.Speaking:
                    pitch += Mathf.Sin(_time * 2.4f) * 0.035f * (0.4f + voice);
                    break;
            }

            _rig.Set("HeadYaw", Mathf.Clamp(yaw, -1.2f, 1.2f));
            _rig.Set("HeadPitch", Mathf.Clamp(pitch, -0.6f, 0.45f));
        }

        void UpdateBody()
        {
            float lean = State == PepperState.Listening ? -0.07f : 0f; // lean in towards the speaker
            _rig.Set("HipPitch", PepperRig.StandAngle("HipPitch") + lean + Mathf.Sin(_time * 1.25f) * 0.012f);
            _rig.Set("HipRoll", Mathf.Sin(_time * 0.37f) * 0.018f);
        }

        void UpdateArms(float voice)
        {
            switch (State)
            {
                case PepperState.Speaking:
                {
                    float energy = Mathf.Clamp01(0.35f + voice * 1.2f);
                    // Beat gestures: smooth noise scaled by how loudly Pepper is speaking, plus an "open
                    // hands" emphasis at the start of each sentence.
                    float n1 = Noise(0.7f, 11f), n2 = Noise(0.6f, 23f), n3 = Noise(0.5f, 37f), n4 = Noise(0.8f, 41f);
                    float m1 = Noise(0.55f, 53f), m2 = Noise(0.65f, 67f), m3 = Noise(0.45f, 71f);
                    float open = _emphasis;

                    Arm("R", Mathf.Lerp(1.45f, 0.7f, energy * n1) - open * 0.3f,
                        -0.12f - 0.3f * energy * n2 - open * 0.35f,
                        0.9f + 0.6f * n3,
                        0.55f + 0.75f * energy * n4 - open * 0.2f,
                        0.2f + 1.1f * n2);
                    Arm("L", Mathf.Lerp(1.5f, 0.95f, energy * m1 * 0.7f) - open * 0.3f,
                        0.12f + 0.22f * energy * m2 + open * 0.35f,
                        -0.9f - 0.5f * m3,
                        -0.5f - 0.6f * energy * m1 + open * 0.2f,
                        -0.2f - 0.9f * m2);
                    break;
                }
                case PepperState.Listening:
                    // Attentive: forearms slightly raised.
                    Arm("R", 1.3f, -0.12f, 1.25f, 0.8f, 0.4f);
                    Arm("L", 1.3f, 0.12f, -1.25f, -0.8f, -0.4f);
                    break;
                case PepperState.Thinking:
                    // Right hand comes up a little, as if considering.
                    Arm("R", 0.95f, -0.2f, 1.45f, 1.25f, 1.0f);
                    Arm("L", 1.5f, 0.12f, -1.22f, -0.55f, 0f);
                    break;
                default:
                    // Relaxed StandInit with a little life in it.
                    float idle = Noise(0.25f, 5f) * 0.06f;
                    Arm("R", 1.57f - idle, -0.12f, 1.2217f, 0.5235f + idle, 0f);
                    Arm("L", 1.57f - idle, 0.12f, -1.2217f, -0.5235f - idle, 0f);
                    break;
            }
        }

        void WaveArms()
        {
            float swing = Mathf.Sin(_time * 9f);
            Arm("R", -0.9f, -0.35f, 1.5f, 1.0f + swing * 0.35f, 1.4f);
            Arm("L", 1.57f, 0.12f, -1.2217f, -0.5235f, 0f);
        }

        void Arm(string side, float shoulderPitch, float shoulderRoll, float elbowYaw, float elbowRoll, float wristYaw)
        {
            _rig.Set(side + "ShoulderPitch", shoulderPitch);
            _rig.Set(side + "ShoulderRoll", shoulderRoll);
            _rig.Set(side + "ElbowYaw", elbowYaw);
            _rig.Set(side + "ElbowRoll", elbowRoll);
            _rig.Set(side + "WristYaw", wristYaw);
        }

        float Noise(float speed, float seed) => Mathf.PerlinNoise(_time * speed, seed);

        // --- LEDs ----------------------------------------------------------------------------------

        void CollectLeds()
        {
            var renderers = new System.Collections.Generic.List<Renderer>();
            var slots = new System.Collections.Generic.List<int>();
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    if (mats[i] == null) continue;
                    if (mats[i].name.StartsWith("Pepper_Face") || mats[i].name.StartsWith("Pepper_BlueLED"))
                    {
                        renderers.Add(r);
                        slots.Add(i);
                    }
                }
            }
            _ledRenderers = renderers.ToArray();
            _ledSlots = slots.ToArray();
        }

        void UpdateLeds(float voice, float micLevel)
        {
            Color target;
            float brightness;
            switch (State)
            {
                case PepperState.Listening:
                    target = listeningColor;
                    brightness = 0.7f + micLevel * 0.6f;
                    break;
                case PepperState.Thinking:
                    target = Color.Lerp(thinkingColor, Color.white, (Mathf.Sin(_time * 7f) + 1f) * 0.25f);
                    brightness = 0.75f + Mathf.Sin(_time * 7f) * 0.2f;
                    break;
                case PepperState.Speaking:
                    target = speakingColor;
                    brightness = 0.6f + voice * 0.9f;
                    break;
                default:
                    target = idleColor;
                    brightness = 0.45f + (Mathf.Sin(_time * 1.6f) + 1f) * 0.12f; // slow "breathing" glow
                    break;
            }
            if (Alert) target = alertColor;

            _ledColor = Color.Lerp(_ledColor, target * brightness * ledIntensity, Time.deltaTime * 10f);
            for (int i = 0; i < _ledRenderers.Length; i++)
            {
                _ledRenderers[i].GetPropertyBlock(_mpb, _ledSlots[i]);
                _mpb.SetColor(EmissionColor, _ledColor);
                _ledRenderers[i].SetPropertyBlock(_mpb, _ledSlots[i]);
            }
        }
    }
}
