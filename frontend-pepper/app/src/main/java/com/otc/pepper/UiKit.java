package com.otc.pepper;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.graphics.drawable.RippleDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.core.content.ContextCompat;

/**
 * Small shared styling helpers so every screen looks consistent without repeating drawable/button
 * boilerplate in each Activity. Colors/theme match frontend-app's "MedCheck" rebrand (see
 * frontend-app/src/styles/tokens.css and app.css) so the Pepper app reads as the same product for
 * the study's condition comparison, not a re-skin - mint gradient background, teal gradient pill
 * buttons, rounded gradient cards with a soft shadow.
 */
final class UiKit {
    private UiKit() {}

    static final int COLOR_PRIMARY = 0xFF1F4C46;
    static final int COLOR_PRIMARY_LIGHT = 0xFF2E6960;
    static final int COLOR_PRIMARY_DARK = 0xFF163731;
    static final int COLOR_ACCENT = 0xFFB98639;
    static final int COLOR_ACCENT_DARK = 0xFF93692B;
    static final int COLOR_WARNING = 0xFF9C3B32;
    static final int COLOR_WARNING_BG = 0xFFFBECEB;
    static final int COLOR_MAX_DOSE_BG = 0xFFFDF3E6;
    static final int COLOR_BG = 0xFFEEF7F4;
    static final int COLOR_BG_MINT = 0xFFE3F3EE;
    static final int COLOR_SURFACE = 0xFFFFFFFF;
    static final int COLOR_TEXT = 0xFF14201E;
    static final int COLOR_TEXT_MUTED = 0xFF4A5A57;
    static final int COLOR_BORDER = 0xFFD8D3C8;
    static final int COLOR_ON_PRIMARY = 0xFFFFFFFF;

