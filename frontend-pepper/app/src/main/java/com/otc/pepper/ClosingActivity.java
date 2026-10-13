package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.widget.Button;
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
 * Native port of frontend-app/src/screens/Closing.tsx. Kiosk sessions must be a dead end for the
 * time it displays - the web version traps the browser back button with history.pushState; the
 * Android equivalent is overriding onBackPressed() to swallow the back press. It shows the
 * post-session survey QR code (long enough for the participant to scan it), then auto-resets to
 * the setup screen for the next participant (matching the tablet's handleResetToStart) - or
 * immediately via the Finish button - clearing the whole back stack so there's no way to navigate
 * back into the ended session.
 */
public class ClosingActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcClosing";
    private static final String CLOSING_TEXT =
            "Thank you for using this system. I hope the information was helpful. The researcher " +
            "will now ask you a few questions. Goodbye!";
    // Long enough to scan the survey QR code; the Finish button resets immediately instead.
    private static final long RESET_DELAY_MS = 120000;

    private QiContext qiContext;
    private Future<Void> sayFuture;
    private boolean spoken = false;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable resetRunnable = this::resetToStart;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildRoot());
        QiSDK.register(this, this);
        handler.postDelayed(resetRunnable, RESET_DELAY_MS);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(resetRunnable);
        QiSDK.unregister(this, this);
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        // Dead end by design - do not call super.onBackPressed().
    }

    @Override
    public void onRobotFocusGained(QiContext context) {
        this.qiContext = context;
        if (spoken) return;
        spoken = true;
        new Thread(() -> {
            try {
                Say say = SayBuilder.with(qiContext).withText(Speech.wrap(CLOSING_TEXT)).build();
                sayFuture = say.async().run();
                sayFuture.get();
            } catch (Exception e) {
                Log.d(TAG, "Closing speech ended: " + e.getMessage());
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

    private void resetToStart() {
        Intent intent = new Intent(this, ResearcherSetupActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(intent);
        finish();
    }

    private ScrollView buildRoot() {
        // Scrollable + fillViewport so content stays centered on a tall screen but is still
        // reachable on a short one (the QR block makes this screen taller than it used to be).
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(UiKit.COLOR_PRIMARY);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        col.setPadding(UiKit.dp(this, 40), UiKit.dp(this, 32), UiKit.dp(this, 40), UiKit.dp(this, 32));

        col.addView(UiKit.brandHeader(this, false, true), wrapWithMaxWidth(0, UiKit.dp(this, 16)));

        TextView title = UiKit.heading(this, "Thank you");
        title.setTextColor(0xFFFFFFFF);
        UiKit.center(title);
        col.addView(title, wrap());

        TextView lede = UiKit.body(this, CLOSING_TEXT);
        lede.setTextColor(0xFFFFFFFF);
        UiKit.center(lede);
        col.addView(lede, wrapWithMaxWidth(UiKit.dp(this, 12), UiKit.dp(this, 8)));

        TextView muted = new TextView(this);
        muted.setText("This session has ended.");
        muted.setTextColor(0xB3FFFFFF);
        muted.setTextSize(14);
        UiKit.center(muted);
        col.addView(muted, wrap());

        // Survey QR code on a white card (a QR needs a light quiet zone around it to scan).
        LinearLayout qrCard = new LinearLayout(this);
        qrCard.setOrientation(LinearLayout.VERTICAL);
        qrCard.setGravity(Gravity.CENTER_HORIZONTAL);
        GradientDrawable qrBg = new GradientDrawable();
        qrBg.setColor(0xFFFFFFFF);
        qrBg.setCornerRadius(UiKit.dp(this, 16));
        qrCard.setBackground(qrBg);
        qrCard.setPadding(UiKit.dp(this, 12), UiKit.dp(this, 12), UiKit.dp(this, 12), UiKit.dp(this, 10));

        ImageView qr = new ImageView(this);
        qr.setImageResource(R.drawable.qr_survey_pepper);
        qr.setAdjustViewBounds(true);
        qr.setContentDescription("QR code linking to the study survey");
        qrCard.addView(qr, new LinearLayout.LayoutParams(UiKit.dp(this, 190), UiKit.dp(this, 190)));

        TextView qrCaption = new TextView(this);
        qrCaption.setText("Scan this QR code to complete a short survey.");
        qrCaption.setTextColor(UiKit.COLOR_PRIMARY);
        qrCaption.setTextSize(13);
        qrCaption.setTypeface(null, android.graphics.Typeface.BOLD);
        UiKit.center(qrCaption);
        qrCard.addView(qrCaption, wrapWithMargins(0, UiKit.dp(this, 6), 0, 0));

        LinearLayout.LayoutParams qrLp = wrap();
        qrLp.topMargin = UiKit.dp(this, 16);
        col.addView(qrCard, qrLp);

        // Researcher-facing: skip the wait and go straight to a fresh session.
        Button finish = new Button(this);
        finish.setText("Finish");
        finish.setAllCaps(false);
        finish.setTextColor(0xFFFFFFFF);
        finish.setTypeface(null, android.graphics.Typeface.BOLD);
        GradientDrawable finishBg = new GradientDrawable();
        finishBg.setColor(0x00000000);
        finishBg.setCornerRadius(999f);
        finishBg.setStroke(UiKit.dp(this, 2), 0x99FFFFFF);
        finish.setBackground(finishBg);
        finish.setPadding(UiKit.dp(this, 32), UiKit.dp(this, 8), UiKit.dp(this, 32), UiKit.dp(this, 8));
        finish.setOnClickListener(v -> resetToStart());
        LinearLayout.LayoutParams finishLp = wrap();
        finishLp.topMargin = UiKit.dp(this, 16);
        col.addView(finish, finishLp);

        scroll.addView(col, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        return scroll;
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
