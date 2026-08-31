package com.otc.pepper;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Log;
import android.view.Gravity;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;

import java.util.ArrayList;

/**
 * Native port of frontend-app/src/screens/VoiceTextChat.tsx. Voice uses Android SpeechRecognizer
 * (free-form dictation) instead of QiSDK's Listen action, which only matches a fixed phrase list -
 * see plan notes / TalkToPepperActivity.java in the Interledger reference. Unlike the web's
 * MediaRecorder flow, the recognizer auto-detects end of speech - tapping the mic only starts
 * listening, the transcript arrives on its own once the user stops talking.
 */
public class ChatActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcChat";
    private static final int REQ_MIC = 101;

    private String sessionId;
    private QiContext qiContext;
    private ConversationController conversation;
    private SpeechRecognizer speechRecognizer;
    private android.content.Intent recognizerIntent;

    private LinearLayout historyContainer;
    private TextView emptyStateTv;
    private ScrollView historyScroll;
    private EditText input;
    private android.widget.ImageView micBtn;
    private TextView statusTv;
    private boolean recording = false;
    private boolean submitting = false;
    /** Hands-free voice loop, matching frontend-app's voiceModeActiveRef pattern: once the
     * participant taps the mic, listening auto-resumes after each answer finishes speaking,
     * instead of requiring another tap. Typing opts back out. */
    private boolean voiceModeActive = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sessionId = getIntent().getStringExtra("session_id");
        conversation = new ConversationController(sessionId, new ConversationController.Listener() {
            @Override
            public void onSubmitStart() {
                runOnUiThread(() -> {
                    submitting = true;
                    setStatus("Thinking...");
                    updateMicEnabled();
                });
            }

            @Override
            public void onTurnAdded(QATurn turn) {
                runOnUiThread(() -> {
                    submitting = false;
                    addTurnBubbles(turn);
                    setStatus("");
                    updateMicEnabled();
                });
            }

            @Override
            public void onSubmitError(String message) {
                Log.e(TAG, "query failed: " + message);
            }

            @Override
            public void onSpeakingStateChanged(boolean speaking) {
                // No dedicated "speaking" visual in this transcript-first screen (matches web,
                // which only shows a speaking indicator on the AvatarChat screen).
                if (!speaking && voiceModeActive && !recording && !submitting) {
                    runOnUiThread(ChatActivity.this::startListening);
                }
            }
        });

        setContentView(buildRoot());
        initSpeechRecognizer();
        QiSDK.register(this, this);
    }

    @Override
    protected void onDestroy() {
        voiceModeActive = false;
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
        conversation.stopSpeaking();
        QiSDK.unregister(this, this);
        super.onDestroy();
    }

    @Override
    public void onRobotFocusGained(QiContext context) {
        this.qiContext = context;
        conversation.setQiContext(context);
    }

    @Override
    public void onRobotFocusLost() {
        this.qiContext = null;
        conversation.setQiContext(null);
    }

    @Override
    public void onRobotFocusRefused(String reason) {
        Log.e(TAG, "Robot focus refused: " + reason);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_MIC && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startListening();
        }
    }

    // ---- UI ----

    private LinearLayout buildRoot() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setBackground(UiKit.screenBackground());
        col.setPadding(UiKit.dp(this, 16), UiKit.dp(this, 16), UiKit.dp(this, 16), UiKit.dp(this, 16));

        LinearLayout.LayoutParams topNavLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        topNavLp.bottomMargin = UiKit.dp(this, 8);
        col.addView(UiKit.topNav(this, v -> finish()), topNavLp);

        historyScroll = new ScrollView(this);
        historyContainer = new LinearLayout(this);
        historyContainer.setOrientation(LinearLayout.VERTICAL);
        historyContainer.setPadding(0, UiKit.dp(this, 8), 0, UiKit.dp(this, 8));

        emptyStateTv = UiKit.muted(this, "Ask anything about this medicine - by voice or by typing below.");
        historyContainer.addView(emptyStateTv, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        historyScroll.addView(historyContainer, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        col.addView(historyScroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        statusTv = UiKit.muted(this, "");
        col.addView(statusTv, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout inputBar = new LinearLayout(this);
        inputBar.setOrientation(LinearLayout.HORIZONTAL);
        inputBar.setGravity(Gravity.CENTER_VERTICAL);
        inputBar.setPadding(0, UiKit.dp(this, 8), 0, UiKit.dp(this, 8));

        input = new EditText(this);
        input.setHint("Type your question");
        input.setBackground(fieldBg());
        input.setPadding(UiKit.dp(this, 16), UiKit.dp(this, 12), UiKit.dp(this, 16), UiKit.dp(this, 12));
        inputBar.addView(input, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        micBtn = UiKit.icon(this, R.drawable.ic_mic, 52, 0xFFFFFFFF);
        micBtn.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14));
        micBtn.setBackground(UiKit.circleGradientBg(this));
        micBtn.setOnClickListener(v -> onMicTapped());
        ((LinearLayout.LayoutParams) micBtn.getLayoutParams()).setMargins(UiKit.dp(this, 8), 0, UiKit.dp(this, 8), 0);
        inputBar.addView(micBtn);

        android.widget.Button askBtn = UiKit.primaryButton(this, "Ask");
        askBtn.setOnClickListener(v -> handleTypedSubmit());
        inputBar.addView(askBtn, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        col.addView(inputBar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        android.widget.Button endBtn = UiKit.ghostButton(this, "I'm done - end session");
        endBtn.setOnClickListener(v -> endSession());
        col.addView(endBtn, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        return col;
    }

    private GradientDrawable fieldBg() {
        GradientDrawable d = new GradientDrawable();
        d.setColor(UiKit.COLOR_SURFACE);
        d.setCornerRadius(UiKit.dp(this, 12));
        d.setStroke(UiKit.dp(this, 1), UiKit.COLOR_BORDER);
        return d;
    }

    private android.graphics.drawable.Drawable circleBg(int color) {
        return UiKit.circleBg(this, color);
    }

    private void addTurnBubbles(QATurn turn) {
        if (emptyStateTv != null) {
            historyContainer.removeView(emptyStateTv);
            emptyStateTv = null;
        }
        TextView q = UiKit.body(this, turn.queryText);
        q.setBackground(bubbleBg(UiKit.COLOR_PRIMARY, true));
        q.setTextColor(0xFFFFFFFF);
        q.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 10), UiKit.dp(this, 14), UiKit.dp(this, 10));
        LinearLayout.LayoutParams qLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        qLp.gravity = Gravity.END;
        qLp.setMargins(UiKit.dp(this, 40), UiKit.dp(this, 6), 0, UiKit.dp(this, 4));
        historyContainer.addView(q, qLp);

        TextView a = UiKit.body(this, turn.answerText);
        a.setBackground(bubbleBg(turn.inScope ? UiKit.COLOR_SURFACE : UiKit.COLOR_WARNING_BG, false));
        a.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 10), UiKit.dp(this, 14), UiKit.dp(this, 10));
        LinearLayout.LayoutParams aLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        aLp.gravity = Gravity.START;
        aLp.setMargins(0, 0, UiKit.dp(this, 40), UiKit.dp(this, 10));
        historyContainer.addView(a, aLp);

        historyScroll.post(() -> historyScroll.fullScroll(android.view.View.FOCUS_DOWN));
    }

    private GradientDrawable bubbleBg(int color, boolean participant) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(UiKit.dp(this, 14));
        if (!participant) d.setStroke(UiKit.dp(this, 1), UiKit.COLOR_BORDER);
        return d;
    }

    private void setStatus(String text) {
        statusTv.setText(text);
    }

    // ---- Actions ----

    private void handleTypedSubmit() {
        String text = input.getText().toString();
        if (text.trim().isEmpty() || submitting) return;
        voiceModeActive = false; // typing opts back out of the hands-free voice loop
        input.setText("");
        conversation.submit(text, "typed");
    }

    private void onMicTapped() {
        if (recording || submitting) return;
        voiceModeActive = true;
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{android.Manifest.permission.RECORD_AUDIO}, REQ_MIC);
            return;
        }
        startListening();
    }

    private void startListening() {
        if (speechRecognizer == null) initSpeechRecognizer();
        if (speechRecognizer == null) {
            setStatus("Voice input isn't available on this device. Please type your question.");
            return;
        }
        recording = true;
        micBtn.setBackground(circleBg(UiKit.COLOR_WARNING));
        setStatus("Listening... release when you're done.");
        updateMicEnabled();
        try {
            speechRecognizer.startListening(recognizerIntent);
        } catch (Exception e) {
            Log.e(TAG, "startListening: " + e.getMessage(), e);
            recording = false;
            micBtn.setBackground(UiKit.circleGradientBg(this));
        }
    }

    private void initSpeechRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.w(TAG, "Speech recognition not available on this device");
            return;
        }
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
        recognizerIntent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US");
        recognizerIntent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);

        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                recording = false;
                micBtn.setBackground(UiKit.circleGradientBg(ChatActivity.this));
                if (matches != null && !matches.isEmpty() && !matches.get(0).trim().isEmpty()) {
                    conversation.submit(matches.get(0), "voice");
                } else {
                    setStatus("Couldn't understand that. Please try again or type your question.");
                    updateMicEnabled();
                }
            }

            @Override
            public void onError(int error) {
                Log.w(TAG, "Speech error: " + error);
                recording = false;
                micBtn.setBackground(UiKit.circleGradientBg(ChatActivity.this));
                if (error != SpeechRecognizer.ERROR_CLIENT) {
                    setStatus("Microphone access was denied or is unavailable. Please type your question instead.");
                }
                updateMicEnabled();
            }

            @Override public void onReadyForSpeech(Bundle p) {}
            @Override public void onBeginningOfSpeech() {}
            @Override public void onRmsChanged(float v) {}
            @Override public void onBufferReceived(byte[] b) {}
            @Override public void onEndOfSpeech() { setStatus("Got it - one moment..."); }
            @Override public void onPartialResults(Bundle b) {}
            @Override public void onEvent(int t, Bundle b) {}
        });
    }

    private void updateMicEnabled() {
        micBtn.setAlpha(submitting ? 0.5f : 1f);
        micBtn.setEnabled(!submitting);
    }

    private void endSession() {
        voiceModeActive = false;
        conversation.stopSpeaking();
        ApiClient.endSession(sessionId, new ApiClient.ApiCallback<Void>() {
            @Override public void onSuccess(Void result) { goToClosing(); }
            @Override public void onError(String message) {
                // Non-blocking, same as the web version: the closing screen shows regardless.
                Log.w(TAG, "endSession failed: " + message);
                goToClosing();
            }
        });
    }

    private void goToClosing() {
        runOnUiThread(() -> {
            Intent intent = new Intent(this, ClosingActivity.class);
            intent.putExtra("session_id", sessionId);
            startActivity(intent);
            finish();
        });
    }
}
