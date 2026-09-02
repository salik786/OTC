package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import com.aldebaran.qi.Future;
import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.builder.SayBuilder;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;
import com.aldebaran.qi.sdk.object.conversation.Say;

import java.util.ArrayList;
import java.util.List;

/**
 * Launcher / setup screen - native port of frontend-app/src/screens/ResearcherSetup.tsx, which
 * merged what used to be two separate screens (a researcher-only product picker, then a
 * participant-facing greeting) into one, matching what the tablet condition now shows. The
 * product list is fetched live from /api/products instead of hardcoded, so a medicine added via
 * the admin panel appears here automatically, the same way it does on the tablet.
 */
public class ResearcherSetupActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcResearcherSetup";
    private static final String GREETING =
            "Hello! I am an AI assistant here to help you understand this medicine. I can tell you " +
            "what it is used for, how to take it, and any important warnings from the packaging. " +
            "I am not a pharmacist and cannot give personal health advice. Tap the microphone " +
            "button or type your question to get started. Or tap 'Tell me about this medicine' to " +
            "hear a full explanation.";

    private QiContext qiContext;
    private TextView errorTv;
    private TextView loadErrorTv;
    private Spinner spinner;
    private Button tellMeBtn;
    private Button askBtn;
    private final List<ApiClient.Product> products = new ArrayList<>();
    private Future<Void> sayFuture;
    private boolean spoken = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildRoot());
        QiSDK.register(this, this);
        loadProducts();
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

    private ScrollView buildRoot() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackground(UiKit.screenBackground(this));

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        col.setPadding(UiKit.dp(this, 32), UiKit.dp(this, 40), UiKit.dp(this, 32), UiKit.dp(this, 32));

        col.addView(UiKit.brandHeader(this, false), wrapWithMaxWidth(0, UiKit.dp(this, 24)));

        LinearLayout card = UiKit.card(this);
        card.setOrientation(LinearLayout.VERTICAL);

        TextView title = UiKit.heading(this, "Hello!");
        card.addView(title, wrapWithMargins(0, 0, 0, UiKit.dp(this, 8)));

        TextView lede = UiKit.body(this,
                "I'm here to help you understand this medicine - what it's used for, how to take it, " +
                "and any important warnings from the packaging.");
        card.addView(lede, wrapWithMargins(0, 0, 0, UiKit.dp(this, 20)));

        LinearLayout labelRow = new LinearLayout(this);
        labelRow.setOrientation(LinearLayout.HORIZONTAL);
        labelRow.setGravity(Gravity.CENTER_VERTICAL);
        ImageView labelIcon = UiKit.iconBadge(this, R.drawable.ic_capsule, 28, UiKit.COLOR_BG_MINT, UiKit.COLOR_PRIMARY);
        LinearLayout.LayoutParams labelIconLp = (LinearLayout.LayoutParams) labelIcon.getLayoutParams();
        labelIconLp.rightMargin = UiKit.dp(this, 8);
        labelRow.addView(labelIcon);
        TextView label = new TextView(this);
        label.setText("Medicine on the counter");
        label.setTextColor(UiKit.COLOR_TEXT);
        label.setTypeface(null, android.graphics.Typeface.BOLD);
        label.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 16);
        labelRow.addView(label);
        card.addView(labelRow, wrapWithMargins(0, 0, 0, UiKit.dp(this, 8)));

        spinner = new Spinner(this);
        android.graphics.drawable.GradientDrawable spinnerBg = new android.graphics.drawable.GradientDrawable();
        spinnerBg.setColor(UiKit.COLOR_SURFACE);
        spinnerBg.setStroke(UiKit.dp(this, 2), UiKit.COLOR_BORDER);
        spinnerBg.setCornerRadius(UiKit.dp(this, 12));
        spinner.setBackground(spinnerBg);
        spinner.setPadding(UiKit.dp(this, 16), UiKit.dp(this, 12), UiKit.dp(this, 16), UiKit.dp(this, 12));
        LinearLayout.LayoutParams spinnerLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        spinnerLp.bottomMargin = UiKit.dp(this, 20);
        card.addView(spinner, spinnerLp);

        loadErrorTv = UiKit.errorText(this, "Loading medicines...");
        card.addView(loadErrorTv, wrapWithMargins(0, 0, 0, UiKit.dp(this, 12)));

        errorTv = UiKit.errorText(this, "");
        errorTv.setVisibility(View.GONE);
        card.addView(errorTv, wrapWithMargins(0, 0, 0, UiKit.dp(this, 12)));

        tellMeBtn = UiKit.primaryButton(this, "Tell me about this medicine");
        UiKit.setLeadingIcon(this, tellMeBtn, R.drawable.ic_sparkle, 0xFFFFFFFF);
        tellMeBtn.setEnabled(false);
        tellMeBtn.setOnClickListener(v -> onTellMe());
        card.addView(tellMeBtn, wrapWithMargins(0, 0, 0, UiKit.dp(this, 12)));

        askBtn = UiKit.secondaryButton(this, "Ask a question");
        UiKit.setLeadingIcon(this, askBtn, R.drawable.ic_question, UiKit.COLOR_PRIMARY);
        askBtn.setEnabled(false);
        askBtn.setOnClickListener(v -> onAskQuestion());
        card.addView(askBtn, wrapWithMargins(0, 0, 0, UiKit.dp(this, 16)));

        LinearLayout disclaimerRow = new LinearLayout(this);
        disclaimerRow.setOrientation(LinearLayout.HORIZONTAL);
        ImageView infoIcon = UiKit.iconBadge(this, R.drawable.ic_info, 20, UiKit.COLOR_BG_MINT, UiKit.COLOR_PRIMARY);
        LinearLayout.LayoutParams infoIconLp = (LinearLayout.LayoutParams) infoIcon.getLayoutParams();
        infoIconLp.rightMargin = UiKit.dp(this, 8);
        infoIconLp.topMargin = UiKit.dp(this, 2);
        disclaimerRow.addView(infoIcon);
        TextView disclaimer = UiKit.muted(this, "I'm not a pharmacist and can't give personal health advice.");
        disclaimerRow.addView(disclaimer, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        card.addView(disclaimerRow);

        col.addView(card, wrapWithMaxWidth(0, 0));
        scroll.addView(col, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        return scroll;
    }

    /** A single failed request here used to strand the screen permanently, needing an app
     * restart to recover - too easy to trip from a brief backend hiccup (e.g. a Render redeploy
     * restarting the server). Retries twice with backoff before giving up, matching
     * frontend-app/src/screens/ResearcherSetup.tsx's fix; loadErrorTv becomes tappable to retry
     * again once it does give up. */
    private void loadProducts() {
        loadProductsAttempt(0);
    }

    private void loadProductsAttempt(int attempt) {
        ApiClient.listProducts(new ApiClient.ApiCallback<List<ApiClient.Product>>() {
            @Override
            public void onSuccess(List<ApiClient.Product> result) {
                runOnUiThread(() -> {
                    loadErrorTv.setOnClickListener(null);
                    products.clear();
                    products.addAll(result);
                    if (products.isEmpty()) {
                        loadErrorTv.setText("No medicines are set up yet. Ask a researcher to upload one in the admin panel.");
                        loadErrorTv.setVisibility(View.VISIBLE);
                        return;
                    }
                    loadErrorTv.setVisibility(View.GONE);
                    List<String> labels = new ArrayList<>();
                    for (ApiClient.Product p : products) labels.add(p.displayName);
                    ArrayAdapter<String> adapter = new ArrayAdapter<>(
                            ResearcherSetupActivity.this, android.R.layout.simple_spinner_item, labels);
                    adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    spinner.setAdapter(adapter);
                    tellMeBtn.setEnabled(true);
                    askBtn.setEnabled(true);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    Log.e(TAG, "listProducts failed (attempt " + attempt + "): " + message);
                    if (attempt < 2) {
                        loadErrorTv.getHandler().postDelayed(
                                () -> loadProductsAttempt(attempt + 1), 1000L * (attempt + 1));
                        return;
                    }
                    loadErrorTv.setText("Could not load the medicine list. Check the connection and tap to try again.");
                    loadErrorTv.setVisibility(View.VISIBLE);
                    loadErrorTv.setOnClickListener(v -> {
                        loadErrorTv.setText("Loading medicines...");
                        loadErrorTv.setOnClickListener(null);
                        loadProductsAttempt(0);
                    });
                });
            }
        });
    }

    private String selectedSlug() {
        int pos = spinner.getSelectedItemPosition();
        if (pos < 0 || pos >= products.size()) return null;
        return products.get(pos).slug;
    }

    private void onTellMe() {
        startSessionThen(CoreInfoActivity.class, tellMeBtn, "Tell me about this medicine");
    }

    private void onAskQuestion() {
        startSessionThen(ModeSelectActivity.class, askBtn, "Ask a question");
    }

    private void startSessionThen(Class<?> next, Button triggerBtn, String originalLabel) {
        String slug = selectedSlug();
        if (slug == null) return;
        errorTv.setVisibility(View.GONE);
        tellMeBtn.setEnabled(false);
        askBtn.setEnabled(false);
        triggerBtn.setText("Starting...");
        ApiClient.startSession(slug, new ApiClient.ApiCallback<ApiClient.SessionStartResponse>() {
            @Override
            public void onSuccess(ApiClient.SessionStartResponse result) {
                runOnUiThread(() -> {
                    Intent intent = new Intent(ResearcherSetupActivity.this, next);
                    intent.putExtra("session_id", result.sessionId);
                    intent.putExtra("product_display_name", result.productDisplayName);
                    startActivity(intent);
                    triggerBtn.setText(originalLabel);
                    tellMeBtn.setEnabled(true);
                    askBtn.setEnabled(true);
                });
            }

            @Override
            public void onError(String message) {
                runOnUiThread(() -> {
                    Log.e(TAG, "startSession failed: " + message);
                    errorTv.setText("Could not start a session. Check the connection and try again.");
                    errorTv.setVisibility(View.VISIBLE);
                    triggerBtn.setText(originalLabel);
                    tellMeBtn.setEnabled(true);
                    askBtn.setEnabled(true);
                });
            }
        });
    }

    private LinearLayout.LayoutParams wrapWithMargins(int l, int t, int r, int b) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(l, t, r, b);
        return lp;
    }

    private LinearLayout.LayoutParams wrapWithMaxWidth(int marginTop, int marginBottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(UiKit.dp(this, 480), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, marginTop, 0, marginBottom);
        return lp;
    }
}
