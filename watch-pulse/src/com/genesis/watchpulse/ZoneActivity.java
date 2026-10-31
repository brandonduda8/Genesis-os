package com.genesis.watchpulse;

import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Honest placeholder for zones that dock in a later build (BUILD / FLEET / FORGE). */
public class ZoneActivity extends Activity {
    public static final String EXTRA_ZONE = "zone";

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String zone = getIntent().getStringExtra(EXTRA_ZONE);
        if (zone == null) zone = "ZONE";

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Ui.BG);
        root.setPadding(Ui.dp(this, 22), Ui.dp(this, 30), Ui.dp(this, 22), Ui.dp(this, 28));

        TextView back = Ui.text(this, "‹ GENESIS", 14, Ui.DIM, true);
        back.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 14));
        back.setOnClickListener(v -> finish());
        root.addView(back);

        TextView title = Ui.text(this, zone, 24, Ui.TEXT, true);
        title.setLetterSpacing(0.3f);
        root.addView(title);

        TextView body = Ui.text(this,
                "This zone docks in a later build. Watch+Pulse v1 ships the PULSE and "
                        + "WATCH zones for real; " + zone + " is present in the design "
                        + "language only — no fake functionality behind this tile.",
                14, Ui.DIM, false);
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        blp.topMargin = Ui.dp(this, 14);
        body.setLayoutParams(blp);
        root.addView(body);

        setContentView(root);
    }
}
