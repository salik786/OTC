package com.otc.pepper;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.QiSDK;
import com.aldebaran.qi.sdk.RobotLifecycleCallbacks;
import com.aldebaran.qi.sdk.design.activity.RobotActivity;

/** Native port of frontend-app/src/screens/ModeSelect.tsx. */
public class ModeSelectActivity extends RobotActivity implements RobotLifecycleCallbacks {

    private static final String TAG = "OtcModeSelect";
    private String sessionId;
    private String productDisplayName;
    private QiContext qiContext;

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
    }

    @Override
    public void onRobotFocusLost() {
        this.qiContext = null;
    }

    @Override
    public void onRobotFocusRefused(String reason) {
        Log.e(TAG, "Robot focus refused: " + reason);
    }

    // Not scrollable before this pass - on a shorter real screen than this was originally tested
    // on, the two mode cards (or the space below them) could end up genuinely below the visible
    // area with no way to reach them, since a plain LinearLayout doesn't clip-and-hide gracefully,
    // it just extends off-screen. Wrapping in a ScrollView (same pattern already used on
    // ResearcherSetupActivity for the same reason) means content is always reachable regardless of
    // screen height, at the cost of nothing when it already fit.
    private ScrollView buildRoot() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackground(UiKit.screenBackground(this));

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);
        col.setPadding(UiKit.dp(this, 24), UiKit.dp(this, 16), UiKit.dp(this, 24), UiKit.dp(this, 24));

        LinearLayout.LayoutParams topNavLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        topNavLp.bottomMargin = UiKit.dp(this, 24);
        col.addView(UiKit.topNav(this, v -> finish()), topNavLp);

        TextView title = UiKit.heading(this, "How would you like to ask?");
        UiKit.center(title);
        col.addView(title, wrap());

        TextView lede = UiKit.body(this, "Choose whichever feels more comfortable - you can talk or type either way.");
        UiKit.center(lede);
        col.addView(lede, wrapWithMargins(0, UiKit.dp(this, 12), 0, UiKit.dp(this, 32)));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);

        row.addView(modeCard(R.drawable.ic_chat, "Voice & Text Chat", "See your conversation as you go, type or talk anytime.",
                        v -> goTo(ChatActivity.class)),
                cardParams());
        row.addView(modeCard(R.drawable.ic_mic, "Talk to the Assistant", "A friendly assistant you can speak with directly.",
                        v -> goTo(AvatarChatActivity.class)),
                cardParams());

        col.addView(row, wrap());

        scroll.addView(col, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        return scroll;
    }

    private LinearLayout modeCard(int iconRes, String title, String desc, android.view.View.OnClickListener onClick) {
        LinearLayout card = UiKit.card(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setClickable(true);
        card.setOnClickListener(onClick);
        UiKit.addCardRipple(this, card);

        android.widget.ImageView iconView = UiKit.iconBadge(this, iconRes, 56, UiKit.COLOR_BG_MINT, UiKit.COLOR_PRIMARY);
        ((LinearLayout.LayoutParams) iconView.getLayoutParams()).setMargins(0, 0, 0, UiKit.dp(this, 8));
        card.addView(iconView);

        TextView titleTv = UiKit.body(this, title);
        titleTv.setTypeface(null, android.graphics.Typeface.BOLD);
        UiKit.center(titleTv);
        card.addView(titleTv, wrapWithMargins(0, UiKit.dp(this, 8), 0, UiKit.dp(this, 4)));

        TextView descTv = UiKit.muted(this, desc);
        UiKit.center(descTv);
        card.addView(descTv, wrap());

        return card;
    }

    private void goTo(Class<?> activity) {
        Intent intent = new Intent(this, activity);
        intent.putExtra("session_id", sessionId);
        intent.putExtra("product_display_name", productDisplayName);
        startActivity(intent);
    }

    private LinearLayout.LayoutParams cardParams() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(UiKit.dp(this, 260), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(UiKit.dp(this, 8), 0, UiKit.dp(this, 8), 0);
        return lp;
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
