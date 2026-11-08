package app.voidlock

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import org.json.JSONObject

/**
 * The whole app is a web page (assets/www) shown in a WebView. This class only hosts it: it serves the files from the APK over
 * https://appassets.androidplatform.net, lets the page pick files, forwards the Back button and hands over a .voidsync file that
 * was opened with VOIDLOCK. Everything native the page needs (network, share sheet, updates...) is in Bridge.kt.
 */
class MainActivity : Activity() {
    private lateinit var web: WebView
    private var fileCallback: ValueCallback<Array<Uri>>? = null
    private var pageReady = false
    private var pendingFile: Pair<String, String>? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        setContentView(web)
        web.setBackgroundColor(0xFF06121A.toInt())
        web.overScrollMode = View.OVER_SCROLL_NEVER

        val loader = WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        val s = web.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.allowFileAccess = false
        s.allowContentAccess = false
        s.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        s.textZoom = 100
        s.setSupportZoom(false)

        web.addJavascriptInterface(Bridge(this, web, this), "Android")

        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                return loader.shouldInterceptRequest(request.url)
            }

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                return true // the app never navigates away from its own page
            }

            override fun onPageFinished(view: WebView, url: String) {
                pageReady = true
                deliverPendingFile()
            }
        }

        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                webView: WebView,
                callback: ValueCallback<Array<Uri>>,
                params: FileChooserParams
            ): Boolean {
                fileCallback?.onReceiveValue(null)
                fileCallback = callback
                val pick = Intent(Intent.ACTION_GET_CONTENT)
                pick.addCategory(Intent.CATEGORY_OPENABLE)
                pick.type = "*/*"
                return try {
                    startActivityForResult(Intent.createChooser(pick, null), REQ_FILE)
                    true
                } catch (e: Exception) {
                    fileCallback = null
                    callback.onReceiveValue(null)
                    false
                }
            }
        }

        web.loadUrl(START_URL)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == REQ_FILE) {
            val cb = fileCallback
            fileCallback = null
            cb?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
        } else {
            super.onActivityResult(requestCode, resultCode, data)
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        // the page closes a sheet or goes back to Today; when there is nothing to close, the app goes to the background
        web.evaluateJavascript("window.__back ? window.__back() : false") { r ->
            if (r != "true") moveTaskToBack(true)
        }
    }

    override fun onStart() {
        super.onStart()
        visible = true
    }

    override fun onStop() {
        visible = false
        BgSync.soon(applicationContext, 20) // what was just typed reaches the computer soon, without waiting for the periodic run
        super.onStop()
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    // A .voidsync file opened with VOIDLOCK (file manager, messenger, Bluetooth): the page asks what to do with it.
    private fun handleIntent(i: Intent?) {
        if (i == null) return
        val found: Uri? = when (i.action) {
            Intent.ACTION_VIEW -> i.data
            Intent.ACTION_SEND -> streamUri(i)
            else -> null
        }
        val uri: Uri = found ?: return
        Thread {
            try {
                val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@Thread
                if (bytes.size > 60 * 1024 * 1024) return@Thread
                val text = String(bytes, Charsets.UTF_8)
                val name = uri.lastPathSegment ?: "sync.voidsync"
                runOnUiThread {
                    pendingFile = Pair(name, text)
                    deliverPendingFile()
                }
            } catch (e: Exception) {
                // not readable: ignore, the person can import it from inside the app
            }
        }.start()
    }

    @Suppress("DEPRECATION")
    private fun streamUri(i: Intent): Uri? {
        return if (Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else i.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
    }

    private fun deliverPendingFile() {
        val p = pendingFile ?: return
        if (!pageReady) return
        pendingFile = null
        val js = "window.__native && window.__native.onOpenFile(" + JSONObject.quote(p.first) + "," + JSONObject.quote(p.second) + ")"
        web.evaluateJavascript(js, null)
    }

    companion object {
        @Volatile
        var visible = false
        const val START_URL = "https://appassets.androidplatform.net/assets/www/index.html"
        const val REQ_FILE = 41
    }
}
