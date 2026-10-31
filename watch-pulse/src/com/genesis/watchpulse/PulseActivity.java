package com.genesis.watchpulse;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * PULSE zone: the Aurum web player (workshop static/aurum.html, 2026-10-01
 * build) bundled in assets and served from a local fake-https origin so the
 * shell + library load fully offline. Streaming itself (Audius) uses the
 * network when available, exactly as the design note allows.
 */
public class PulseActivity extends Activity {
    static final String HOST = "aurum.watchpulse.local";
    private WebView web;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Ui.BG);

        // Slim top bar: back to GENESIS, gold Aurum label
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        bar.setBackgroundColor(Ui.PANEL);
        TextView back = Ui.text(this, "‹ GENESIS", 14, Ui.DIM, true);
        back.setPadding(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 6));
        back.setOnClickListener(v -> finish());
        bar.addView(back);
        TextView label = Ui.text(this, "AURUM · PULSE", 14, Ui.GOLD_HI, true);
        label.setLetterSpacing(0.2f);
        bar.addView(label);
        root.addView(bar);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                 // resume position, local state
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new AurumClient());
        root.addView(web, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        web.loadUrl("https://" + HOST + "/aurum");
    }

    private class AurumClient extends WebViewClient {
        @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if (uri == null || !HOST.equals(uri.getHost())) return null; // real network (Audius etc.)
            String path = uri.getPath() == null ? "/" : uri.getPath();
            try {
                switch (path) {
                    case "/":
                    case "/aurum":
                    case "/index.html":
                        return asset("aurum/index.html", "text/html; charset=utf-8");
                    case "/aurum.webmanifest":
                        return asset("aurum/aurum.webmanifest", "application/manifest+json");
                    case "/aurum-icon-192.png":
                        return asset("aurum/aurum-icon-192.png", "image/png");
                    case "/aurum-icon-512.png":
                        return asset("aurum/aurum-icon-512.png", "image/png");
                    case "/aurum-sw.js":
                        // No service worker in the shell build; harmless no-op.
                        return text("/* watchpulse: no service worker */", "text/javascript");
                    case "/api/aurum/tracks":
                        return asset("aurum/tracks.json", "application/json; charset=utf-8");
                    case "/api/aurum/rate":
                    case "/api/aurum/history":
                        // Fire-and-forget on the live workshop; acknowledged locally in v1.
                        return json("{\"ok\":true}");
                    case "/api/aurum/chat":
                        // Apollo chat lives on the live workshop; be honest in-product.
                        return json("{\"reply\":\"Apollo chat runs on the live Genesis workshop — "
                                + "in this offline shell the library is fully playable, but I can't "
                                + "chat here yet. (Watch+Pulse v1)\",\"brain\":\"fallback\"}");
                    default:
                        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found",
                                new HashMap<String, String>(),
                                new ByteArrayInputStream(new byte[0]));
                }
            } catch (IOException e) {
                return new WebResourceResponse("text/plain", "utf-8", 500, "Asset error",
                        new HashMap<String, String>(), new ByteArrayInputStream(new byte[0]));
            }
        }

        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            // Keep the fake origin inside; let real links (artist pages etc.) leave to the browser.
            return uri == null || !HOST.equals(uri.getHost());
        }
    }

    private WebResourceResponse asset(String name, String mime) throws IOException {
        InputStream in = getAssets().open(name);
        Map<String, String> headers = new HashMap<>();
        headers.put("Cache-Control", "no-cache");
        return new WebResourceResponse(mime.contains(";") ? mime.split(";")[0] : mime,
                "utf-8", 200, "OK", headers, in);
    }

    private WebResourceResponse text(String body, String mime) {
        return new WebResourceResponse(mime, "utf-8", 200, "OK",
                new HashMap<String, String>(),
                new ByteArrayInputStream(body.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }

    private WebResourceResponse json(String body) {
        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Type", "application/json; charset=utf-8");
        return new WebResourceResponse("application/json", "utf-8", 200, "OK", headers,
                new ByteArrayInputStream(body.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onPause() { super.onPause(); if (web != null) web.onPause(); }
    @Override protected void onResume() { super.onResume(); if (web != null) web.onResume(); }
    @Override protected void onDestroy() { if (web != null) web.destroy(); super.onDestroy(); }
}
