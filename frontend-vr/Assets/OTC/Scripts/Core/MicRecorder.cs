using System;
using System.IO;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// Records the participant's question and hands back a 16-bit mono WAV for /api/stt. Stops on its
    /// own after a pause in speech (same behaviour as the tablet app's voice mode), or when Stop() is called.
    /// </summary>
    public class MicRecorder : MonoBehaviour
    {
        const int PreferredRate = 16000;
        const int MaxSeconds = 20;

        [Tooltip("RMS level counted as speech.")]
        public float voiceThreshold = 0.02f;
        [Tooltip("Seconds of quiet after speech before recording stops by itself.")]
        public float silenceToStop = 1.3f;
        public float minSeconds = 0.5f;

        public bool IsRecording { get; private set; }
        public float Level { get; private set; }

        /// <summary>WAV bytes, or null if nothing usable was recorded (too short / no speech).</summary>
        public event Action<byte[]> Finished;

        AudioClip _clip;
        int _rate;
        float _startTime, _lastVoiceTime;
        bool _heardVoice;
        readonly float[] _window = new float[512];

        void Start()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!UnityEngine.Android.Permission.HasUserAuthorizedPermission(UnityEngine.Android.Permission.Microphone))
                UnityEngine.Android.Permission.RequestUserPermission(UnityEngine.Android.Permission.Microphone);
#endif
        }

        public bool Begin()
        {
            if (IsRecording) return true;
            if (Microphone.devices.Length == 0)
            {
                Debug.LogWarning("[OTC] No microphone available");
                return false;
            }

            Microphone.GetDeviceCaps(null, out int minRate, out int maxRate);
            _rate = maxRate == 0 ? PreferredRate : Mathf.Clamp(PreferredRate, Mathf.Max(minRate, 1), maxRate);
            _clip = Microphone.Start(null, false, MaxSeconds, _rate);
            Debug.Log($"[OTC] Recording on '{Microphone.devices[0]}' at {_rate} Hz (clip {(_clip != null ? "ok" : "null")})");
            _startTime = _lastVoiceTime = Time.unscaledTime;
            _heardVoice = false;
            IsRecording = true;
            return true;
        }

        public void Stop()
        {
            if (!IsRecording) return;
            int samples = Microphone.GetPosition(null);
            Microphone.End(null);
            IsRecording = false;
            Level = 0f;

            float duration = samples / (float)_rate;
            if (_clip == null || samples <= 0 || duration < minSeconds || !_heardVoice)
            {
                Finished?.Invoke(null);
                return;
            }

            var data = new float[samples * _clip.channels];
            _clip.GetData(data, 0);
            Finished?.Invoke(EncodeWav(data, _clip.channels, _rate));
        }

        public void Cancel()
        {
            if (!IsRecording) return;
            Microphone.End(null);
            IsRecording = false;
            Level = 0f;
        }

        void Update()
        {
            if (!IsRecording) return;

            int pos = Microphone.GetPosition(null);
            if (pos >= _window.Length)
            {
                _clip.GetData(_window, pos - _window.Length);
                float sum = 0f;
                foreach (float s in _window) sum += s * s;
                Level = Mathf.Sqrt(sum / _window.Length);
                if (Level > voiceThreshold)
                {
                    _heardVoice = true;
                    _lastVoiceTime = Time.unscaledTime;
                }
            }

            float elapsed = Time.unscaledTime - _startTime;
            bool quietAfterSpeech = _heardVoice && Time.unscaledTime - _lastVoiceTime > silenceToStop;
            if ((quietAfterSpeech && elapsed > minSeconds) || elapsed > MaxSeconds - 0.25f)
                Stop();
        }

        static byte[] EncodeWav(float[] samples, int channels, int rate)
        {
            using var stream = new MemoryStream(44 + samples.Length * 2);
            using var w = new BinaryWriter(stream);
            int dataBytes = samples.Length * 2;
            w.Write(new[] { 'R', 'I', 'F', 'F' });
            w.Write(36 + dataBytes);
            w.Write(new[] { 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ' });
            w.Write(16);
            w.Write((short)1); // PCM
            w.Write((short)channels);
            w.Write(rate);
            w.Write(rate * channels * 2);
            w.Write((short)(channels * 2));
            w.Write((short)16);
            w.Write(new[] { 'd', 'a', 't', 'a' });
            w.Write(dataBytes);
            foreach (float s in samples)
                w.Write((short)(Mathf.Clamp(s, -1f, 1f) * short.MaxValue));
            return stream.ToArray();
        }
    }
}
