package com.genesis.watchpulse;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Shared Quantum Void styling helpers. Gold is reserved for Aurum/Pulse. */
public final class Ui {
    public static final int BG      = Color.rgb(13, 6, 24);    // deepest void purple
    public static final int PANEL   = Color.rgb(30, 16, 51);   // zone tile fill
    public static final int PANEL2  = Color.rgb(42, 24, 80);   // pressed / row fill
    public static final int PURPLE  = Color.rgb(139, 92, 246); // violet accent
    public static final int PURPLE_DK = Color.rgb(88, 54, 160);
    public static final int GOLD    = Color.rgb(232, 184, 75); // AURUM ONLY
    public static final int GOLD_HI = Color.rgb(255, 215, 110);
    public static final int TEXT    = Color.rgb(239, 234, 247);
    public static final int DIM     = Color.rgb(154, 143, 181);

    private Ui() {}

    public static int dp(Context c, float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                c.getResources().getDisplayMetrics());
    }

    public static GradientDrawable rounded(int fill, int stroke, float radiusDp, Context c) {
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.RECTANGLE);
        g.setColor(fill);
        g.setCornerRadius(dp(c, radiusDp));
        if (stroke != 0) g.setStroke(Math.max(1, dp(c, 1)), stroke);
        return g;
    }

    public static TextView text(Context c, String s, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return t;
    }

    /** A full-width zone tile. gold=true is reserved for the Pulse (Aurum) tile. */
    public static LinearLayout tile(Context c, String title, String sub, boolean gold) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(c, 20), dp(c, 18), dp(c, 20), dp(c, 18));
        row.setBackground(rounded(PANEL, gold ? GOLD : PURPLE_DK, 16, c));

        View dot = new View(c);
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.OVAL);
        d.setColor(gold ? GOLD : PURPLE);
        dot.setBackground(d);
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(dp(c, 14), dp(c, 14));
        dlp.rightMargin = dp(c, 16);
        dot.setLayoutParams(dlp);
        row.addView(dot);

        LinearLayout col = new LinearLayout(c);
        col.setOrientation(LinearLayout.VERTICAL);
        TextView t = text(c, title, 19, gold ? GOLD_HI : TEXT, true);
        t.setLetterSpacing(0.18f);
        col.addView(t);
        TextView s = text(c, sub, 12.5f, DIM, false);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        slp.topMargin = dp(c, 3);
        s.setLayoutParams(slp);
        col.addView(s);
        row.addView(col);
        return row;
    }

    public static LinearLayout.LayoutParams tileLp(Context c) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(c, 12);
        return lp;
    }
}
