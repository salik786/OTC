using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace Otc.VR
{
    /// <summary>
    /// Speaks an answer sentence by sentence while it is still streaming in: each complete sentence is
    /// sent to /api/tts straight away (fetches run ahead in parallel) and played in order from Pepper's
    /// head - the same latency trick as the tablet app's useTTS.speakStream().
    /// </summary>
    public class SpeechPlayer : MonoBehaviour
    {
        public AudioSource source;

        public bool IsSpeaking => _items.Count > _playIndex || (source != null && source.isPlaying);
        /// <summary>Loudness of what Pepper is currently saying, 0..1 - drives LEDs and gesture energy.</summary>
        public float Level { get; private set; }

        public event Action<string> SentenceStarted;
        /// <summary>Raised once every queued sentence has been spoken and EndOfText() was called.</summary>
        public event Action Finished;

        class Item
        {
            public string Text;
            public AudioClip Clip;
            public bool Done;
        }

        readonly List<Item> _items = new List<Item>();
        readonly StringBuilder _pending = new StringBuilder();
        readonly float[] _samples = new float[256];
        int _playIndex;
        bool _textComplete;
        int _generation; // bumps on Stop() so late TTS responses from an old answer are dropped
        Coroutine _playLoop;

        /// <summary>Starts a new utterance (stops anything currently playing).</summary>
        public void Begin()
        {
            Stop();
            _textComplete = false;
            _playLoop = StartCoroutine(PlayLoop(_generation));
        }

        /// <summary>Feeds streamed text; complete sentences are queued for speech immediately.</summary>
        public void AddText(string delta)
        {
            _pending.Append(delta);
            foreach (string sentence in TakeSentences(_pending, final: false))
                Enqueue(sentence);
        }

        /// <summary>No more text is coming; speaks whatever is left over.</summary>
        public void EndOfText()
        {
            foreach (string sentence in TakeSentences(_pending, final: true))
                Enqueue(sentence);
            _textComplete = true;
        }

        /// <summary>Convenience for a complete text (core info, safety prompts).</summary>
        public void Say(string text)
        {
            Begin();
            AddText(text);
            EndOfText();
        }

        public void Stop()
        {
            _generation++;
            if (_playLoop != null) StopCoroutine(_playLoop);
            _playLoop = null;
            if (source != null) source.Stop();
            _items.Clear();
            _pending.Clear();
            _playIndex = 0;
            _textComplete = true;
            Level = 0f;
        }

        void Enqueue(string sentence)
        {
            var item = new Item { Text = sentence };
            _items.Add(item);
            int generation = _generation;
            StartCoroutine(OtcApi.Speak(sentence, OtcSettings.Instance.SlowSpeech,
                clip => { if (generation == _generation) { item.Clip = clip; item.Done = true; } },
                error =>
                {
                    Debug.LogWarning($"[OTC] TTS failed: {error}");
                    if (generation == _generation) item.Done = true;
                }));
        }

        IEnumerator PlayLoop(int generation)
        {
            while (generation == _generation)
            {
                if (_playIndex < _items.Count)
                {
                    var item = _items[_playIndex];
                    while (!item.Done && generation == _generation) yield return null;
                    if (generation != _generation) yield break;

                    SentenceStarted?.Invoke(item.Text);
                    if (item.Clip != null)
                    {
                        source.clip = item.Clip;
                        source.Play();
                        while (source.isPlaying && generation == _generation) yield return null;
                    }
                    else
                    {
                        // TTS failed: leave the caption up for a reading-speed pause instead of skipping it.
                        yield return new WaitForSeconds(Mathf.Clamp(item.Text.Length * 0.06f, 1.5f, 8f));
                    }
                    _playIndex++;
                }
                else if (_textComplete)
                {
                    _playLoop = null;
                    Finished?.Invoke();
                    yield break;
                }
                else
                {
                    yield return null;
                }
            }
        }

        void Update()
        {
            if (source == null || !source.isPlaying)
            {
                Level = Mathf.MoveTowards(Level, 0f, Time.deltaTime * 4f);
                return;
            }
            source.GetOutputData(_samples, 0);
            float sum = 0f;
            foreach (float s in _samples) sum += s * s;
            float rms = Mathf.Sqrt(sum / _samples.Length);
            Level = Mathf.Lerp(Level, Mathf.Clamp01(rms * 6f), Time.deltaTime * 18f);
        }

        /// <summary>Removes complete sentences from the buffer. With final=true the remainder counts too.</summary>
        public static List<string> TakeSentences(StringBuilder buffer, bool final)
        {
            var result = new List<string>();
            string text = buffer.ToString();
            int start = 0;
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                bool terminator = c == '.' || c == '!' || c == '?' || c == '\n' || c == '。' || c == '！' || c == '？';
                // Only split once the next character is known, so "2.5 mg" or "e.g." mid-stream isn't cut.
                if (terminator && i + 1 < text.Length && (char.IsWhiteSpace(text[i + 1]) || c == '\n' || c > 0x3000))
                {
                    string sentence = text.Substring(start, i + 1 - start).Trim();
                    if (sentence.Length > 1) result.Add(sentence);
                    start = i + 1;
                }
            }
            string rest = text.Substring(start);
            if (final)
            {
                if (rest.Trim().Length > 0) result.Add(rest.Trim());
                rest = "";
            }
            buffer.Clear().Append(rest);
            return result;
        }
    }
}
