package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.aldebaran.qi.Future;
import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.builder.SayBuilder;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;
import com.aldebaran.qi.sdk.object.conversation.Say;

/**
 * Native port of frontend-app/src/screens/Welcome.tsx. Speaks the greeting via QiSDK Say as soon
 * as robot focus is gained (the web version speaks on mount via useTTS - Say is the on-robot
 * equivalent), then offers "Tell me about this medicine" or "Ask a question".
 */
public class WelcomeActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcWelcome";
    private static final String GREETING =
            "Hello! I am an AI assistant here to help you understand this medicine. I can tell you " +
            "what it is used for, how to take it, and any important warnings from the packaging. " +
            "I am not a pharmacist and cannot give personal health advice. Tap the microphone " +
            "button or type your question to get started. Or tap 'Tell me about this medicine' to " +
            "hear a full explanation.";

    private String sessionId;
    private String productDisplayName;
    private QiContext qiContext;
    private Future<Void> sayFuture;
    private boolean spoken = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sessionId = getIntent().getStringExtra("session_id");
        productDisplayName = getIntent().getStringExtra("product_display_name");
        setContentView(buildRoot());
        QiSDK.register(this, this);
    }

    @Override
    protected void onDestroy() {
        QiSDK.unregister(this, this);
        super.onDestroy();
    }

    @Override
    public void onRobotFocusGained(QiContext context) {
        this.qiContext = context;
        if (spoken) return;
        spoken = true;
        new Thread(() -> {
            try {
                Say say = SayBuilder.with(qiContext).withText(Speech.wrap(GREETING)).build();
                sayFuture = say.async().run();
                sayFuture.get();
            } catch (Exception e) {
                Log.d(TAG, "Greeting speech ended: " + e.getMessage());
            }
        }).start();
    }

    @Override
    public void onRobotFocusLost() {
        this.qiContext = null;
    }

    @Override
    public void onRobotFocusRefused(String reason) {
        Log.e(TAG, "Robot focus refused: " + reason);
    }

    private LinearLayout buildRoot() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        col.setBackgroundColor(UiKit.COLOR_BG);
        col.setPadding(UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40));

        TextView title = UiKit.heading(this, "Hello!");
        UiKit.center(title);
        col.addView(title, wrap());

        TextView lede = UiKit.body(this,
                "I'm here to help you understand this medicine - what it's used for, how to take it, " +
                "and any important warnings from the packaging.");
        UiKit.center(lede);
        col.addView(lede, wrapWithMaxWidth(UiKit.dp(this, 16), UiKit.dp(this, 8)));

        TextView muted = UiKit.muted(this, "I'm not a pharmacist and can't give personal health advice.");
        UiKit.center(muted);
        col.addView(muted, wrapWithMargins(0, 0, 0, UiKit.dp(this, 32)));

        android.widget.Button tellMeBtn = UiKit.primaryButton(this, "Tell me about this medicine");
        tellMeBtn.setOnClickListener(v -> {
            Intent intent = new Intent(this, CoreInfoActivity.class);
            intent.putExtra("session_id", sessionId);
            intent.putExtra("product_display_name", productDisplayName);
            startActivity(intent);
        });
        col.addView(tellMeBtn, wrapWithMaxWidth(0, UiKit.dp(this, 12)));

        android.widget.Button askBtn = UiKit.secondaryButton(this, "Ask a question");
        UiKit.setLeadingIcon(this, askBtn, R.drawable.ic_mic, UiKit.COLOR_PRIMARY);
        askBtn.setOnClickListener(v -> goToModeSelect());
        col.addView(askBtn, wrapWithMaxWidth(0, 0));

        return col;
    }

    private void goToModeSelect() {
        Intent intent = new Intent(this, ModeSelectActivity.class);
        intent.putExtra("session_id", sessionId);
        intent.putExtra("product_display_name", productDisplayName);
        startActivity(intent);
    }

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams wrapWithMargins(int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = wrap();
        lp.setMargins(l, t, r, b);
        return lp;
    }

    private LinearLayout.LayoutParams wrapWithMaxWidth(int marginTop, int marginBottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(UiKit.dp(this, 480), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, marginTop, 0, marginBottom);
        return lp;
    }
}
