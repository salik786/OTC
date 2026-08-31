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
 * Native port of frontend-app/src/screens/AvatarChat.tsx. The web version shows an animated
 * on-screen avatar as the interaction focus; on Pepper the robot itself is the physical avatar, so
 * this screen is just a large mic button + status line + compact transcript, and "speaking" is
 * Pepper's own Say output rather than a CSS animation state.
 */
public class AvatarChatActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcAvatarChat";
    private static final int REQ_MIC = 102;

    private String sessionId;
    private QiContext qiContext;
    private ConversationController conversation;
    private SpeechRecognizer speechRecognizer;
    private Intent recognizerIntent;

    private TextView statusTv;
    private android.widget.ImageView micBtn;
    private android.view.View orbView;
    private LinearLayout dock;
    private TextView typeInsteadTv;
    private LinearLayout transcriptContainer;
    private TextView transcriptEmptyTv;
    private ScrollView transcriptScroll;
    private LinearLayout typedRow;
    private EditText typedInput;
    private android.widget.ImageView stopBtn;
    private boolean showTyped = false;
    private boolean recording = false;
    private boolean submitting = false;
    private boolean speaking = false;
    /** Hands-free voice loop, matching frontend-app's voiceModeActiveRef pattern - see ChatActivity. */
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
                    updateStatus();
                });
            }

            @Override
            public void onTurnAdded(QATurn turn) {
                runOnUiThread(() -> {
                    submitting = false;
                    addTranscriptTurn(turn);
                    updateStatus();
                });
            }

            @Override
            public void onSubmitError(String message) {
                Log.e(TAG, "query failed: " + message);
            }

            @Override
            public void onSpeakingStateChanged(boolean isSpeaking) {
                runOnUiThread(() -> {
                    speaking = isSpeaking;
                    updateStatus();
                    if (!isSpeaking && voiceModeActive && !recording && !submitting && !showTyped) {
                        startListening();
                    }
                });
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
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackground(UiKit.screenBackground(this));
        root.setPadding(UiKit.dp(this, 24), UiKit.dp(this, 16), UiKit.dp(this, 24), UiKit.dp(this, 16));

        LinearLayout.LayoutParams topNavLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        topNavLp.bottomMargin = UiKit.dp(this, 8);
        root.addView(UiKit.topNav(this, v -> finish()), topNavLp);

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.VERTICAL);
        main.setGravity(Gravity.CENTER);
        main.setPadding(0, UiKit.dp(this, 16), 0, UiKit.dp(this, 16));

        orbView = UiKit.orb(this);
        main.addView(orbView, wrapWithMargins(0, 0, 0, UiKit.dp(this, 24)));

        statusTv = UiKit.body(this, "Tap the microphone to talk to me.");
        UiKit.center(statusTv);
        main.addView(statusTv, wrapWithMargins(0, 0, 0, UiKit.dp(this, 20)));

        // Dock: one white pill holding the (small) mic button + "Type instead" link side by side,
        // matching frontend-app's .avatar-dock - the orb above is the decorative focal point,
        // this pill is the actual tap target, not a large standalone mic circle.
        dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setGravity(Gravity.CENTER_VERTICAL);
        GradientDrawable dockBg = new GradientDrawable();
        dockBg.setColor(UiKit.COLOR_SURFACE);
        dockBg.setCornerRadius(999f);
        dock.setBackground(dockBg);
        dock.setElevation(UiKit.dp(this, 3));
        dock.setPadding(UiKit.dp(this, 8), UiKit.dp(this, 8), UiKit.dp(this, 20), UiKit.dp(this, 8));

        micBtn = UiKit.icon(this, R.drawable.ic_mic, 52, 0xFFFFFFFF);
        micBtn.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14));
        micBtn.setBackground(UiKit.circleGradientBg(this));
        micBtn.setOnClickListener(v -> onMicTapped());
        LinearLayout.LayoutParams micLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        micLp.rightMargin = UiKit.dp(this, 12);
        dock.addView(micBtn, micLp);

        stopBtn = UiKit.icon(this, R.drawable.ic_stop, 52, 0xFFFFFFFF);
        stopBtn.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14), UiKit.dp(this, 14));
        stopBtn.setBackground(UiKit.circleGradientBg(this));
        stopBtn.setOnClickListener(v -> handleStop());
        stopBtn.setVisibility(android.view.View.GONE);
        LinearLayout.LayoutParams stopLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        stopLp.rightMargin = UiKit.dp(this, 12);
        dock.addView(stopBtn, stopLp);

        typeInsteadTv = new TextView(this);
        typeInsteadTv.setText("Type instead");
        typeInsteadTv.setTextColor(UiKit.COLOR_PRIMARY);
        typeInsteadTv.setTypeface(null, android.graphics.Typeface.BOLD);
        typeInsteadTv.setPaintFlags(typeInsteadTv.getPaintFlags() | android.graphics.Paint.UNDERLINE_TEXT_FLAG);
        typeInsteadTv.setOnClickListener(v -> setShowTyped(true));
        dock.addView(typeInsteadTv, wrap());

        main.addView(dock, wrapWithMargins(0, 0, 0, UiKit.dp(this, 12)));

        typedRow = new LinearLayout(this);
        typedRow.setOrientation(LinearLayout.HORIZONTAL);
        typedRow.setGravity(Gravity.CENTER_VERTICAL);
        typedRow.setVisibility(android.view.View.GONE);

        typedInput = new EditText(this);
        typedInput.setHint("Type your question");
        GradientDrawable fieldBg = new GradientDrawable();
        fieldBg.setColor(UiKit.COLOR_SURFACE);
        fieldBg.setCornerRadius(UiKit.dp(this, 12));
        fieldBg.setStroke(UiKit.dp(this, 1), UiKit.COLOR_BORDER);
        typedInput.setBackground(fieldBg);
        typedInput.setPadding(UiKit.dp(this, 14), UiKit.dp(this, 10), UiKit.dp(this, 14), UiKit.dp(this, 10));
        typedRow.addView(typedInput, new LinearLayout.LayoutParams(UiKit.dp(this, 260), LinearLayout.LayoutParams.WRAP_CONTENT));

        android.widget.Button askBtn = UiKit.primaryButton(this, "Ask");
        askBtn.setOnClickListener(v -> handleTypedSubmit());
        LinearLayout.LayoutParams askLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        askLp.setMargins(UiKit.dp(this, 8), 0, UiKit.dp(this, 8), 0);
        typedRow.addView(askBtn, askLp);

        android.widget.Button useVoice = UiKit.ghostButton(this, "Use voice");
        useVoice.setOnClickListener(v -> setShowTyped(false));
        typedRow.addView(useVoice, wrap());

        main.addView(typedRow, wrapWithMargins(0, UiKit.dp(this, 8), 0, 0));

        android.widget.Button endBtn = UiKit.ghostButton(this, "I'm done - end session");
        endBtn.setOnClickListener(v -> endSession());
        main.addView(endBtn, wrapWithMargins(0, UiKit.dp(this, 20), 0, 0));

        root.addView(main, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        transcriptScroll = new ScrollView(this);
        transcriptContainer = new LinearLayout(this);
        transcriptContainer.setOrientation(LinearLayout.VERTICAL);
        transcriptEmptyTv = UiKit.muted(this, "Your conversation will appear here.");
        transcriptContainer.addView(transcriptEmptyTv, wrap());
        transcriptScroll.addView(transcriptContainer, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        root.addView(transcriptScroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        return root;
    }

    private void setShowTyped(boolean show) {
        showTyped = show;
        if (show) voiceModeActive = false; // typing opts back out of the hands-free voice loop
        typedRow.setVisibility(show ? android.view.View.VISIBLE : android.view.View.GONE);
        updateStatus();
    }

    private void handleStop() {
        voiceModeActive = false;
        conversation.stopSpeaking();
    }

    private android.graphics.drawable.Drawable circleBg(int color) {
        return UiKit.circleBg(this, color);
    }

    private void addTranscriptTurn(QATurn turn) {
        if (transcriptEmptyTv != null) {
            transcriptContainer.removeView(transcriptEmptyTv);
            transcriptEmptyTv = null;
        }
        TextView q = UiKit.body(this, turn.queryText);
        q.setTypeface(null, android.graphics.Typeface.BOLD);
        transcriptContainer.addView(q, wrapWithMargins(0, UiKit.dp(this, 8), 0, UiKit.dp(this, 2)));

        // Deflected answers get the same warning-tinted treatment as ChatActivity's transcript,
        // instead of rendering identically to an in-scope answer with no visual distinction.
        TextView a = turn.inScope ? UiKit.muted(this, turn.answerText) : UiKit.body(this, turn.answerText);
        if (!turn.inScope) {
            a.setTextColor(UiKit.COLOR_WARNING);
            GradientDrawable deflectedBg = new GradientDrawable();
            deflectedBg.setColor(UiKit.COLOR_WARNING_BG);
            deflectedBg.setCornerRadius(UiKit.dp(this, 10));
            a.setBackground(deflectedBg);
            a.setPadding(UiKit.dp(this, 10), UiKit.dp(this, 8), UiKit.dp(this, 10), UiKit.dp(this, 8));
        }
        transcriptContainer.addView(a, wrap());

        transcriptScroll.post(() -> transcriptScroll.fullScroll(android.view.View.FOCUS_DOWN));
    }

    private void updateStatus() {
        String text;
        if (speaking) text = "Speaking...";
        else if (recording) text = "Listening...";
        else if (submitting) text = "Thinking...";
        else text = "Tap the microphone to talk to me.";
        statusTv.setText(text);
        micBtn.setAlpha(submitting ? 0.5f : 1f);
        micBtn.setEnabled(!submitting);

        stopBtn.setVisibility(speaking ? android.view.View.VISIBLE : android.view.View.GONE);
        micBtn.setVisibility(!speaking && !showTyped ? android.view.View.VISIBLE : android.view.View.GONE);
        typeInsteadTv.setVisibility(!speaking && !showTyped ? android.view.View.VISIBLE : android.view.View.GONE);
        dock.setVisibility(showTyped ? android.view.View.GONE : android.view.View.VISIBLE);
    }

    // ---- Actions ----

    private void handleTypedSubmit() {
        String text = typedInput.getText().toString();
        if (text.trim().isEmpty() || submitting) return;
        voiceModeActive = false;
        typedInput.setText("");
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
            statusTv.setText("Voice input isn't available on this device. Please type your question.");
            return;
        }
        recording = true;
        micBtn.setBackground(circleBg(UiKit.COLOR_WARNING));
        updateStatus();
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
                micBtn.setBackground(UiKit.circleGradientBg(AvatarChatActivity.this));
                if (matches != null && !matches.isEmpty() && !matches.get(0).trim().isEmpty()) {
                    conversation.submit(matches.get(0), "voice");
                } else {
                    statusTv.setText("Couldn't understand that. Please try again or type your question.");
                    updateStatus();
                }
            }

            @Override
            public void onError(int error) {
                Log.w(TAG, "Speech error: " + error);
                recording = false;
                micBtn.setBackground(UiKit.circleGradientBg(AvatarChatActivity.this));
                if (error != SpeechRecognizer.ERROR_CLIENT) {
                    statusTv.setText("Microphone access was denied or is unavailable. Please type your question instead.");
                }
                updateStatus();
            }

            @Override public void onReadyForSpeech(Bundle p) {}
            @Override public void onBeginningOfSpeech() {}
            @Override public void onRmsChanged(float v) {}
            @Override public void onBufferReceived(byte[] b) {}
            @Override public void onEndOfSpeech() { statusTv.setText("Got it - one moment..."); }
            @Override public void onPartialResults(Bundle b) {}
            @Override public void onEvent(int t, Bundle b) {}
        });
    }

    private void endSession() {
        voiceModeActive = false;
        conversation.stopSpeaking();
        ApiClient.endSession(sessionId, new ApiClient.ApiCallback<Void>() {
            @Override public void onSuccess(Void result) { goToClosing(); }
            @Override public void onError(String message) {
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

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams wrapWithMargins(int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = wrap();
        lp.setMargins(l, t, r, b);
        return lp;
    }
}
