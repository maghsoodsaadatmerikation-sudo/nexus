package org.nexus.mobile;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.util.Base64;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.SafeBrowsingResponse;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;
import org.json.JSONException;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Native offline-only NEXUS Studio + Motion experimental debug APK.
 *
 * Has NO INTERNET permission. Embedded public sources are verified against
 * the exact source-bound catalog before WebView initializes. Unlisted URLs,
 * all non-GET requests, remote links, file:// navigations, non-HTTPS and
 * unknown files are refused. User-chosen exports go through ACTION_CREATE_DOCUMENT.
 */
public final class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String ROOT = "https://" + HOST + "/";
    private static final int PICK_SOURCE = 201;
    private static final int PICK_EXPORT = 202;
    private static final long MAX_EXPORT = 96L * 1024 * 1024;

    private WebView web;
    private ValueCallback<Uri[]> selectedFiles;
    private final Map<String, Entry> allowed = new HashMap<>();
    private final ExportBridge exporter = new ExportBridge();

    private static final class Entry {
        final String path;
        final String mime;
        Entry(String path, String mime) { this.path=path; this.mime=mime; }
    }

    private static byte[] read(InputStream input, int max) throws IOException {
        try (InputStream in=input; ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] buf=new byte[16384];
            int n, total=0;
            while ((n=in.read(buf))!=-1) {
                total+=n;
                if (total>max) throw new IOException("Embedded asset exceeds bound");
                out.write(buf,0,n);
            }
            return out.toByteArray();
        }
    }

    private InputStream open(String path) throws IOException {
        return getAssets().open("nexus/" + path);
    }

    private static String sha256(byte[] data) throws Exception {
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        byte[] digest=md.digest(data);
        StringBuilder s=new StringBuilder(64);
        for (byte value:digest) s.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
        return s.toString();
    }

    private void validateAllAssets() throws Exception {
        JSONObject catalog=new JSONObject(new String(
                read(open("nexus-catalog.json"),20000),StandardCharsets.UTF_8));
        if (!"nexus.android.public-assets.v1".equals(catalog.getString("schema"))
                || !catalog.getBoolean("no_network_permission")
                || !catalog.getBoolean("no_user_data")) throw new IOException("catalog contract rejected");
        JSONObject items=catalog.getJSONObject("assets");
        if (items.length()<15 || items.length()>80) throw new IOException("invalid asset count");
        for (java.util.Iterator<String> keys=items.keys();keys.hasNext();) {
            String name=keys.next();
            if (!name.matches("[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*")
                    || name.contains("..") || name.startsWith(".")) throw new IOException("unsafe asset name");
            JSONObject expected=items.getJSONObject(name);
            int size=expected.getInt("bytes");
            if (size<1 || size>500000) throw new IOException("asset size invalid");
            byte[] bytes=read(open(name),500000);
            if (bytes.length!=size || !sha256(bytes).equals(expected.getString("sha256")))
                throw new IOException("embedded asset integrity mismatch");
            String mime=expected.getString("mime");
            if (!mime.matches("text/html|text/javascript|application/json|image/png|text/plain"))
                throw new IOException("unsupported asset MIME");
            allowed.put("/"+name,new Entry(name,mime));
        }
        if (!allowed.containsKey("/apps.html") || !allowed.containsKey("/index.html")
                || !allowed.containsKey("/motion/index.html")) throw new IOException("critical UI missing");
        allowed.put("/", allowed.get("/index.html"));
        allowed.put("/motion/", allowed.get("/motion/index.html"));
    }

    private boolean local(Uri uri) {
        return "https".equals(uri.getScheme()) && HOST.equals(uri.getHost())
                && uri.getPort()==-1 && uri.getEncodedQuery()==null
                && uri.getEncodedFragment()==null;
    }

    private WebResourceResponse denied() {
        Map<String,String> h=new HashMap<>();
        h.put("Cache-Control","no-store");
        h.put("X-Content-Type-Options","nosniff");
        return new WebResourceResponse("text/plain","UTF-8",404,"Not Found",h,
                new ByteArrayInputStream("Private or unknown resource refused".getBytes(StandardCharsets.UTF_8)));
    }

    private WebResourceResponse localAsset(WebResourceRequest request) {
        if (!"GET".equals(request.getMethod()) || !local(request.getUrl()))
            return denied();
        String path=request.getUrl().getEncodedPath();
        if (path==null || path.contains("%") || path.contains("//")
                || path.contains("..")) return denied();
        Entry entry=allowed.get(path);
        if (entry==null) return denied();
        try {
            Map<String,String> h=new HashMap<>();
            h.put("Cache-Control","no-store");
            h.put("X-Content-Type-Options","nosniff");
            h.put("Referrer-Policy","no-referrer");
            return new WebResourceResponse(entry.mime,"UTF-8",200,"OK",h,open(entry.path));
        } catch (IOException e) { return denied(); }
    }

    private void notifyUser(String message) {
        runOnUiThread(()->Toast.makeText(this,message,Toast.LENGTH_LONG).show());
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try { validateAllAssets(); }
        catch (Exception e) {
            TextView blocked=new TextView(this);
            blocked.setPadding(28,40,28,20);
            blocked.setText("NEXUS did not start: embedded public asset verification failed. No network was used.");
            setContentView(blocked);
            return;
        }

        // Never restore an untrusted URL or arbitrary web history on startup.
        web=new WebView(this);
        web.setBackgroundColor(0xff0b1427);
        setContentView(web);
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true); // user-selected Android content Uri only
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(true);
        if (Build.VERSION.SDK_INT>=26) settings.setSafeBrowsingEnabled(true);

        web.addJavascriptInterface(exporter,"NexusExport");
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest req) {
                return localAsset(req);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return !local(req.getUrl()) || !allowed.containsKey(req.getUrl().getEncodedPath());
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (!local(Uri.parse(url))) return;
                // Never log project content, user inputs, URLs with queries or
                // secret values. Emulator-only witness checks static public
                // UI readiness rather than trusting a successful Activity boot.
                if ((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
                    String page = Uri.parse(url).getEncodedPath();
                    String witness = null;
                    if ("/apps.html".equals(page)) {
                        witness = "(document.title.includes('NEXUS Mobile') && " +
                                  "!!document.querySelector('a[href=\\\"./motion/\\\"]') && " +
                                  "!!document.querySelector('a[href=\\\"./\\\"]'))";
                    } else if ("/motion/".equals(page)) {
                        witness = "(document.title.includes('NEXUS Motion') && " +
                                  "typeof window.NexusMotion === 'object' && " +
                                  "!!document.getElementById('motion-canvas') && " +
                                  "!!document.getElementById('motion-add') && " +
                                  "!!document.getElementById('motion-draft-pass') && " +
                                  "!!document.getElementById('motion-draft-restore') && " +
                                  "!!window.crypto && !!window.crypto.subtle && " +
                                  "typeof window.crypto.subtle.encrypt === 'function')";
                    } else if ("/".equals(page)) {
                        witness = "(document.title === 'NEXUS Studio' && " +
                                  "!!document.getElementById('messages'))";
                    }
                    if (witness != null) {
                        final String publicPath = page;
                        view.evaluateJavascript(witness, value ->
                            Log.i("NEXUS_ANDROID_SMOKE", publicPath + " ready=" + value));
                    }
                }
                // The signed, bundled JavaScript adapter is evaluated only on
                // the trusted local appassets origin; no remote frames exist.
                try {
                    byte[] adapter=read(open("android-export.js"),20000);
                    view.evaluateJavascript(new String(adapter,StandardCharsets.UTF_8),null);
                    view.evaluateJavascript(
                       "document.getElementById('motion-offline-panel')?.setAttribute('hidden','');"+
                       "document.getElementById('studio-install-card')?.setAttribute('hidden','');",null);
                } catch (IOException e) { notifyUser("Local file save adapter unavailable"); }
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view,
                    ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (selectedFiles!=null) selectedFiles.onReceiveValue(null);
                selectedFiles=callback;
                try {
                    Intent picker=params.createIntent();
                    picker.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(picker,PICK_SOURCE);
                    return true;
                } catch (ActivityNotFoundException e) {
                    selectedFiles=null;
                    callback.onReceiveValue(null);
                    notifyUser("Android file picker not available");
                    return false;
                }
            }
        });
        web.loadUrl(ROOT+"apps.html");
    }

    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if (request==PICK_SOURCE && selectedFiles!=null) {
            Uri[] files=WebChromeClient.FileChooserParams.parseResult(result,data);
            selectedFiles.onReceiveValue(files);
            selectedFiles=null;
        } else if (request==PICK_EXPORT) {
            exporter.complete(result==RESULT_OK && data!=null ? data.getData() : null);
        }
    }

    @Override public void onBackPressed() {
        if (web!=null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (web!=null) {
            web.removeJavascriptInterface("NexusExport");
            web.destroy();
        }
        exporter.cancelCurrent();
        super.onDestroy();
    }

    /**
     * Explicit user-owned export protocol, with bounded base64 chunks and
     * Android Storage Access Framework destination chooser. Never silently
     * writes media to shared storage or shares it over the network.
     */
    private final class ExportBridge {
        private File temp;
        private FileOutputStream stream;
        private String id,filename,mime;
        private long expected,received;
        private boolean selecting;

        @JavascriptInterface public synchronized String begin(String name,String type,double count) {
            if (id!=null || selecting || !Double.isFinite(count) ||
                    count<=0 || count>MAX_EXPORT || count!=Math.rint(count) ||
                    name==null || !name.matches("[a-zA-Z0-9_. -]{1,90}") ||
                    name.contains("..") || type==null ||
                    !type.matches("application/(json|zip|octet-stream|pdf)|text/(plain|html|markdown)|video/(mp4|webm)|audio/(wav|mpeg|ogg)|image/(png|jpeg|webp)"))
                return "";
            try {
                id=java.util.UUID.randomUUID().toString();
                temp=File.createTempFile("nexus-export-", ".tmp",getCacheDir());
                stream=new FileOutputStream(temp);
                expected=(long)count;received=0;filename=name;mime=type;
                return id;
            } catch (IOException e) { cancelCurrent();return ""; }
        }

        @JavascriptInterface public synchronized boolean append(String token,String encoded) {
            if (!valid(token) || encoded==null || encoded.length()>100_000) return false;
            try {
                byte[] chunk=Base64.decode(encoded,Base64.NO_WRAP);
                if (chunk.length==0 || chunk.length>48*1024 ||
                        received+chunk.length>expected) { cancelCurrent();return false; }
                stream.write(chunk);
                received+=chunk.length;
                return true;
            } catch (RuntimeException|IOException e) { cancelCurrent();return false; }
        }

        @JavascriptInterface public synchronized boolean finish(String token) {
            if (!valid(token) || received!=expected) { cancelCurrent();return false; }
            try {
                stream.getFD().sync();
                stream.close();
                stream=null;selecting=true;
                runOnUiThread(()->{
                    Intent save=new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    save.addCategory(Intent.CATEGORY_OPENABLE);
                    save.setType(mime);
                    save.putExtra(Intent.EXTRA_TITLE,filename);
                    try { startActivityForResult(save,PICK_EXPORT); }
                    catch (ActivityNotFoundException e) {
                        cancelCurrent();notifyUser("Android Save As dialog unavailable");
                    }
                });
                return true;
            } catch (IOException e) { cancelCurrent();return false; }
        }

        @JavascriptInterface public synchronized void cancel(String token) {
            if (valid(token) && !selecting) cancelCurrent();
        }

        private synchronized boolean valid(String token) {
            return token!=null && token.equals(id) && stream!=null && !selecting;
        }

        private synchronized void complete(Uri destination) {
            if (!selecting || temp==null) { cancelCurrent();return; }
            try {
                if (destination!=null) {
                    try(InputStream in=new FileInputStream(temp);
                        OutputStream out=getContentResolver().openOutputStream(destination,"w")) {
                        if (out==null) throw new IOException("Cannot open destination");
                        byte[] chunk=new byte[65536];int n;
                        while ((n=in.read(chunk))!=-1)out.write(chunk,0,n);
                        out.flush();
                    }
                    notifyUser("NEXUS file saved to selected Android destination");
                } else notifyUser("NEXUS export cancelled; no shared file written");
            } catch(IOException|SecurityException e) {
                notifyUser("NEXUS export could not be written to selected location");
            } finally { cancelCurrent(); }
        }

        private synchronized void cancelCurrent() {
            try { if(stream!=null)stream.close(); }catch(IOException ignored){}
            if(temp!=null)temp.delete();
            stream=null;temp=null;id=null;filename=null;mime=null;
            expected=received=0;selecting=false;
        }
    }
}
