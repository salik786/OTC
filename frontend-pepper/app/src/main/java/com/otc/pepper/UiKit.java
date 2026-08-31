package com.otc.pepper;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.core.content.ContextCompat;

/**
 * Small shared styling helpers so every screen looks consistent without repeating drawable/button
 * boilerplate in each Activity. Colors are copied from frontend-app/src/styles/tokens.css so the
 * Pepper app reads as the same product, not a re-skin.
 */
final class UiKit {
    private UiKit() {}

    static final int COLOR_PRIMARY = 0xFF1F4C46;
    static final int COLOR_PRIMARY_DARK = 0xFF163731;
    static final int COLOR_ACCENT = 0xFFB98639;
    static final int COLOR_WARNING = 0xFF9C3B32;
    static final int COLOR_WARNING_BG = 0xFFFBECEB;
    static final int COLOR_BG = 0xFFFAF8F4;
    static final int COLOR_SURFACE = 0xFFFFFFFF;
    static final int COLOR_TEXT = 0xFF14201E;
    static final int COLOR_TEXT_MUTED = 0xFF4A5A57;
    static final int COLOR_BORDER = 0xFFD8D3C8;

    static int dp(Context ctx, int value) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, ctx.getResources().getDisplayMetrics());
    }

    static Button primaryButton(Context ctx, String text) {
        Button b = baseButton(ctx, text);
        b.setTextColor(0xFFFFFFFF);
        b.setBackground(withRipple(pill(COLOR_PRIMARY, 0, 0), 0x33FFFFFF));
        return b;
    }

    static Button secondaryButton(Context ctx, String text) {
        Button b = baseButton(ctx, text);
        b.setTextColor(COLOR_PRIMARY);
        b.setBackground(withRipple(pill(COLOR_SURFACE, dp(ctx, 2), COLOR_PRIMARY), 0x221F4C46));
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
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(COLOR_SURFACE);
        bg.setCornerRadius(dp(ctx, 16));
        card.setBackground(bg);
        card.setPadding(dp(ctx, 24), dp(ctx, 24), dp(ctx, 24), dp(ctx, 24));
        card.setElevation(dp(ctx, 3));
        return card;
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
