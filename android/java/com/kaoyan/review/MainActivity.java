package com.kaoyan.review;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.Window;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * 单 Activity WebView 壳：本地 HTML/JS 应用放在 assets/www/，数据在 assets/data/。
 * 页面以 https://app.local/ 为源（shouldInterceptRequest 拦截后从 assets 供文件），
 * 外部 https 请求（在线刷新 / 图片 CDN）不拦截，走系统网络栈。
 */
public class MainActivity extends Activity {

    private static final String ORIGIN = "https://app.local";
    private static final String TAG = "KaoyanReview";
    private WebView web;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setTextZoom(100);
        // 深色模式下不要系统强制反色，页面自带配色
        if (Build.VERSION.SDK_INT >= 29) {
            s.setForceDark(WebSettings.FORCE_DARK_OFF);
            web.setForceDarkAllowed(false);
        }

        web.setBackgroundColor(Color.parseColor("#f5f6f8"));
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                String host = url.getHost();
                if (host == null || !host.equals("app.local")) {
                    return null; // 外部资源走默认网络加载
                }
                return serveAsset(url.getPath());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if ("app.local".equals(url.getHost())) {
                    return false; // 应用内路由
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (Exception e) {
                    Log.w(TAG, "cannot open " + url);
                }
                return true;
            }
        });

        setContentView(web);
        if (savedInstanceState == null) {
            web.loadUrl(ORIGIN + "/www/index.html");
        } else {
            web.restoreState(savedInstanceState);
        }
    }

    /** 把 /www/... /data/... 路径映射到 assets 内同名文件。 */
    private WebResourceResponse serveAsset(String path) {
        if (path == null || path.contains("..")) {
            return notFound();
        }
        if (path.startsWith("/")) {
            path = path.substring(1);
        }
        if (path.isEmpty()) {
            path = "www/index.html";
        }
        AssetManager am = getAssets();
        InputStream in;
        try {
            in = am.open(path);
        } catch (IOException e) {
            return notFound();
        }
        Map<String, String> headers = new HashMap<>();
        headers.put("Access-Control-Allow-Origin", ORIGIN);
        headers.put("Cache-Control", "no-cache");
        return new WebResourceResponse(mimeOf(path), "utf-8", 200, "OK", headers, in);
    }

    private WebResourceResponse notFound() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found",
                null, new ByteArrayInputStream("not found".getBytes()));
    }

    private static String mimeOf(String path) {
        int dot = path.lastIndexOf('.');
        String ext = dot < 0 ? "" : path.substring(dot + 1).toLowerCase();
        switch (ext) {
            case "html": return "text/html";
            case "js":   return "application/javascript";
            case "css":  return "text/css";
            case "json": return "application/json";
            case "png":  return "image/png";
            case "jpg": case "jpeg": return "image/jpeg";
            case "gif":  return "image/gif";
            case "svg":  return "image/svg+xml";
            case "webp": return "image/webp";
            case "ico":  return "image/x-icon";
            case "woff": return "font/woff";
            case "woff2": return "font/woff2";
            case "ttf":  return "font/ttf";
            case "txt": case "md": return "text/plain";
            default: return "application/octet-stream";
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
