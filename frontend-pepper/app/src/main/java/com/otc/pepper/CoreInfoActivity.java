package com.otc.pepper;

import android.content.Intent;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.widget.ImageView;
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
 * the structured leaflet summary as icon-labeled cards (matching the tablet's redesign), and
 * speaks full_text via QiSDK Say once robot focus is ready.
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
        scroll.setBackground(UiKit.screenBackground());

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(UiKit.dp(this, 16), UiKit.dp(this, 16), UiKit.dp(this, 16), UiKit.dp(this, 16));
        LinearLayout.LayoutParams topNavLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        topNavLp.bottomMargin = UiKit.dp(this, 16);
        root.addView(UiKit.topNav(this, v -> finish()), topNavLp);

        contentContainer = new LinearLayout(this);
        contentContainer.setOrientation(LinearLayout.VERTICAL);
        contentContainer.setGravity(Gravity.CENTER_HORIZONTAL);

        TextView loading = UiKit.muted(this, "Loading information about " + productDisplayName + "...");
        contentContainer.addView(loading, wrap());

        root.addView(contentContainer, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));
        scroll.addView(root, new ScrollView.LayoutParams(
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

        LinearLayout headingRow = new LinearLayout(this);
        headingRow.setOrientation(LinearLayout.HORIZONTAL);
        headingRow.setGravity(Gravity.CENTER_VERTICAL);
        ImageView pillIcon = UiKit.iconBadge(this, R.drawable.ic_capsule, 48, UiKit.COLOR_BG_MINT, UiKit.COLOR_PRIMARY);
        LinearLayout.LayoutParams pillIconLp = (LinearLayout.LayoutParams) pillIcon.getLayoutParams();
        pillIconLp.rightMargin = UiKit.dp(this, 12);
        headingRow.addView(pillIcon);
        headingRow.addView(UiKit.heading(this, data.productName), wrap());
        card.addView(headingRow, wrapWithMargins(0, 0, 0, UiKit.dp(this, 16)));

        addRow(card, R.drawable.ic_target, "Used for", data.usedFor, UiKit.COLOR_BG_MINT);
        addRow(card, R.drawable.ic_dose, "Dose", data.dose, UiKit.COLOR_BG_MINT);
        addRow(card, R.drawable.ic_clock, "Frequency", data.frequency, UiKit.COLOR_BG_MINT);
        addRow(card, R.drawable.ic_warning, "Max in 24 hours", data.maxDose24h, UiKit.COLOR_MAX_DOSE_BG);

        if (!data.warnings.isEmpty()) {
            LinearLayout warnBlock = new LinearLayout(this);
            warnBlock.setOrientation(LinearLayout.VERTICAL);
            GradientDrawable warnBg = new GradientDrawable();
            warnBg.setColor(UiKit.COLOR_WARNING_BG);
            warnBlock.setBackground(warnBg);
            warnBlock.setPadding(UiKit.dp(this, 12), UiKit.dp(this, 12), UiKit.dp(this, 12), UiKit.dp(this, 12));

            LinearLayout warnHeading = new LinearLayout(this);
            warnHeading.setOrientation(LinearLayout.HORIZONTAL);
            warnHeading.setGravity(Gravity.CENTER_VERTICAL);
            ImageView warnIcon = UiKit.icon(this, R.drawable.ic_warning, 18, UiKit.COLOR_WARNING);
            LinearLayout.LayoutParams warnIconLp = (LinearLayout.LayoutParams) warnIcon.getLayoutParams();
            warnIconLp.rightMargin = UiKit.dp(this, 6);
            warnHeading.addView(warnIcon);
            TextView warnTitle = new TextView(this);
            warnTitle.setText("Warnings");
            warnTitle.setTextColor(UiKit.COLOR_WARNING);
            warnTitle.setTypeface(null, android.graphics.Typeface.BOLD);
            warnHeading.addView(warnTitle);
            warnBlock.addView(warnHeading, wrapWithMargins(0, 0, 0, UiKit.dp(this, 6)));

            for (String w : data.warnings) {
                warnBlock.addView(UiKit.body(this, "•  " + w), wrapWithMargins(0, 0, 0, UiKit.dp(this, 4)));
            }
            card.addView(warnBlock, wrapWithMargins(0, UiKit.dp(this, 8), 0, UiKit.dp(this, 8)));
        }

        LinearLayout footerNote = new LinearLayout(this);
        footerNote.setOrientation(LinearLayout.HORIZONTAL);
        GradientDrawable footerBg = new GradientDrawable();
        footerBg.setColor(UiKit.COLOR_BG_MINT);
        footerBg.setCornerRadius(UiKit.dp(this, 12));
        footerNote.setBackground(footerBg);
        footerNote.setPadding(UiKit.dp(this, 10), UiKit.dp(this, 10), UiKit.dp(this, 10), UiKit.dp(this, 10));
        ImageView footerIcon = UiKit.icon(this, R.drawable.ic_info, 14, UiKit.COLOR_PRIMARY);
        LinearLayout.LayoutParams footerIconLp = (LinearLayout.LayoutParams) footerIcon.getLayoutParams();
        footerIconLp.rightMargin = UiKit.dp(this, 8);
        footerNote.addView(footerIcon);
        TextView footerText = UiKit.muted(this, "Always read the label and follow the instructions on the packaging.");
        footerNote.addView(footerText, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        card.addView(footerNote, wrapWithMargins(0, UiKit.dp(this, 4), 0, UiKit.dp(this, 12)));

        TextView prompt = UiKit.body(this, "Do you have any questions?");
        card.addView(prompt, wrapWithMargins(0, 0, 0, UiKit.dp(this, 12)));

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

    private void addRow(LinearLayout parent, int iconRes, String labelText, String value, int badgeColor) {
        if (value == null || value.isEmpty()) return;
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        GradientDrawable rowBg = new GradientDrawable();
        rowBg.setColor(badgeColor);
        rowBg.setCornerRadius(UiKit.dp(this, 12));
        row.setBackground(rowBg);
        row.setPadding(UiKit.dp(this, 10), UiKit.dp(this, 10), UiKit.dp(this, 10), UiKit.dp(this, 10));

        ImageView icon = UiKit.icon(this, iconRes, 18, UiKit.COLOR_PRIMARY);
        LinearLayout.LayoutParams iconLp = (LinearLayout.LayoutParams) icon.getLayoutParams();
        iconLp.rightMargin = UiKit.dp(this, 10);
        iconLp.topMargin = UiKit.dp(this, 2);
        row.addView(icon);

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.addView(UiKit.label(this, labelText.toUpperCase()), wrap());
        body.addView(UiKit.body(this, value), wrap());
        row.addView(body, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

        parent.addView(row, wrapWithMargins(0, 0, 0, UiKit.dp(this, 8)));
    }

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams wrapWithMargins(int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(l, t, r, b);
        return lp;
    }
}
