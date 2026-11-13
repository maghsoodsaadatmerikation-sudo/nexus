package org.nexus.offline.stage26.test;

import android.app.Activity;
import android.app.Instrumentation;
import android.app.UiAutomation;
import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityNodeInfo;
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
                    "url:location.href})");
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
            "criteria:['Human review required'],steps:['Synthetic task']," +
            "assistant_profile:{name:'Stage27 verifier'," +
            "instructions:'SYNTHETIC_STAGE27_PROFILE',style:'concise'}," +
            "memory:['SYNTHETIC_STAGE27_MEMORY']});" +
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
            "if(raw.includes('" + MARK + "')||" +
            "raw.includes('SYNTHETIC_STAGE27_MEMORY')||" +
            "raw.includes('SYNTHETIC_STAGE27_PROFILE'))" +
            "throw Error('plaintext-backup');" +
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
            "if(project.assistant_profile.name!=='Stage27 verifier'||" +
            "project.assistant_profile.style!=='concise'||" +
            "project.assistant_profile.instructions!=='SYNTHETIC_STAGE27_PROFILE'||" +
            "project.memory.length!==1||" +
            "project.memory[0]!=='SYNTHETIC_STAGE27_MEMORY')" +
            "throw Error('custom-profile-or-memory-lost-after-reopen');" +
            "let env=JSON.parse(await v.backup());" +
            "env.ciphertext='AA'+env.ciphertext.slice(2);" +
            "let tamperDenied=false;" +
            "try{await v.restore('" + PASS + "',JSON.stringify(env))}" +
            "catch(e){tamperDenied=true}" +
            "if(!tamperDenied)throw Error('tampered-archive-accepted');" +
            "return {reopened:true,wrongDenied,tamperDenied," +
            "stillDone:v.get(all[0].id).tasks[0].status==='done'," +
            "profileMemoryReopened:v.get(all[0].id).memory[0]===" +
            "'SYNTHETIC_STAGE27_MEMORY'};";
        JSONObject result=asyncScript(view,js);
        check(result.getBoolean("reopened"), "independent-activity-reopen");
        check(result.getBoolean("wrongDenied"), "wrong-password-refused");
        check(result.getBoolean("tamperDenied"), "tampered-backup-refused");
        check(result.getBoolean("stillDone"), "failed-restore-keeps-project");
        check(result.getBoolean("profileMemoryReopened"),
              "encrypted-custom-assistant-and-project-memory-survive-Android-reopen");
    }

    private void confirmActualSystemDocumentPicker(String name) throws Exception {
        UiAutomation automation=getUiAutomation();
        String lastPackage="none";
        for(int i=0;i<120;i++) {
            AccessibilityNodeInfo root=automation.getRootInActiveWindow();
            if(root!=null&&root.getPackageName()!=null) {
                lastPackage=root.getPackageName().toString();
                // A real OS document UI window, NOT a fabricated app dialog.
                if(lastPackage.toLowerCase().contains("documentsui")) {
                    check(true,name);
                    check(automation.performGlobalAction(
                          AccessibilityService.GLOBAL_ACTION_BACK),
                          "android-document-picker-back");
                    SystemClock.sleep(550);
                    return;
                }
            }
            SystemClock.sleep(100);
        }
        // Package only: no file names, project data, clipboard or UI contents.
        throw new IllegalStateException("stage26-"+name+"-not-visible-package_"+
            lastPackage.replaceAll("[^a-zA-Z0-9_.]","_"));
    }

    private void testDocumentPickers(Activity activity,WebView view) throws Exception {
        JSONObject nativeBridge=json(view,
            "({present:!!window.NEXUS_NATIVE_EXPORT," +
            "callable:typeof(window.NEXUS_NATIVE_EXPORT&&" +
            "window.NEXUS_NATIVE_EXPORT.save)==='function'," +
            "origin:location.href})");
        check(nativeBridge.getBoolean("present") &&
              nativeBridge.getBoolean("callable") &&
              URL.equals(nativeBridge.getString("origin")),
              "native-export-bridge-not-bound");

        // Accessibility observes the actual Android DocumentsUI activity.
        // Instrumentation.ActivityMonitor did not intercept this cross-process
        // SAF launch; a real DocumentsUI window is stronger runtime proof.
        getUiAutomation().getRootInActiveWindow();
        evaluate(view,
            "NEXUS_NATIVE_EXPORT.save('nexus-stage26.synthetic.json'," +
            "btoa('offline-synthetic-encrypted-export'))");
        confirmActualSystemDocumentPicker("native-save-picker-approval-required");

        // Android DocumentsUI closes asynchronously. The native Activity
        // must receive RESULT_CANCELED before it may open a different picker.
        // Never bypass the production guard; wait until it really clears.
        AtomicReference<Boolean> exportReleased=new AtomicReference<>(false);
        for(int i=0;i<120;i++) {
            runOnMainSync(()->{
                try {
                    Field field=activity.getClass().getDeclaredField("pendingExport");
                    field.setAccessible(true);
                    Field chooserField=activity.getClass().getDeclaredField("chooser");
                    chooserField.setAccessible(true);
                    exportReleased.set(field.get(activity)==null &&
                                       chooserField.get(activity)==null);
                } catch(Exception exception) {
                    exportReleased.set(false);
                }
            });
            if(Boolean.TRUE.equals(exportReleased.get()))break;
            SystemClock.sleep(100);
        }
        check(Boolean.TRUE.equals(exportReleased.get()),
              "android-document-export-cancellation-clears-native-pending-state");

        AtomicReference<Boolean> importHook=new AtomicReference<>(false);
        runOnMainSync(()->{
            WebChromeClient chrome=view.getWebChromeClient();
            ValueCallback<Uri[]> callback=uris-> {};
            importHook.set(chrome!=null &&
                chrome.onShowFileChooser(view,callback,null));
        });
        check(Boolean.TRUE.equals(importHook.get()),"native-import-chooser-hook");
        confirmActualSystemDocumentPicker("native-open-picker-approval-required");
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
            JSONObject workers=asyncScript(page,
                "const sw=navigator.serviceWorker;" +
                "const registrations=sw&&sw.getRegistrations?" +
                "await sw.getRegistrations():[];" +
                "return {installed:registrations.length,controlled:!!(sw&&sw.controller)};");
            check(workers.getInt("installed")==0 &&
                  !workers.getBoolean("controlled"),"no-active-or-installed-service-worker");
            AtomicReference<boolean[]> flags = new AtomicReference<>();
            runOnMainSync(()->{
                WebSettings settings=page.getSettings();
                flags.set(new boolean[]{!settings.getAllowFileAccess(),
                                        !settings.getAllowContentAccess()});
            });
            check(flags.get()[0],"no-arbitrary-file-access");
            check(flags.get()[1],"no-ambient-provider-access");
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
