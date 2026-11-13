package app.voidlock

import android.app.Activity
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.print.PrintAttributes
import android.print.PrintManager
import android.provider.MediaStore
import android.provider.Settings
import android.util.Base64
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.core.content.FileProvider
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.net.Inet4Address
import java.net.HttpURLConnection
import java.net.NetworkInterface
import java.net.URL
import java.security.MessageDigest

/**
 * What the web page can ask the phone to do (window.Android in the page, see assets/www/js/native.js).
 * Calls from the page arrive on a background thread; results go back by calling window.__native.* on the main thread.
 * `activity` is null when the page runs without a screen (the background sync, see SyncWorker): then only the network and
 * device functions are used.
 */
class Bridge(private val ctx: Context, private val web: WebView, private val activity: Activity?) {
    private val main = Handler(Looper.getMainLooper())
    private var printView: WebView? = null

    // ---- reminders and notifications (see Reminders.kt)
    @JavascriptInterface
    fun scheduleReminders(json: String) {
        try { Reminders.schedule(ctx, json) } catch (_: Exception) { }
    }

    @JavascriptInterface
    fun showNotification(title: String, text: String, id: String) {
        try { Reminders.show(ctx, if (id.isEmpty()) "n" + System.currentTimeMillis() else id, title, text, Reminders.CH_UPDATE) } catch (_: Exception) { }
    }

    @JavascriptInterface
    fun notificationsAllowed(): Boolean = try { Reminders.allowed(ctx) } catch (_: Exception) { false }