    static int dp(Context ctx, int value) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, ctx.getResources().getDisplayMetrics());
    }

    /** The app's mint gradient background PLUS the same faint scattered medical-icon watermark
     * (heartbeat squiggle, bandage cross, capsule, footsteps, checkmark circle) as
     * frontend-app/src/styles/tokens.css's tiled SVG - apply to every screen's root view so the
     * whole app reads as one consistent "MedCheck" surface instead of a flat gradient with no
     * texture. Needs a Context to render the repeating tile as a bitmap (Android's VectorDrawable
     * has no built-in tile mode, unlike a CSS background-image). */
    static Drawable screenBackground(Context ctx) {
        GradientDrawable gradient = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{0xFFE9F5F1, COLOR_BG, 0xFFEFF6F1});

        Bitmap tileBmp = buildWatermarkTile(ctx);
        BitmapDrawable tile = new BitmapDrawable(ctx.getResources(), tileBmp);
        tile.setTileModeXY(Shader.TileMode.REPEAT, Shader.TileMode.REPEAT);

        return new LayerDrawable(new Drawable[]{gradient, tile});
    }

    private static Bitmap buildWatermarkTile(Context ctx) {
        int size = dp(ctx, 220);
        Bitmap bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);

        Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setColor(COLOR_PRIMARY);
        stroke.setAlpha(16);
        stroke.setStrokeWidth(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 1.4f, ctx.getResources().getDisplayMetrics()));
        stroke.setStrokeCap(Paint.Cap.ROUND);

        float s = size / 160f; // scale factor so the hand-tuned coordinates below stay proportional

        // Heartbeat squiggle, top-left.
        Path heartbeat = new Path();
        heartbeat.moveTo(4 * s, 30 * s);
        heartbeat.lineTo(24 * s, 30 * s);
        heartbeat.lineTo(30 * s, 18 * s);
        heartbeat.lineTo(36 * s, 42 * s);
        heartbeat.lineTo(42 * s, 26 * s);
        heartbeat.lineTo(48 * s, 30 * s);
        heartbeat.lineTo(70 * s, 30 * s);
        c.drawPath(heartbeat, stroke);

        // Bandage cross, top-right.
        c.drawCircle(130 * s, 24 * s, 10 * s, stroke);
        c.drawLine(130 * s, 16 * s, 130 * s, 32 * s, stroke);
        c.drawLine(122 * s, 24 * s, 138 * s, 24 * s, stroke);

        // Capsule, mid-left, rotated.
        c.save();
        c.rotate(45f, 34 * s, 68 * s);
        c.drawRoundRect(14 * s, 60 * s, 54 * s, 76 * s, 8 * s, 8 * s, stroke);
        c.drawLine(30 * s, 60 * s, 30 * s, 76 * s, stroke);
        c.restore();

        // Heart outline, center-right.
        Path heart = new Path();
        heart.moveTo(122 * s, 82 * s);
        heart.cubicTo(112 * s, 68 * s, 92 * s, 82 * s, 122 * s, 106 * s);
        heart.cubicTo(152 * s, 82 * s, 132 * s, 68 * s, 122 * s, 82 * s);
        c.drawPath(heart, stroke);

        // Checkmark circle, bottom-left.
        c.drawCircle(24 * s, 128 * s, 12 * s, stroke);
        Path check = new Path();
        check.moveTo(18 * s, 128 * s);
        check.lineTo(22 * s, 133 * s);
        check.lineTo(31 * s, 122 * s);
        c.drawPath(check, stroke);

        // Footsteps dots, bottom-right.
        Path steps = new Path();
        steps.moveTo(112 * s, 150 * s);
        steps.quadTo(120 * s, 138 * s, 128 * s, 150 * s);
        steps.moveTo(128 * s, 150 * s);
        steps.quadTo(136 * s, 138 * s, 144 * s, 150 * s);
        c.drawPath(steps, stroke);

        return bmp;
    }

    static Button primaryButton(Context ctx, String text) {
        Button b = baseButton(ctx, text);
        b.setTextColor(0xFFFFFFFF);
        b.setBackground(withRipple(primaryGradientPill(), 0x33FFFFFF));
        b.setElevation(dp(ctx, 4));
        return b;
    }

    private static GradientDrawable primaryGradientPill() {
        GradientDrawable d = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{COLOR_PRIMARY_LIGHT, COLOR_PRIMARY, COLOR_PRIMARY_DARK});
        d.setCornerRadius(999f);
        return d;
    }

    static Button secondaryButton(Context ctx, String text) {
        Button b = baseButton(ctx, text);
        b.setTextColor(COLOR_PRIMARY);
        b.setBackground(withRipple(pill(COLOR_SURFACE, dp(ctx, 2), COLOR_PRIMARY_LIGHT), 0x221F4C46));
        return b;
    }

    static Button ghostButton(Context ctx, String text) {
        Button b = baseButton(ctx, text);
        b.setTextColor(COLOR_TEXT_MUTED);
        b.setBackground(withRipple(pill(0x00000000, 0, 0), 0x1A000000));
        return b;
    }

    /** Wraps a background drawable with a Material ripple so touch feedback survives replacing
     * the theme's default button background with a flat custom pill/circle. */
    static Drawable withRipple(Drawable base, int rippleColor) {
        return new RippleDrawable(ColorStateList.valueOf(rippleColor), base, null);
    }

    /** Shared circular button background (mic buttons) with ripple feedback baked in. */
    static Drawable circleBg(Context ctx, int fillColor) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fillColor);
        d.setCornerRadius(999f);
        return withRipple(d, 0x33FFFFFF);
    }

    /** Teal gradient circular button background (mic buttons), matching the web app's
     * mic-button-small gradient instead of a flat fill. */
    static Drawable circleGradientBg(Context ctx) {
        GradientDrawable d = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{COLOR_PRIMARY_LIGHT, COLOR_PRIMARY});
        d.setCornerRadius(999f);
        return withRipple(d, 0x33FFFFFF);
    }

    private static Button baseButton(Context ctx, String text) {
        Button b = new Button(ctx);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        b.setTypeface(null, Typeface.BOLD);
        b.setPadding(dp(ctx, 24), dp(ctx, 14), dp(ctx, 24), dp(ctx, 14));
        b.setStateListAnimator(null);
        return b;
    }

    private static GradientDrawable pill(int fill, int strokeWidth, int strokeColor) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(999f);
        if (strokeWidth > 0) d.setStroke(strokeWidth, strokeColor);
        return d;
    }

    static TextView heading(Context ctx, String text) {
        TextView tv = new TextView(ctx);
        tv.setText(text);
        tv.setTextColor(COLOR_TEXT);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28);
        tv.setTypeface(null, Typeface.BOLD);
        return tv;
    }

    static TextView body(Context ctx, String text) {
        TextView tv = new TextView(ctx);
        tv.setText(text);
        tv.setTextColor(COLOR_TEXT);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        tv.setLineSpacing(0, 1.3f);
        return tv;
    }

    static TextView muted(Context ctx, String text) {
        TextView tv = body(ctx, text);
        tv.setTextColor(COLOR_TEXT_MUTED);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        return tv;
    }

    static TextView label(Context ctx, String text) {
        TextView tv = new TextView(ctx);
        tv.setText(text);
        tv.setTextColor(COLOR_ACCENT);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        tv.setTypeface(null, Typeface.BOLD);
        tv.setLetterSpacing(0.08f);
        return tv;
    }

    static TextView errorText(Context ctx, String text) {
        TextView tv = body(ctx, text);
        tv.setTextColor(COLOR_WARNING);
        return tv;
    }

    static android.widget.LinearLayout card(Context ctx) {
        android.widget.LinearLayout card = new android.widget.LinearLayout(ctx);
        card.setOrientation(android.widget.LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR,
                new int[]{COLOR_SURFACE, COLOR_BG_MINT});
        bg.setCornerRadius(dp(ctx, 28));
        card.setBackground(bg);
        card.setPadding(dp(ctx, 24), dp(ctx, 24), dp(ctx, 24), dp(ctx, 24));
        card.setElevation(dp(ctx, 6));
        return card;
    }

    /** Small colored pill-shaped icon badge (e.g. next to "Medicine on the counter", or leading a
     * structured info row on the core-info screen) - matches the web app's `.field-icon` /
     * `.info-row-icon` mint circle treatment. */
    static ImageView iconBadge(Context ctx, int drawableRes, int sizeDp, int badgeColor, int tintColor) {
        ImageView iv = icon(ctx, drawableRes, sizeDp / 2, tintColor);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(badgeColor);
        bg.setCornerRadius(999f);
        iv.setBackground(bg);
        int size = dp(ctx, sizeDp);
        iv.setLayoutParams(new android.widget.LinearLayout.LayoutParams(size, size));
        iv.setPadding(size / 4, size / 4, size / 4, size / 4);
        return iv;
    }

    static android.widget.LinearLayout brandHeader(Context ctx, boolean compact) {
        return brandHeader(ctx, compact, false);
    }

    /** The shared "MedCheck" brand header - heart+cross mark drawn directly (no bitmap asset) plus
     * the wordmark, rendered identically to frontend-app's AppHeader component so both study
     * conditions show the same brand identity. Pass compact=true for mid-flow screens (smaller,
     * no tagline) vs the full version on the merged welcome screen. Pass light=true on a solid
     * dark-teal background (e.g. ClosingActivity) - the default teal-on-light treatment would be
     * invisible there, matching frontend-app's AppHeader `light` prop. */
    static android.widget.LinearLayout brandHeader(Context ctx, boolean compact, boolean light) {
        int fg = light ? 0xFFFFFFFF : COLOR_PRIMARY;

        android.widget.LinearLayout col = new android.widget.LinearLayout(ctx);
        col.setOrientation(android.widget.LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER_HORIZONTAL);

        android.widget.LinearLayout row = new android.widget.LinearLayout(ctx);
        row.setOrientation(android.widget.LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);

        ImageView logo = icon(ctx, R.drawable.ic_heart_cross, compact ? 22 : 32, fg);
        android.widget.LinearLayout.LayoutParams logoLp =
                (android.widget.LinearLayout.LayoutParams) logo.getLayoutParams();
        logoLp.rightMargin = dp(ctx, 8);
        row.addView(logo);

        TextView wordmark = new TextView(ctx);
        wordmark.setText("MedCheck");
        wordmark.setTextColor(fg);
        wordmark.setTypeface(null, Typeface.BOLD);
        wordmark.setTextSize(TypedValue.COMPLEX_UNIT_SP, compact ? 16 : 22);
        row.addView(wordmark);

        android.widget.LinearLayout.LayoutParams rowLp = new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT);
        rowLp.gravity = Gravity.CENTER_HORIZONTAL;
        col.addView(row, rowLp);

        if (!compact) {
            TextView tagline = new TextView(ctx);
            tagline.setText("Smarter Medicine Decisions");
            tagline.setTextColor(light ? 0xBFFFFFFF : COLOR_TEXT_MUTED);
            tagline.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            tagline.setTypeface(null, Typeface.BOLD);
            center(tagline);
            col.addView(tagline);
        }

        return col;
    }

    /** Back button + compact brand header in a real row, matching frontend-app's TopNav component
     * - the header centers only in the space left over after the back button, so it can never
     * visually collide with it regardless of screen width (a real bug found and fixed on the
     * tablet side; ported here for the same reason). Use at the top of every mid-flow screen. */
    static LinearLayout topNav(Context ctx, View.OnClickListener onBack) {
        LinearLayout row = new LinearLayout(ctx);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);

        Button back = ghostButtonWithIcon(ctx, R.drawable.ic_back, "Back");
        back.setOnClickListener(onBack);
        GradientDrawable backBg = new GradientDrawable();
        backBg.setColor(COLOR_SURFACE);
        backBg.setCornerRadius(999f);
        backBg.setStroke(1, 0x1F1F4C46);
        back.setBackground(withRipple(backBg, 0x1A1F4C46));
        back.setTextColor(COLOR_PRIMARY);
        setLeadingIcon(ctx, back, R.drawable.ic_back, COLOR_PRIMARY);
        row.addView(back, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        LinearLayout headerWrap = new LinearLayout(ctx);
        headerWrap.setGravity(Gravity.CENTER);
        headerWrap.addView(brandHeader(ctx, true));
        row.addView(headerWrap, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

        return row;
    }

    /** Adds ripple touch feedback to a clickable card, matching its rounded corners. Call after
     * card.setOnClickListener(...) and card.setClickable(true). */
    static void addCardRipple(Context ctx, android.view.View card) {
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(0xFFFFFFFF);
        mask.setCornerRadius(dp(ctx, 16));
        card.setForeground(new RippleDrawable(ColorStateList.valueOf(0x1F1F4C46), null, mask));
    }

    static void center(TextView tv) {
        tv.setGravity(Gravity.CENTER);
    }

    /** Tinted, sized ImageView for one of the bundled vector icons (ic_mic, ic_back, ic_chat) -
     * used instead of emoji glyphs, which render as broken tofu boxes on Pepper's Android 6.0
     * build (it predates color emoji font support for newer codepoints like the mic emoji). */
    static ImageView icon(Context ctx, int drawableRes, int sizeDp, int tintColor) {
        ImageView iv = new ImageView(ctx);
        Drawable d = ContextCompat.getDrawable(ctx, drawableRes);
        if (d != null) {
            d = d.mutate();
            d.setTint(tintColor);
        }
        iv.setImageDrawable(d);
        int size = dp(ctx, sizeDp);
        iv.setLayoutParams(new android.widget.LinearLayout.LayoutParams(size, size));
        return iv;
    }

    /** A ghost-style button with an icon (instead of text glyphs) before the label, e.g. the back
     * navigation control. */
    static Button ghostButtonWithIcon(Context ctx, int drawableRes, String text) {
        Button b = ghostButton(ctx, text);
        setLeadingIcon(ctx, b, drawableRes, COLOR_TEXT_MUTED);
        return b;
    }

    /** Adds a tinted leading icon (compound drawable) to any button, replacing emoji-in-text. */
    static void setLeadingIcon(Context ctx, Button b, int drawableRes, int tintColor) {
        Drawable d = ContextCompat.getDrawable(ctx, drawableRes);
        if (d != null) {
            d = d.mutate();
            d.setTint(tintColor);
            int size = dp(ctx, 18);
            d.setBounds(0, 0, size, size);
        }
        b.setCompoundDrawables(d, null, null, null);
        b.setCompoundDrawablePadding(dp(ctx, 8));
    }
}
