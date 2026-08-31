package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.aldebaran.qi.Future;
import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.builder.SayBuilder;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;
import com.aldebaran.qi.sdk.object.conversation.Say;

/**
 * Native port of frontend-app/src/screens/CoreInfo.tsx. Fetches /api/core-info on load, renders
 * the structured leaflet summary, and speaks full_text via QiSDK Say once robot focus is ready.
 */
public class CoreInfoActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcCoreInfo";

    private String sessionId;
    private String productDisplayName;
    private QiContext qiContext;
    private Future<Void> sayFuture;

    private LinearLayout contentContainer;
    private ApiClient.CoreInfoResponse pendingSpeak;
    private boolean spoken = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sessionId = getIntent().getStringExtra("session_id");
        productDisplayName = getIntent().getStringExtra("product_display_name");
        setContentView(buildRoot());
        QiSDK.register(this, this);
        loadCoreInfo();
    }

    @Override
    protected void onDestroy() {
        QiSDK.unregister(this, this);
        super.onDestroy();
    }

    @Override
    public void onRobotFocusGained(QiContext context) {
        this.qiContext = context;
        if (!spoken && pendingSpeak != null) speakFullText(pendingSpeak.fullText);
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

        contentContainer = new LinearLayout(this);
        contentContainer.setOrientation(LinearLayout.VERTICAL);
        contentContainer.setGravity(Gravity.CENTER_HORIZONTAL);
        contentContainer.setPadding(UiKit.dp(this, 32), UiKit.dp(this, 40), UiKit.dp(this, 32), UiKit.dp(this, 32));

        TextView loading = UiKit.muted(this, "Loading information about " + productDisplayName + "...");
        contentContainer.addView(loading, wrap());

        scroll.addView(contentContainer, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        return scroll;
    }

    private void loadCoreInfo() {
        ApiClient.coreInfo(sessionId, new ApiClient.ApiCallback<ApiClient.CoreInfoResponse>() {
            @Override
            public void onSuccess(ApiClient.CoreInfoResponse result) {
                runOnUiThread(() -> {
                    renderInfo(result);
                    pendingSpeak = result;
                    if (qiContext != null && !spoken) speakFullText(result.fullText);
                });
            }

            @Override
            public void onError(String message) {
                Log.e(TAG, "coreInfo failed: " + message);
                runOnUiThread(() -> {
                    contentContainer.removeAllViews();
                    contentContainer.addView(
                            UiKit.errorText(CoreInfoActivity.this, "Could not load information about this medicine. Please tell the researcher."),
                            wrap());
                });
            }
        });
    }

    private void speakFullText(String text) {
        spoken = true;
        new Thread(() -> {
            try {
                Say say = SayBuilder.with(qiContext).withText(Speech.wrap(text)).build();
                sayFuture = say.async().run();
                sayFuture.get();
            } catch (Exception e) {
                Log.d(TAG, "Core info speech ended: " + e.getMessage());
            }
        }).start();
    }

    private void renderInfo(ApiClient.CoreInfoResponse data) {
        contentContainer.removeAllViews();

        LinearLayout card = UiKit.card(this);
        card.setOrientation(LinearLayout.VERTICAL);

        card.addView(UiKit.heading(this, data.productName), wrapWithMargins(0, 0, 0, UiKit.dp(this, 16)));

        addRow(card, "Used for", data.usedFor);
        addRow(card, "Dose", data.dose);
        addRow(card, "Frequency", data.frequency);
        addRow(card, "Max in 24 hours", data.maxDose24h);

        if (!data.warnings.isEmpty()) {
            card.addView(UiKit.label(this, "WARNINGS"), wrapWithMargins(0, UiKit.dp(this, 12), 0, UiKit.dp(this, 6)));
            for (String w : data.warnings) {
                card.addView(UiKit.body(this, "•  " + w), wrapWithMargins(0, 0, 0, UiKit.dp(this, 6)));
            }
        }

        TextView prompt = UiKit.body(this, "Do you have any questions?");
        card.addView(prompt, wrapWithMargins(0, UiKit.dp(this, 20), 0, UiKit.dp(this, 12)));

        android.widget.Button askBtn = UiKit.primaryButton(this, "Ask a question");
        askBtn.setOnClickListener(v -> {
            Intent intent = new Intent(this, ModeSelectActivity.class);
            intent.putExtra("session_id", sessionId);
            intent.putExtra("product_display_name", productDisplayName);
            startActivity(intent);
        });
        card.addView(askBtn, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        contentContainer.addView(card, new LinearLayout.LayoutParams(
                UiKit.dp(this, 560), LinearLayout.LayoutParams.WRAP_CONTENT));
    }

    private void addRow(LinearLayout parent, String labelText, String value) {
        if (value == null || value.isEmpty()) return;
        parent.addView(UiKit.label(this, labelText.toUpperCase()), wrapWithMargins(0, UiKit.dp(this, 10), 0, UiKit.dp(this, 2)));
        parent.addView(UiKit.body(this, value), wrap());
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