    @JavascriptInterface
    fun requestNotifications() {
        val a = activity ?: return
        main.post {
            try {
                if (Build.VERSION.SDK_INT >= 33) a.requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 71)
                else a.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName))
            } catch (_: Exception) { }
        }
    }

    @JavascriptInterface
    fun canExactAlarms(): Boolean = try { Reminders.canExact(ctx) } catch (_: Exception) { false }

    @JavascriptInterface
    fun openAlarmSettings() {
        val a = activity ?: return
        main.post {
            try {
                if (Build.VERSION.SDK_INT >= 31) a.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:" + ctx.packageName)))
            } catch (_: Exception) { }
        }
    }

    /** Called by the page when a background sync is over. */
    var onBgDone: (() -> Unit)? = null

    private fun js(code: String) {
        main.post { web.evaluateJavascript(code, null) }
    }

    @JavascriptInterface
    fun deviceName(): String {
        val maker = Build.MANUFACTURER ?: ""
        val model = Build.MODEL ?: "Android"
        return if (model.startsWith(maker, ignoreCase = true)) model else "$maker $model".trim()
    }

    @JavascriptInterface
    fun appVersion(): String {
        return try {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "0"
        } catch (e: Exception) {
            "0"
        }
    }

    /** Private IPv4 addresses of Wi-Fi / hotspot interfaces: the page scans these networks for the computer. */
    @JavascriptInterface
    fun localIps(): String {
        val out = JSONArray()
        try {
            val all = NetworkInterface.getNetworkInterfaces()
            while (all != null && all.hasMoreElements()) {
                val ni = all.nextElement()
                if (!ni.isUp || ni.isLoopback) continue
                if (!Regex("^(wlan|swlan|ap|eth|p2p).*").matches(ni.name)) continue // not the mobile-data interfaces
                val addrs = ni.inetAddresses
                while (addrs.hasMoreElements()) {
                    val a = addrs.nextElement()
                    if (a is Inet4Address && a.isSiteLocalAddress) out.put(a.hostAddress)
                }
            }
        } catch (e: Exception) {
            // no addresses: the page lets the person type the address
        }
        return out.toString()
    }

    @JavascriptInterface
    fun keepAwake(on: Boolean) {
        val a = activity ?: return
        main.post {
            if (on) a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else a.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    /** The page tells whether it should sync by itself in the background (every ~15 minutes and when the app is left). */
    @JavascriptInterface
    fun setBackgroundSync(on: Boolean) {
        BgSync.apply(ctx, on)
    }

    @JavascriptInterface
    fun bgDone(ok: Boolean) {
        onBgDone?.invoke()
    }

    /** The Wi-Fi network itself (not the VPN on top of it): a VPN app on the phone sends everything, even addresses of the home
     *  network, into its tunnel; a connection bound to the Wi-Fi network goes straight to the computer. */
    private fun lanNetwork(): Network? {
        return try {
            val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            @Suppress("DEPRECATION")
            cm.allNetworks.firstOrNull { n ->
                val c = cm.getNetworkCapabilities(n)
                c != null && !c.hasTransport(NetworkCapabilities.TRANSPORT_VPN) &&
                    (c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))
            }
        } catch (e: Exception) {
            null
        }
    }

    // ---------------------------------------------------------------- network (no browser CORS / mixed-content rules)
    @JavascriptInterface
    fun http(id: String, method: String, url: String, headersJson: String, body: String, timeoutMs: Int) {
        Thread {
            var status = 0
            var text = ""
            try {
                val u = URL(url)
                val allowed = u.protocol == "https" || (u.protocol == "http" && isPrivateHost(u.host ?: ""))
                if (!allowed) throw IOException("blocked address")
                val lan = if (u.protocol == "http") lanNetwork() else null
                val c = (if (lan != null) lan.openConnection(u) else u.openConnection()) as HttpURLConnection
                c.requestMethod = method
                c.connectTimeout = timeoutMs
                c.readTimeout = timeoutMs
                c.instanceFollowRedirects = true
                c.setRequestProperty("User-Agent", "VOIDLOCK-Android")
                val hs = JSONObject(headersJson)
                for (k in hs.keys()) c.setRequestProperty(k, hs.getString(k))
                if (body.isNotEmpty()) {
                    val bytes = body.toByteArray(Charsets.UTF_8)
                    c.doOutput = true
                    c.setFixedLengthStreamingMode(bytes.size)
                    c.outputStream.use { it.write(bytes) }
                }
                status = c.responseCode
                val stream = if (status in 200..399) c.inputStream else c.errorStream
                text = stream?.use { String(it.readBytes(), Charsets.UTF_8) } ?: ""
            } catch (e: Exception) {
                status = 0
                text = e.toString()
            }
            val b64 = Base64.encodeToString(text.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
            js("window.__native.onHttp('$id',$status,'$b64')")
        }.start()
    }

    /** Plain HTTP is only used for the computer on the local network. */
    private fun isPrivateHost(host: String): Boolean {
        val p = host.split(".")
        if (p.size != 4) return false
        val n = p.map { it.toIntOrNull() ?: return false }
        if (n.any { it < 0 || it > 255 }) return false
        return n[0] == 10 || n[0] == 127 || (n[0] == 192 && n[1] == 168) || (n[0] == 172 && n[1] in 16..31)
    }

    // ---------------------------------------------------------------- files
    @JavascriptInterface
    fun shareFile(name: String, mime: String, text: String) {
        main.post {
            try {
                val dir = File(ctx.cacheDir, "share")
                dir.mkdirs()
                val f = File(dir, name.replace(Regex("[^A-Za-z0-9._-]"), "_"))
                f.writeText(text, Charsets.UTF_8)
                val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".fileprovider", f)
                val send = Intent(Intent.ACTION_SEND)
                send.type = mime
                send.putExtra(Intent.EXTRA_STREAM, uri)
                send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                val chooser = Intent.createChooser(send, name)
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                ctx.startActivity(chooser)
            } catch (e: Exception) {
                Toast.makeText(ctx, "Could not share the file: " + e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    /** Prints an HTML page (the report): in the Android print dialog the person can choose "Save as PDF". */
    @JavascriptInterface
    fun printHtml(title: String, html: String) {
        val a = activity ?: return
        main.post {
            try {
                val wv = WebView(a)
                wv.settings.javaScriptEnabled = false
                wv.webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView, url: String) {
                        val pm = a.getSystemService(Context.PRINT_SERVICE) as PrintManager
                        val attrs = PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build()
                        pm.print(title, view.createPrintDocumentAdapter(title), attrs)
                    }
                }
                printView = wv // keep it alive while the print dialog is open
                wv.loadDataWithBaseURL("https://appassets.androidplatform.net/", html, "text/html", "utf-8", null)
            } catch (e: Exception) {
                Toast.makeText(ctx, "Could not print: " + e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    @JavascriptInterface
    fun saveFile(name: String, mime: String, text: String): String {
        return try {
            if (Build.VERSION.SDK_INT >= 29) {
                val v = ContentValues()
                v.put(MediaStore.Downloads.DISPLAY_NAME, name)
                v.put(MediaStore.Downloads.MIME_TYPE, mime)
                v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                val uri = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v) ?: return "error"
                ctx.contentResolver.openOutputStream(uri)?.use { it.write(text.toByteArray(Charsets.UTF_8)) }
            } else {
                val dir = ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                File(dir, name).writeText(text, Charsets.UTF_8)
            }
            "ok"
        } catch (e: Exception) {
            "error"
        }
    }

    // ---------------------------------------------------------------- updates from GitHub
    @JavascriptInterface
    fun openInstallSettings() {
        main.post {
            try {
                val i = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + ctx.packageName))
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                ctx.startActivity(i)
            } catch (e: Exception) {
                // the person can open it from the system settings
            }
        }
    }

    /** Downloads the APK, checks its SHA-256 against the .sha256 file of the release and its package name, then opens the installer.
     *  Android itself refuses the install unless the APK is signed with the same key as this app. */
    @JavascriptInterface
    fun installApk(url: String, shaUrl: String) {
        Thread {
            try {
                if (!allowedUpdateUrl(url) || !allowedUpdateUrl(shaUrl)) {
                    js("window.__native.onApk('error'," + JSONObject.quote("blocked address") + ",0)")
                    return@Thread
                }
                if (Build.VERSION.SDK_INT >= 26 && !ctx.packageManager.canRequestPackageInstalls()) {
                    js("window.__native.onApk('need_permission',0,0)")
                    return@Thread
                }
                val expected = String(download(shaUrl, null), Charsets.UTF_8).trim().split(Regex("\\s+"))[0].lowercase()
                if (expected.length != 64) throw IOException("the checksum file is not valid")
                val bytes = download(url) { done, total -> js("window.__native.onApk('downloading',$done,$total)") }
                js("window.__native.onApk('verifying',0,0)")
                val got = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
                if (got != expected) throw IOException("the checksum does not match")
                val dir = File(ctx.cacheDir, "updates")
                dir.mkdirs()
                dir.listFiles()?.forEach { it.delete() }
                val f = File(dir, "VoidLock.apk")
                f.writeBytes(bytes)
                val info = ctx.packageManager.getPackageArchiveInfo(f.absolutePath, 0)
                if (info == null || info.packageName != ctx.packageName) throw IOException("this is not a VOIDLOCK package")
                val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".fileprovider", f)
                val view = Intent(Intent.ACTION_VIEW)
                view.setDataAndType(uri, "application/vnd.android.package-archive")
                view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                main.post { ctx.startActivity(view) }
                js("window.__native.onApk('ready',0,0)")
            } catch (e: Exception) {
                js("window.__native.onApk('error'," + JSONObject.quote(e.message ?: e.toString()) + ",0)")
            }
        }.start()
    }

    private fun allowedUpdateUrl(u: String): Boolean {
        return try {
            val x = URL(u)
            x.protocol == "https" && listOf("github.com", "githubusercontent.com").any { x.host == it || x.host.endsWith(".$it") }
        } catch (e: Exception) {
            false
        }
    }

    private fun download(url: String, progress: ((Long, Long) -> Unit)?): ByteArray {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 15000
        c.readTimeout = 30000
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "VOIDLOCK-Android")
        if (c.responseCode !in 200..299) throw IOException("HTTP " + c.responseCode)
        if (!allowedUpdateUrl(c.url.toString())) throw IOException("the download was redirected to an address that is not allowed")
        val total = c.contentLengthLong
        val out = ByteArrayOutputStream()
        val buf = ByteArray(65536)
        var done = 0L
        var last = 0L
        c.inputStream.use { ins ->
            while (true) {
                val n = ins.read(buf)
                if (n < 0) break
                out.write(buf, 0, n)
                done += n
                val now = System.currentTimeMillis()
                if (progress != null && now - last > 300) {
                    last = now
                    progress(done, total)
                }
            }
        }
        return out.toByteArray()
    }
}
