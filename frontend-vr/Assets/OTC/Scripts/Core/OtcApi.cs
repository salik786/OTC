using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace Otc.VR
{
    /// <summary>
    /// Coroutine client for the shared OTC backend - the same endpoints frontend-app and frontend-pepper
    /// use (see frontend-app/src/lib/api.ts and backend/app/schemas.py).
    /// </summary>
    public static class OtcApi
    {
        public const string Platform = "vr_quest";

        public class Product
        {
            public string id;
            public string slug;
            public string display_name;
        }

        public class Session
        {
            public string session_id;
            public string participant_id;
            public string condition;
            public string product_slug;
            public string product_display_name;
        }

        public class CoreInfo
        {
            public string product_name;
            public string used_for;
            public string dose;
            public string frequency;
            public string max_dose_24h;
            public List<string> warnings = new List<string>();
            public string full_text;
        }

        public class AnswerDone
        {
            public int turn_number;
            public bool in_scope;
            public float latency_ms;
            public string answer_text;
            public List<string> sources = new List<string>();
        }

        static string Url(string path) => OtcSettings.Instance.BaseUrl + path;

        /// <summary>Lists the study's medicines, retrying with backoff - the free-tier backend may be asleep.</summary>
        public static IEnumerator ListProducts(Action<List<Product>> ok, Action<string> fail)
        {
            string lastError = null;
            float delay = 2f;
            for (int attempt = 0; attempt < 4; attempt++)
            {
                using var req = UnityWebRequest.Get(Url("/api/products"));
                req.timeout = 30;
                yield return req.SendWebRequest();
                if (req.result == UnityWebRequest.Result.Success)
                {
                    ok(JsonConvert.DeserializeObject<List<Product>>(req.downloadHandler.text));
                    yield break;
                }
                lastError = Describe(req);
                yield return new WaitForSeconds(delay);
                delay *= 2f;
            }
            fail(lastError);
        }

        public static IEnumerator StartSession(string productSlug, Action<Session> ok, Action<string> fail)
        {
            var body = new
            {
                platform = Platform,
                product_slug = productSlug,
                device_info = new
                {
                    user_agent = $"Unity {Application.unityVersion}; {SystemInfo.deviceModel}; {SystemInfo.operatingSystem}",
                    screen_width = XRScreenWidth(),
                    screen_height = XRScreenHeight(),
                },
            };
            yield return PostJson(Url("/api/session/start"), body, ok, fail);
        }

        public static IEnumerator EndSession(string sessionId, int errorsLogged, Action<string> fail = null)
        {
            yield return PostJson<JObject>(Url($"/api/session/{sessionId}/end"), new { errors_logged = errorsLogged },
                _ => { }, fail ?? (e => Debug.LogWarning($"[OTC] end session failed: {e}")));
        }

        public static IEnumerator GetCoreInfo(string sessionId, string language, Action<CoreInfo> ok, Action<string> fail)
        {
            string url = Url($"/api/core-info?session_id={UnityWebRequest.EscapeURL(sessionId)}");
            if (!string.IsNullOrEmpty(language))
                url += $"&language={UnityWebRequest.EscapeURL(language)}";
            using var req = new UnityWebRequest(url, "POST") { downloadHandler = new DownloadHandlerBuffer(), timeout = 60 };
            yield return req.SendWebRequest();
            if (req.result == UnityWebRequest.Result.Success)
                ok(JsonConvert.DeserializeObject<CoreInfo>(req.downloadHandler.text));
            else
                fail(Describe(req));
        }

        /// <summary>
        /// Streams an answer: onDelta gets each text chunk as the model writes it (so speech can start
        /// on the first sentence), onDone the final metadata.
        /// </summary>
        public static IEnumerator AskStream(string sessionId, string question, string inputMethod, string language,
            Action<string> onDelta, Action<AnswerDone> onDone, Action<string> fail)
        {
            var body = new Dictionary<string, object>
            {
                ["session_id"] = sessionId,
                ["query_text"] = question,
                ["input_method"] = inputMethod,
            };
            if (!string.IsNullOrEmpty(language))
                body["response_language"] = language;

            var handler = new NdjsonDownloadHandler(onDelta);
            using var req = new UnityWebRequest(Url("/api/query/stream"), "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(body))),
                downloadHandler = handler,
                timeout = 90,
            };
            req.SetRequestHeader("Content-Type", "application/json");
            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
                fail(Describe(req));
            else if (handler.Done == null)
                fail("Stream ended without a final result");
            else
                onDone(handler.Done);
        }

        public static IEnumerator Transcribe(byte[] wav, Action<string> ok, Action<string> fail)
        {
            var form = new List<IMultipartFormSection>
            {
                new MultipartFormFileSection("audio", wav, "recording.wav", "audio/wav"),
            };
            using var req = UnityWebRequest.Post(Url("/api/stt"), form);
            req.timeout = 60;
            yield return req.SendWebRequest();
            if (req.result == UnityWebRequest.Result.Success)
                ok(JObject.Parse(req.downloadHandler.text)["transcript"]?.ToString() ?? "");
            else
                fail(Describe(req));
        }

        /// <summary>Text-to-speech through the backend proxy (MP3), decoded into an AudioClip.</summary>
        public static IEnumerator Speak(string text, bool slow, Action<AudioClip> ok, Action<string> fail)
        {
            string url = Url("/api/tts");
            var json = JsonConvert.SerializeObject(new { text, slow });
            using var req = new UnityWebRequest(url, "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
                downloadHandler = new DownloadHandlerAudioClip(url, AudioType.MPEG),
                timeout = 60,
            };
            req.SetRequestHeader("Content-Type", "application/json");
            yield return req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success)
            {
                fail(Describe(req));
                yield break;
            }
            var clip = DownloadHandlerAudioClip.GetContent(req);
            if (clip == null || clip.length <= 0f)
                fail("TTS returned no audio");
            else
                ok(clip);
        }

        static IEnumerator PostJson<T>(string url, object body, Action<T> ok, Action<string> fail)
        {
            using var req = new UnityWebRequest(url, "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(body))),
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = 30,
            };
            req.SetRequestHeader("Content-Type", "application/json");
            yield return req.SendWebRequest();
            if (req.result == UnityWebRequest.Result.Success)
                ok(JsonConvert.DeserializeObject<T>(req.downloadHandler.text));
            else
                fail(Describe(req));
        }

        static string Describe(UnityWebRequest req)
        {
            string body = req.downloadHandler is DownloadHandlerBuffer b ? b.text : null;
            return string.IsNullOrEmpty(body) ? $"{req.responseCode} {req.error}" : $"{req.responseCode} {body}";
        }

        static int XRScreenWidth() => UnityEngine.XR.XRSettings.enabled ? UnityEngine.XR.XRSettings.eyeTextureWidth : Screen.width;
        static int XRScreenHeight() => UnityEngine.XR.XRSettings.enabled ? UnityEngine.XR.XRSettings.eyeTextureHeight : Screen.height;

        /// <summary>Parses /api/query/stream's newline-delimited JSON as bytes arrive.</summary>
        class NdjsonDownloadHandler : DownloadHandlerScript
        {
            readonly Action<string> _onDelta;
            readonly Decoder _decoder = Encoding.UTF8.GetDecoder(); // keeps multi-byte characters split across chunks intact
            readonly StringBuilder _buffer = new StringBuilder();
            public AnswerDone Done { get; private set; }

            public NdjsonDownloadHandler(Action<string> onDelta) : base(new byte[4096]) => _onDelta = onDelta;

            protected override bool ReceiveData(byte[] data, int length)
            {
                if (data == null || length == 0) return true;
                var chars = new char[_decoder.GetCharCount(data, 0, length)];
                _decoder.GetChars(data, 0, length, chars, 0);
                _buffer.Append(chars);

                string text = _buffer.ToString();
                int newline;
                while ((newline = text.IndexOf('\n')) >= 0)
                {
                    string line = text.Substring(0, newline).Trim();
                    text = text.Substring(newline + 1);
                    if (line.Length > 0) HandleLine(line);
                }
                _buffer.Clear().Append(text);
                return true;
            }

            protected override void CompleteContent()
            {
                string rest = _buffer.ToString().Trim();
                if (rest.Length > 0) HandleLine(rest);
                _buffer.Clear();
            }

            void HandleLine(string line)
            {
                var obj = JObject.Parse(line);
                if (obj["delta"] != null)
                    _onDelta?.Invoke(obj["delta"].ToString());
                else if (obj["done"]?.Value<bool>() == true)
                    Done = obj.ToObject<AnswerDone>();
            }
        }
    }
}
