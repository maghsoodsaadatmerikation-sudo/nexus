package org.nexus.offline.stage25;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.util.Base64;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.JsResult;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * Stage25 TEST build only — fully local human-reviewed Work Mode.
 * Delivers a single reviewed HTML asset through an app-owned HTTPS origin.
 * No INTERNET permission, cloud client, audio/video permission, telemetry,
 * native task executor, general Android file-system access or sync.
 */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String PREFIX = "/nexus/";
    private static final String START = "https://" + HOST + PREFIX + "index.html";
    private static final int CHOOSE_FILE = 102;
    private static final int SAVE_FILE = 103;
    private static final int LIMIT = 6 * 1024 * 1024;
    private WebView webView;
    private ValueCallback<Uri[]> chooser;
    private byte[] pendingExport;

    private boolean local(Uri uri) {
        return uri != null && "https".equals(uri.getScheme()) &&
               HOST.equals(uri.getHost()) && uri.getPort() == -1 &&
               uri.getEncodedQuery() == null && uri.getEncodedFragment() == null &&
               (PREFIX + "index.html").equals(uri.getEncodedPath());
    }

    private WebResourceResponse deny() {
        WebResourceResponse response = new WebResourceResponse(
            "text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
        response.setStatusCodeAndReasonPhrase(403, "Blocked");
        response.setResponseHeaders(new HashMap<String,String>() {{
            put("Cache-Control", "no-store");
        }});
        return response;
    }

    private WebResourceResponse localResource(Uri uri) {
        if (!local(uri)) return deny();
        try {
            InputStream input = getAssets().open("nexus/index.html");
            Map<String,String> headers = new HashMap<>();
            headers.put("Cache-Control", "no-store");
            headers.put("X-Content-Type-Options", "nosniff");
            WebResourceResponse response =
                new WebResourceResponse("text/html", "UTF-8", input);
            response.setStatusCodeAndReasonPhrase(200, "OK");
            response.setResponseHeaders(headers);
            return response;
        } catch (Exception exception) {
            return deny();
        }
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));
        webView.setBackgroundColor(0xfff1f6f5);
        WebSettings settings=webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(
                    WebView view, WebResourceRequest req) {
                // Returning a response, including for all unknown URLs,
                // prevents WebView from falling back to a network request.
                if (!"GET".equals(req.getMethod())) return deny();
                return localResource(req.getUrl());
            }
            @Override public boolean shouldOverrideUrlLoading(
                    WebView view, WebResourceRequest request) {
                return !local(request.getUrl());
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onJsConfirm(
                    WebView view, String url, String message, final JsResult result) {
                if (!START.equals(url)) {
                    result.cancel();
                    return true;
                }
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle("NEXUS · Human confirmation")
                    .setMessage(message)
                    .setPositiveButton("Confirm", (dialog,which)->result.confirm())
                    .setNegativeButton("Cancel", (dialog,which)->result.cancel())
                    .setOnCancelListener(dialog->result.cancel()).show();
                return true;
            }
            @Override public boolean onShowFileChooser(WebView view,
                    ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (chooser != null || pendingExport != null) return false;
                chooser=callback;
                Intent input=new Intent(Intent.ACTION_OPEN_DOCUMENT);
                input.addCategory(Intent.CATEGORY_OPENABLE);
                input.setType("*/*");
                try {
                    startActivityForResult(input, CHOOSE_FILE);
                    return true;
                } catch (Exception ex) {
                    chooser=null;
                    callback.onReceiveValue(null);
                    return true;
                }
            }
        });
        webView.addJavascriptInterface(new FileExportBridge(),"NEXUS_NATIVE_EXPORT");
        setContentView(webView);
        webView.loadUrl(START);
    }

    /** Exposes exactly one explicit-document-export function, no authority to
        invoke other native services. The user chooses the output location. */
    private final class FileExportBridge {
        @JavascriptInterface public void save(String name, String text64) {
            if (name == null || text64 == null || name.length()>160 ||
                text64.length()>8*1024*1024+100 ||
                name.length()==0 || name.contains("/") ||
                name.contains("\\") || name.contains("..") ||
                name.matches(".*[\\x00-\\x1f].*")) return;
            final byte[] payload;
            try { payload=Base64.decode(text64,Base64.DEFAULT); }
            catch (IllegalArgumentException ex) { return; }
            if (payload.length>LIMIT) return;
            runOnUiThread(()->{
                if (pendingExport!=null || chooser!=null || webView==null ||
                    !START.equals(webView.getUrl())) return;
                pendingExport=payload;
                Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType(name.endsWith(".json")?
                    "application/json":name.endsWith(".md")?
                    "text/markdown":"application/octet-stream");
                intent.putExtra(Intent.EXTRA_TITLE,name);
                try { startActivityForResult(intent,SAVE_FILE); }
                catch (Exception ex) {
                    pendingExport=null;
                    Toast.makeText(MainActivity.this,
                        "File picker unavailable",Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,
                                               Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==CHOOSE_FILE){
            ValueCallback<Uri[]> callback=chooser;chooser=null;
            if(callback==null)return;
            Uri uri=(resultCode==RESULT_OK&&data!=null)?data.getData():null;
            callback.onReceiveValue(uri!=null&&"content".equals(uri.getScheme())?
                new Uri[]{uri}:null);
        }else if(requestCode==SAVE_FILE){
            byte[] payload=pendingExport;pendingExport=null;
            Uri uri=(resultCode==RESULT_OK&&data!=null)?data.getData():null;
            if(payload==null||uri==null||!"content".equals(uri.getScheme()))return;
            try(OutputStream stream=getContentResolver().openOutputStream(uri,"w")){
                if(stream==null)throw new IllegalStateException("no output stream");
                stream.write(payload);
                stream.flush();
                Toast.makeText(this,"Saved selected file",Toast.LENGTH_SHORT).show();
            }catch(Exception ex){
                Toast.makeText(this,"Could not write selected file",Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override public void onBackPressed(){
        // Never navigate to unexpected external origins inside WebView.
        super.onBackPressed();
    }

    @Override protected void onDestroy(){
        if(chooser!=null){chooser.onReceiveValue(null);chooser=null;}
        pendingExport=null;
        if(webView!=null){
            webView.removeJavascriptInterface("NEXUS_NATIVE_EXPORT");
            webView.destroy();
            webView=null;
        }
        super.onDestroy();
    }
}
