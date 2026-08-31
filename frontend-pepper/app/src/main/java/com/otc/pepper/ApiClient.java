package com.otc.pepper;

import android.os.Build;
import android.util.DisplayMetrics;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import javax.net.ssl.X509TrustManager;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/**
 * Thin REST client for the OTC backend. Mirrors backend/app/schemas.py request/response shapes
 * exactly (verified live against the Railway deployment) - see frontend-app/src/lib/api.ts for the
 * equivalent web client this is a native port of.
 *
 * No /api/stt or /api/tts calls here: Pepper uses its own QiSDK Say (output) and Android
 * SpeechRecognizer (input) instead of the backend's Whisper/TTS proxy - see ConversationController.
 */
public final class ApiClient {

    private ApiClient() {}

    private static final String TAG = "OtcApiClient";
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private static final OkHttpClient CLIENT = buildClient();

    private static OkHttpClient buildClient() {
        OkHttpClient.Builder builder = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .writeTimeout(15, TimeUnit.SECONDS);
        try {
            X509TrustManager trustManager = TrustManagerUtil.buildCompositeTrustManager(PepperApplication.getContext());
            builder.sslSocketFactory(TrustManagerUtil.buildSslSocketFactory(PepperApplication.getContext(), trustManager), trustManager);
        } catch (Exception e) {
            // Falls back to the platform default trust store - fine on devices whose system CAs
            // are already current; only Pepper's old Android 6.0 image needed the bundled roots.
            Log.w(TAG, "Could not install bundled trust anchors, using system default: " + e.getMessage());
        }
        return builder.build();
    }

    public interface ApiCallback<T> {
        void onSuccess(T result);
        void onError(String message);
    }

    // ---- Data models (mirrors backend/app/schemas.py) ----

    public static class Product {
        public final String slug;
        public final String displayName;

        Product(JSONObject o) throws Exception {
            slug = o.getString("slug");
            displayName = o.getString("display_name");
        }
    }

    public static class SessionStartResponse {
        public final String sessionId;
        public final String participantId;
        public final String productSlug;
        public final String productDisplayName;

        SessionStartResponse(JSONObject o) throws Exception {
            sessionId = o.getString("session_id");
            participantId = o.getString("participant_id");
            productSlug = o.getString("product_slug");
            productDisplayName = o.getString("product_display_name");
        }
    }

    public static class CoreInfoResponse {
        public final String productName;
        public final String usedFor;
        public final String dose;
        public final String frequency;
        public final String maxDose24h;
        public final List<String> warnings;
        public final String fullText;

        CoreInfoResponse(JSONObject o) throws Exception {
            productName = o.getString("product_name");
            usedFor = o.isNull("used_for") ? null : o.getString("used_for");
            dose = o.isNull("dose") ? null : o.getString("dose");
            frequency = o.isNull("frequency") ? null : o.getString("frequency");
            maxDose24h = o.isNull("max_dose_24h") ? null : o.getString("max_dose_24h");
            fullText = o.getString("full_text");
            warnings = new ArrayList<>();
            JSONArray arr = o.getJSONArray("warnings");
            for (int i = 0; i < arr.length(); i++) warnings.add(arr.getString(i));
        }
    }

    public static class QueryResponse {
        public final String answerText;
        public final boolean inScope;
        public final int turnNumber;

        QueryResponse(JSONObject o) throws Exception {
            answerText = o.getString("answer_text");
            inScope = o.getBoolean("in_scope");
            turnNumber = o.getInt("turn_number");
        }
    }

    // ---- Calls ----

