package com.genesis.watchpulse;

import android.app.Activity;
import android.content.Intent;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** GENESIS home: Quantum Void shell, breathing gold Pulse dot, five zone tiles. */
public class MainActivity extends Activity {
    private View pulseDot;
    private final Handler handler = new Handler();
    private boolean breathing = false;

    private final Runnable breath = new Runnable() {
        @Override public void run() {
            if (pulseDot == null) return;
            breathing = !breathing;
            pulseDot.animate()
                    .alpha(breathing ? 0.35f : 1.0f)
                    .scaleX(breathing ? 0.78f : 1.0f)
                    .scaleY(breathing ? 0.78f : 1.0f)
                    .setDuration(1400)
                    .start();
            handler.postDelayed(this, 1450);
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Ui.BG);
        scroll.setFillViewport(true);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(Ui.dp(this, 22), Ui.dp(this, 34), Ui.dp(this, 22), Ui.dp(this, 30));
        scroll.addView(root);

        // Title row: GENESIS + breathing gold Pulse dot
        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setOrientation(LinearLayout.HORIZONTAL);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = Ui.text(this, "GENESIS", 27, Ui.TEXT, true);
        title.setLetterSpacing(0.32f);
        titleRow.addView(title);

        pulseDot = new View(this);
        GradientDrawable gd = new GradientDrawable();
        gd.setShape(GradientDrawable.OVAL);
        gd.setColor(Ui.GOLD);
        pulseDot.setBackground(gd);
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(
                Ui.dp(this, 13), Ui.dp(this, 13));
        dlp.leftMargin = Ui.dp(this, 14);
        pulseDot.setLayoutParams(dlp);
        titleRow.addView(pulseDot);
        root.addView(titleRow);

        TextView sub = Ui.text(this, "WATCH + PULSE · v1", 12, Ui.DIM, false);
        sub.setLetterSpacing(0.22f);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        slp.topMargin = Ui.dp(this, 6);
        sub.setLayoutParams(slp);
        root.addView(sub);

        // PULSE — gold, Aurum inside (offline shell + library)
        LinearLayout pulse = Ui.tile(this, "PULSE", "Aurum player — your music, inside the shell", true);
        pulse.setOnClickListener(v -> startActivity(new Intent(this, PulseActivity.class)));
        LinearLayout.LayoutParams first = Ui.tileLp(this);
        first.topMargin = Ui.dp(this, 28);
        pulse.setLayoutParams(first);
        root.addView(pulse);

        // WATCH — Shape A handoff to the official YouTube app
        LinearLayout watch = Ui.tile(this, "WATCH", "Your YouTube — opens in the official app, Lite perks intact", false);
        watch.setOnClickListener(v -> startActivity(new Intent(this, WatchActivity.class)));
        watch.setLayoutParams(Ui.tileLp(this));
        root.addView(watch);

        addPlaceholder(root, "BUILD", "Cody's bench — docks in a later build");
        addPlaceholder(root, "FLEET", "Fleet board — docks in a later build");
        addPlaceholder(root, "FORGE", "Apex Forge — docks in a later build");

        setContentView(scroll);
    }

    private void addPlaceholder(LinearLayout root, final String zone, String sub) {
        LinearLayout t = Ui.tile(this, zone, sub, false);
        t.setAlpha(0.75f);
        t.setOnClickListener(v -> {
            Intent i = new Intent(this, ZoneActivity.class);
            i.putExtra(ZoneActivity.EXTRA_ZONE, zone);
            startActivity(i);
        });
        t.setLayoutParams(Ui.tileLp(this));
        root.addView(t);
    }

    @Override protected void onResume() {
        super.onResume();
        handler.removeCallbacks(breath);
        handler.post(breath);
    }

    @Override protected void onPause() {
        super.onPause();
        handler.removeCallbacks(breath);
    }
}
