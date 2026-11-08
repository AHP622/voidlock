package app.voidlock

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequest
import androidx.work.PeriodicWorkRequest
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Syncs with the computer while the app is closed. The sync itself is the same JavaScript as in the app (it is the only copy of the
 * merge rules), so this worker opens the app page in a WebView that has no screen, with "#bg" in the address: the page then does one
 * sync, saves, and calls Android.bgDone(). It never runs while the app is on the screen (the app syncs by itself then).
 * Android decides the exact time (at least every 15 minutes, later in power-saving), so this is "every now and then", not live.
 */
class SyncWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        if (MainActivity.visible) return Result.success()
        if (!BgSync.enabled(applicationContext)) return Result.success()
        val ctx = applicationContext
        val done = CountDownLatch(1)
        val holder = arrayOfNulls<WebView>(1)
        val main = Handler(Looper.getMainLooper())
        main.post {
            try {
                val web = WebView(ctx)
                holder[0] = web
                val s = web.settings
                s.javaScriptEnabled = true
                s.domStorageEnabled = true
                s.allowFileAccess = false
                s.allowContentAccess = false
                s.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                val loader = WebViewAssetLoader.Builder()
                    .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(ctx))
                    .build()
                val bridge = Bridge(ctx, web, null)
                bridge.onBgDone = { done.countDown() }
                web.addJavascriptInterface(bridge, "Android")
                web.webViewClient = object : WebViewClient() {
                    override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                        return loader.shouldInterceptRequest(request.url)
                    }

                    override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                        return true
                    }
                }
                web.loadUrl(MainActivity.START_URL + "#bg")
            } catch (e: Exception) {
                done.countDown()
            }
        }
        done.await(75, TimeUnit.SECONDS)
        main.post {
            try {
                holder[0]?.destroy()
            } catch (e: Exception) {
                // already gone
            }
        }
        return Result.success()
    }
}

/** Switches the background sync on or off and schedules it. */
object BgSync {
    private const val PREFS = "voidlock"
    private const val KEY = "bg_sync"
    private const val PERIODIC = "voidlock-bg-sync"
    private const val ONCE = "voidlock-bg-once"

    fun enabled(ctx: Context): Boolean = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(KEY, false)

    private fun constraints(): Constraints =
        Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    fun apply(ctx: Context, on: Boolean) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(KEY, on).apply()
        val wm = WorkManager.getInstance(ctx)
        if (on) {
            val req = PeriodicWorkRequest.Builder(SyncWorker::class.java, 15, TimeUnit.MINUTES)
                .setConstraints(constraints())
                .build()
            wm.enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, req)
        } else {
            wm.cancelUniqueWork(PERIODIC)
            wm.cancelUniqueWork(ONCE)
        }
    }

    /** One sync soon after the app was left, so what was just typed on the phone reaches the computer without waiting. */
    fun soon(ctx: Context, delaySeconds: Long) {
        if (!enabled(ctx)) return
        val req = OneTimeWorkRequest.Builder(SyncWorker::class.java)
            .setInitialDelay(delaySeconds, TimeUnit.SECONDS)
            .setConstraints(constraints())
            .build()
        WorkManager.getInstance(ctx).enqueueUniqueWork(ONCE, ExistingWorkPolicy.REPLACE, req)
    }
}