    /** Public (no-auth) medicine list - only products with an active ingested document, matching
     * frontend-app's ResearcherSetup screen (see backend/app/routes/sessions.py:list_available_products).
     * Fetched fresh on every launch instead of hardcoded, so a medicine an admin adds via the
     * admin panel shows up on Pepper the same way it does on the tablet, with no app update. */
    public static void listProducts(ApiCallback<List<Product>> cb) {
        run(() -> {
            Request request = new Request.Builder()
                    .url(BuildConfig.API_BASE_URL + "/api/products")
                    .get()
                    .build();
            try (Response response = CLIENT.newCall(request).execute()) {
                String responseBody = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    throw new Exception("HTTP " + response.code() + ": " + responseBody);
                }
                JSONArray arr = new JSONArray(responseBody);
                List<Product> products = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) products.add(new Product(arr.getJSONObject(i)));
                return products;
            }
        }, cb);
    }

    /** platform is always "pepper" - a value the backend's Platform literal already supports. */
    public static void startSession(String productSlug, ApiCallback<SessionStartResponse> cb) {
        run(() -> {
            JSONObject deviceInfo = new JSONObject()
                    .put("user_agent", "pepper/" + Build.MODEL)
                    .put("screen_width", screenWidth())
                    .put("screen_height", screenHeight());
            JSONObject body = new JSONObject()
                    .put("platform", "pepper")
                    .put("product_slug", productSlug)
                    .put("device_info", deviceInfo);
            JSONObject resp = post("/api/session/start", body);
            return new SessionStartResponse(resp);
        }, cb);
    }

    public static void endSession(String sessionId, ApiCallback<Void> cb) {
        run(() -> {
            post("/api/session/" + sessionId + "/end", new JSONObject().put("errors_logged", 0));
            return null;
        }, cb);
    }

    /** session_id is a query param on this endpoint (see backend/app/routes/query.py:core_info),
     * not a JSON body field. */
    public static void coreInfo(String sessionId, ApiCallback<CoreInfoResponse> cb) {
        run(() -> {
            JSONObject resp = postNoBody("/api/core-info?session_id=" + sessionId);
            return new CoreInfoResponse(resp);
        }, cb);
    }

    public static void query(String sessionId, String queryText, String inputMethod, ApiCallback<QueryResponse> cb) {
        run(() -> {
            JSONObject body = new JSONObject()
                    .put("session_id", sessionId)
                    .put("query_text", queryText)
                    .put("input_method", inputMethod);
            JSONObject resp = post("/api/query", body);
            return new QueryResponse(resp);
        }, cb);
    }

    // ---- Internals ----

    private interface Call<T> {
        T run() throws Exception;
    }

    private static <T> void run(Call<T> call, ApiCallback<T> cb) {
        new Thread(() -> {
            try {
                T result = call.run();
                cb.onSuccess(result);
            } catch (Exception e) {
                cb.onError(e.getMessage() != null ? e.getMessage() : e.toString());
            }
        }).start();
    }

    private static JSONObject post(String path, JSONObject body) throws Exception {
        RequestBody requestBody = RequestBody.create(body.toString(), JSON);
        Request request = new Request.Builder()
                .url(BuildConfig.API_BASE_URL + path)
                .post(requestBody)
                .build();
        return execute(request);
    }

    private static JSONObject postNoBody(String path) throws Exception {
        Request request = new Request.Builder()
                .url(BuildConfig.API_BASE_URL + path)
                .post(RequestBody.create(new byte[0], null))
                .build();
        return execute(request);
    }

    private static JSONObject execute(Request request) throws Exception {
        try (Response response = CLIENT.newCall(request).execute()) {
            String responseBody = response.body() != null ? response.body().string() : "";
            if (!response.isSuccessful()) {
                throw new Exception("HTTP " + response.code() + ": " + responseBody);
            }
            return new JSONObject(responseBody);
        }
    }

    private static int screenWidth() {
        DisplayMetrics dm = android.content.res.Resources.getSystem().getDisplayMetrics();
        return dm.widthPixels;
    }

    private static int screenHeight() {
        DisplayMetrics dm = android.content.res.Resources.getSystem().getDisplayMetrics();
        return dm.heightPixels;
    }
}
