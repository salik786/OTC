package com.otc.pepper;

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
 * Native port of frontend-app/src/screens/Closing.tsx. Kiosk sessions must be a dead end - the web
 * version traps the browser back button with history.pushState; the Android equivalent is
 * overriding onBackPressed() to swallow the back press outright, regardless of what activities are
 * still on the stack behind this one.
 */
public class ClosingActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcClosing";
    private static final String CLOSING_TEXT =
            "Thank you for using this system. I hope the information was helpful. The researcher " +
            "will now ask you a few questions. Goodbye!";

    private QiContext qiContext;
    private Future<Void> sayFuture;
    private boolean spoken = false;

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

    private LinearLayout buildRoot() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        col.setBackgroundColor(UiKit.COLOR_BG);
        col.setPadding(UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40), UiKit.dp(this, 40));

        TextView title = UiKit.heading(this, "Thank you");
        UiKit.center(title);
        col.addView(title, wrap());

        TextView lede = UiKit.body(this, CLOSING_TEXT);
        UiKit.center(lede);
        col.addView(lede, wrapWithMaxWidth(UiKit.dp(this, 16), UiKit.dp(this, 8)));

        TextView muted = UiKit.muted(this, "This session has ended.");
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
