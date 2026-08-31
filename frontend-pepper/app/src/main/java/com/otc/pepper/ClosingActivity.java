package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
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
 * Native port of frontend-app/src/screens/Closing.tsx. Kiosk sessions must be a dead end for the
 * ~4s it displays - the web version traps the browser back button with history.pushState; the
 * Android equivalent is overriding onBackPressed() to swallow the back press. After that window,
 * it auto-resets to the setup screen for the next participant (matching the tablet's
 * handleResetToStart), clearing the whole back stack so there's no way to navigate back into the
 * ended session - previously this was a genuine dead end with no way back to a fresh session
 * short of force-closing the app.
 */
public class ClosingActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcClosing";
    private static final String CLOSING_TEXT =
            "Thank you for using this system. I hope the information was helpful. The researcher " +
            "will now ask you a few questions. Goodbye!";
    private static final long RESET_DELAY_MS = 4000;

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

    private LinearLayout buildRoot() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        col.setBackgroundColor(UiKit.COLOR_PRIMARY);
        col.setPadding(UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40));

        col.addView(UiKit.brandHeader(this, false, true), wrapWithMaxWidth(0, UiKit.dp(this, 24)));

        TextView title = UiKit.heading(this, "Thank you");
        title.setTextColor(0xFFFFFFFF);
        UiKit.center(title);
        col.addView(title, wrap());

        TextView lede = UiKit.body(this, CLOSING_TEXT);
        lede.setTextColor(0xFFFFFFFF);
        UiKit.center(lede);
        col.addView(lede, wrapWithMaxWidth(UiKit.dp(this, 16), UiKit.dp(this, 8)));

        TextView muted = new TextView(this);
        muted.setText("This session has ended.");
        muted.setTextColor(0xB3FFFFFF);
        muted.setTextSize(14);
        UiKit.center(muted);
        col.addView(muted, wrap());

        return col;
    }

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams wrapWithMaxWidth(int marginTop, int marginBottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(UiKit.dp(this, 480), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, marginTop, 0, marginBottom);
        return lp;
    }
}
