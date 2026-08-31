package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;

import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;

/**
 * Launcher screen - native port of frontend-app/src/screens/ResearcherSetup.tsx. Not participant
 * facing: the researcher picks which medicine is on the counter, then starts a session. Every
 * Activity in this app registers with QiSDK (matching every screen in the Interledger reference
 * app, including its non-speaking HomeActivity) so the robot holds focus and doesn't drop into
 * autonomous life behaviors between screens.
 */
public class ResearcherSetupActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcResearcherSetup";
    private static final String[] PRODUCT_SLUGS = {"paracetamol", "multivitamin"};
    private static final String[] PRODUCT_LABELS = {"Paracetamol", "Multivitamin"};

    private QiContext qiContext;
    private TextView errorTv;
    private String selectedSlug = PRODUCT_SLUGS[0];

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
    }

    @Override
    public void onRobotFocusLost() {
        this.qiContext = null;
    }

    @Override
    public void onRobotFocusRefused(String reason) {
        Log.e(TAG, "Robot focus refused: " + reason);
    }

    private ScrollView buildRoot() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(UiKit.COLOR_BG);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        col.setPadding(UiKit.dp(this, 32), UiKit.dp(this, 48), UiKit.dp(this, 32), UiKit.dp(this, 32));

        LinearLayout card = UiKit.card(this);
        card.setOrientation(LinearLayout.VERTICAL);

        TextView badge = UiKit.label(this, "RESEARCHER SETUP — NOT PARTICIPANT FACING");
        card.addView(badge);

        TextView title = UiKit.heading(this, "Start a session");
        addMargin(title, 0, UiKit.dp(this, 12), 0, UiKit.dp(this, 8));
        card.addView(title);

        TextView subtitle = UiKit.muted(this,
                "Place the matching medicine box on the counter before starting. The participant will only see information about the product selected here.");
        addMargin(subtitle, 0, 0, 0, UiKit.dp(this, 20));
        card.addView(subtitle);

        RadioGroup group = new RadioGroup(this);
        group.setOrientation(RadioGroup.VERTICAL);
        for (int i = 0; i < PRODUCT_SLUGS.length; i++) {
            RadioButton rb = new RadioButton(this);
            rb.setText(PRODUCT_LABELS[i]);
            rb.setTextSize(16);
            rb.setTextColor(UiKit.COLOR_TEXT);
            rb.setPadding(0, UiKit.dp(this, 6), 0, UiKit.dp(this, 6));
            rb.setId(i + 1);
            if (i == 0) rb.setChecked(true);
            group.addView(rb);
        }
        group.setOnCheckedChangeListener((g, checkedId) -> selectedSlug = PRODUCT_SLUGS[checkedId - 1]);
        addMargin(group, 0, 0, 0, UiKit.dp(this, 20));
        card.addView(group);

        errorTv = UiKit.errorText(this, "");
        errorTv.setVisibility(android.view.View.GONE);
        addMargin(errorTv, 0, 0, 0, UiKit.dp(this, 12));
        card.addView(errorTv);

        android.widget.Button startBtn = UiKit.primaryButton(this, "Start Session");
        startBtn.setOnClickListener(v -> onStart(startBtn));
        LinearLayout.LayoutParams btnLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        card.addView(startBtn, btnLp);

        LinearLayout.LayoutParams cardLp = new LinearLayout.LayoutParams(
                UiKit.dp(this, 480), LinearLayout.LayoutParams.WRAP_CONTENT);
        col.addView(card, cardLp);
        scroll.addView(col, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        return scroll;
    }

    private void onStart(android.widget.Button startBtn) {
        errorTv.setVisibility(android.view.View.GONE);
        startBtn.setEnabled(false);
        startBtn.setText("Starting...");
        ApiClient.startSession(selectedSlug, new ApiClient.ApiCallback<ApiClient.SessionStartResponse>() {
            @Override
            public void onSuccess(ApiClient.SessionStartResponse result) {
                runOnUiThread(() -> {
                    Intent intent = new Intent(ResearcherSetupActivity.this, WelcomeActivity.class);
                    intent.putExtra("session_id", result.sessionId);
                    intent.putExtra("product_display_name", result.productDisplayName);
                    startActivity(intent);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    Log.e(TAG, "startSession failed: " + message);
                    errorTv.setText("Could not start a session. Check the connection and try again.");
                    errorTv.setVisibility(android.view.View.VISIBLE);
                    startBtn.setEnabled(true);
                    startBtn.setText("Start Session");
                });
            }
        });
    }

    private static void addMargin(android.view.View v, int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(l, t, r, b);
        v.setLayoutParams(lp);
    }
}
