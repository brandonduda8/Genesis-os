package com.genesis.watchpulse;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * WATCH zone — Shape A (Brandon's pick, 2026-10-31): designed tiles that hand
 * off to the official YouTube app, where his Premium Lite entitlements
 * (ad-light playback, downloads, background play) are honored in full.
 * No embedded player, no credentials, no unofficial APIs.
 */
public class WatchActivity extends Activity {
    private static final String YT_PACKAGE = "com.google.android.youtube";

    private static final String[][] ROWS = {
        {"Your Playlists", "Every playlist on your account", "https://www.youtube.com/feed/playlists"},
        {"Subscriptions", "Latest from channels you follow", "https://www.youtube.com/feed/subscriptions"},
        {"History", "Pick up where you left off", "https://www.youtube.com/feed/history"},
        {"Watch Later", "Your saved Watch Later list", "https://www.youtube.com/playlist?list=WL"},
        {"YouTube Home", "The front page, signed in as you", "https://www.youtube.com/"},
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Ui.BG);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(Ui.dp(this, 22), Ui.dp(this, 30), Ui.dp(this, 22), Ui.dp(this, 28));
        scroll.addView(root);

        TextView back = Ui.text(this, "‹ GENESIS", 14, Ui.DIM, true);
        back.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 14));
        back.setOnClickListener(v -> finish());
        root.addView(back);

        TextView title = Ui.text(this, "WATCH", 24, Ui.TEXT, true);
        title.setLetterSpacing(0.3f);
        root.addView(title);

        TextView note = Ui.text(this,
                "Opens in the official YouTube app — that's where your Premium Lite "
                        + "perks (downloads, background play) live.", 12.5f, Ui.DIM, false);
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        nlp.topMargin = Ui.dp(this, 8);
        note.setLayoutParams(nlp);
        root.addView(note);

        for (String[] r : ROWS) {
            final String url = r[2];
            LinearLayout tile = Ui.tile(this, r[0], r[1], false);
            tile.setOnClickListener(v -> openYouTube(url));
            tile.setLayoutParams(Ui.tileLp(this));
            root.addView(tile);
        }

        setContentView(scroll);
    }

    private void openYouTube(String url) {
        Intent targeted = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        targeted.setPackage(YT_PACKAGE);
        try {
            startActivity(targeted);
        } catch (ActivityNotFoundException e) {
            // Official app absent/disabled — fall back to whatever handles the URL (browser).
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (ActivityNotFoundException ignored) {
                // Nothing on the device can open it; stay on the Watch screen.
            }
        }
    }
}
