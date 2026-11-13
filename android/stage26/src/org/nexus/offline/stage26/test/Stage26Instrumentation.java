package org.nexus.offline.stage26.test;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebSettings;
import java.lang.reflect.Field;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONObject;
import org.json.JSONTokener;

/**
 * Real Android platform instrumentation (not desktop Chromium).
 * Runs in the original app process, with no networking or provider token.
 * All values are synthetic. Fails closed; sends no plaintext to CI.
 */
public final class Stage26Instrumentation extends Instrumentation {
    private static final String PACKAGE = "org.nexus.offline.stage25";
    private static final String URL =
        "https://appassets.androidplatform.net/nexus/index.html";
    private static final String PASS = "Stage26-SYNTHETIC-Encrypted-Project-Only";
    private static final String MARK = "SYNTHETIC_STAGE26_DO_NOT_USE";
    private int assertions = 0;

    private void check(boolean okay, String name) {
        if (!okay) throw new IllegalStateException("stage26-" + name);
        assertions++;
    }

    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        start();
    }

    private Activity launch() throws Exception {
        Intent intent = new Intent();
        intent.setClassName(PACKAGE, PACKAGE + ".MainActivity");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        Activity activity = startActivitySync(intent);
        check(activity != null, "activity-launch");
        return activity;
    }

    private WebView webView(Activity activity) throws Exception {
        Field field = activity.getClass().getDeclaredField("webView");
        field.setAccessible(true);
        WebView view = (WebView) field.get(activity);
        check(view != null, "native-webview");
        return view;
    }

    private String evaluate(WebView view, String expression) throws Exception {
        CountDownLatch event = new CountDownLatch(1);
        AtomicReference<String> output = new AtomicReference<>();
        runOnMainSync(() -> view.evaluateJavascript(expression, value -> {
            output.set(value);
            event.countDown();
        }));
        if (!event.await(12, TimeUnit.SECONDS)) {
            throw new IllegalStateException("stage26-webview-js-timeout");
        }
        String result = output.get();
        if (result == null) throw new IllegalStateException("stage26-null-js");
        Object decoded = new JSONTokener(result).nextValue();
        return decoded instanceof String ? (String) decoded : result;
    }

    private JSONObject json(WebView view, String expression) throws Exception {
        return new JSONObject(evaluate(view, "JSON.stringify(" + expression + ")"));
    }

    private JSONObject awaitPage(WebView view) throws Exception {
        for (int i=0; i<80; i++) {
            try {
                JSONObject result = json(view,
                    "({ready:document.readyState==='complete'&&" +
                    "!!document.getElementById('native-android')&&" +
                    "!!globalThis.NexusWorkMode," +
                    "url:location.href,worker:!!navigator.serviceWorker})");
                if (result.optBoolean("ready",false)) return result;
            } catch (Exception ignored) {
                // WebView may not have committed the first document yet.
            }
            SystemClock.sleep(250);
        }
        throw new IllegalStateException("stage26-local-page-never-loaded");
    }

    private JSONObject asyncScript(WebView view, String javascript) throws Exception {
        evaluate(view, "window.__stage26Proof=null");
        evaluate(view,
            "(async()=>{try{let result=await (async()=>{" + javascript +
            "})();window.__stage26Proof={status:'PASS',result};}" +
            "catch(e){window.__stage26Proof={status:'FAILED'," +
            "reason:String(e&&e.message||e).slice(0,100)};}})()");
        for (int i=0; i<180; i++) {
            try {
                String value = evaluate(view, "JSON.stringify(window.__stage26Proof)");
                if (!"null".equals(value)) {
                    JSONObject proof = new JSONObject(value);
                    if (!"PASS".equals(proof.optString("status"))) {
                        throw new IllegalStateException(
                            "stage26-synthetic-js-failure:" + proof.optString("reason"));
                    }
                    return proof.getJSONObject("result");
                }
            } catch (org.json.JSONException ignored) {}
            SystemClock.sleep(250);
        }
        throw new IllegalStateException("stage26-crypto-or-indexeddb-timeout");
    }

    private void testPersistenceAndHumanReview(WebView view) throws Exception {
        String js =
            "const W=NexusWorkMode,pass='" + PASS + "';" +
            "const v=new W.Vault();" +
            "await v.create(pass);" +
            "let project=W.create({title:'" + MARK + "',goal:'Synthetic offline goal'," +
            "criteria:['Human review required'],steps:['Synthetic task']});" +
            "const task=project.tasks[0];let denied=false;" +
            "try{W.update(project,'edit_task',{id:task.id,title:task.title," +
            "status:'done',dependencies:[],evidence:'',file_ids:[],reviewed:false});}" +
            "catch(e){denied=e.message==='work-review-required'}" +
            "if(!denied)throw Error('human-review-was-bypassed');" +
            "project=W.update(project,'edit_task',{id:task.id,title:task.title," +
            "status:'done',dependencies:[],evidence:'Synthetic manually reviewed'," +
            "file_ids:[],reviewed:true});" +
            "await v.save(project);" +
            "const raw=await v.backup();" +
            "if(raw.includes('" + MARK + "'))throw Error('plaintext-backup');" +
            "v.lock();" +
            "return {saved:true,done:project.tasks[0].status==='done'," +
            "reviewed:project.tasks[0].reviewed===true,denied:denied," +
            "plaintextBackup:false,origin:location.href};";
        JSONObject result=asyncScript(view,js);
        check(result.getBoolean("saved"), "encrypted-persisted");
        check(result.getBoolean("done")&&result.getBoolean("reviewed"),
              "human-reviewed-done");
        check(result.getBoolean("denied"), "unreviewed-done-blocked");
        check(!result.getBoolean("plaintextBackup"), "private-backup");
        check(URL.equals(result.getString("origin")), "exact-origin");
    }

    private void testIndependentReopen(WebView view) throws Exception {
        String js =
            "const W=NexusWorkMode,v=new W.Vault();" +
            "let wrongDenied=false;" +
            "try{await v.unlock('incorrect-synthetic-password')}catch(e){" +
            "wrongDenied=e.message==='work-unlock-failed'}" +
            "if(!wrongDenied)throw Error('wrong-key-accepted');" +
            "await v.unlock('" + PASS + "');" +
            "const all=v.list();" +
            "if(all.length!==1)throw Error('missing-saved-project');" +
            "const project=v.get(all[0].id);" +
            "if(project.title!=='" + MARK + "'||project.tasks.length!==1||" +
            "project.tasks[0].status!=='done'||!project.tasks[0].reviewed)" +
            "throw Error('saved-project-changed');" +
            "let env=JSON.parse(await v.backup());" +
            "env.ciphertext='AA'+env.ciphertext.slice(2);" +
            "let tamperDenied=false;" +
            "try{await v.restore('" + PASS + "',JSON.stringify(env))}" +
            "catch(e){tamperDenied=true}" +
            "if(!tamperDenied)throw Error('tampered-archive-accepted');" +
            "return {reopened:true,wrongDenied,tamperDenied," +
            "stillDone:v.get(all[0].id).tasks[0].status==='done'};";
        JSONObject result=asyncScript(view,js);
        check(result.getBoolean("reopened"), "independent-activity-reopen");
        check(result.getBoolean("wrongDenied"), "wrong-password-refused");
        check(result.getBoolean("tamperDenied"), "tampered-backup-refused");
        check(result.getBoolean("stillDone"), "failed-restore-keeps-project");
    }

    private void waitForHits(ActivityMonitor monitor, String name) {
        for(int i=0;i<60 && monitor.getHits()<1;i++) SystemClock.sleep(100);
        check(monitor.getHits()>=1,name);
    }

    private void testDocumentPickers(Activity activity,WebView view) throws Exception {
        IntentFilter write=new IntentFilter(Intent.ACTION_CREATE_DOCUMENT);
        ActivityMonitor outbound=addMonitor(write,
            new ActivityResult(Activity.RESULT_CANCELED,null),true);
        try {
            evaluate(view,
                "NEXUS_NATIVE_EXPORT.save('nexus-stage26.synthetic.json'," +
                "btoa('offline-synthetic-encrypted-export'))");
            waitForHits(outbound,"native-save-picker-approval-required");
        } finally {
            removeMonitor(outbound);
        }

        IntentFilter read=new IntentFilter(Intent.ACTION_OPEN_DOCUMENT);
        ActivityMonitor inbound=addMonitor(read,
            new ActivityResult(Activity.RESULT_CANCELED,null),true);
        try {
            AtomicReference<Boolean> result=new AtomicReference<>(false);
            runOnMainSync(()->{
                WebChromeClient chrome=view.getWebChromeClient();
                ValueCallback<Uri[]> callback=uris-> {};
                result.set(chrome!=null &&
                    chrome.onShowFileChooser(view,callback,null));
            });
            check(Boolean.TRUE.equals(result.get()),"native-import-chooser-hook");
            waitForHits(inbound,"native-open-picker-approval-required");
        } finally {
            removeMonitor(inbound);
        }
    }

    @Override public void onStart() {
        super.onStart();
        Bundle result = new Bundle();
        result.putString("schema","nexus.stage26.android-emulator.v1");
        result.putString("real_android_hardware","false");
        result.putString("real_android_emulator","true");
        result.putString("synthetic_only","true");
        result.putString("original_Railway_data","not_accessed");
        result.putString("network_permission","none");
        Activity first=null,second=null;
        try {
            first=launch();
            WebView page=webView(first);
            JSONObject initial=awaitPage(page);
            check(URL.equals(initial.getString("url")),"local-asset-origin");
            check(!initial.getBoolean("worker"),"no-service-worker");
            WebSettings settings=page.getSettings();
            check(!settings.getAllowFileAccess(),"no-arbitrary-file-access");
            check(!settings.getAllowContentAccess(),"no-ambient-provider-access");
            testPersistenceAndHumanReview(page);
            Activity old=first;
            runOnMainSync(old::finish);
            SystemClock.sleep(650);
            second=launch();
            WebView reopened=webView(second);
            JSONObject current=awaitPage(reopened);
            check(URL.equals(current.getString("url")),"reopened-on-reviewed-origin");
            testIndependentReopen(reopened);
            testDocumentPickers(second,reopened);
            result.putString("status","PASS");
            result.putInt("checks",assertions);
            result.putString("proof",
                "native-launch;local-asset-origin;real-webview-crypto;" +
                "encrypted-idb-reopen;human-review;tamper-rejection;" +
                "document-open-save-pickers");
            finish(Activity.RESULT_OK,result);
        } catch(Throwable failure) {
            result.putString("status","FAILED");
            result.putString("reason",String.valueOf(failure.getMessage())
                .replaceAll("[^a-zA-Z0-9_:\\-]","_").substring(0,
                    Math.min(120,String.valueOf(failure.getMessage()).length())));
            result.putInt("checks_before_failure",assertions);
            finish(Activity.RESULT_CANCELED,result);
        }
    }
}
