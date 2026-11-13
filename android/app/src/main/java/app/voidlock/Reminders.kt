package app.voidlock

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import org.json.JSONArray

/**
 * Notifications that must arrive even when the app is closed: class reminders, exam reminders and the "new version" notice.
 * The page decides WHAT and WHEN (assets/www/js/notify.js) and hands over a JSON list [{id, at (ms), title, text, channel}];
 * this object keeps one alarm per item and shows the notification when it fires. The list is remembered, so the alarms are
 * set again after a restart of the phone or an update of the app (BootReceiver).
 */
object Reminders {
    const val CH_CLASS = "class"
    const val CH_EXAM = "exam"
    const val CH_UPDATE = "update"
    private const val PREFS = "voidlock_reminders"
    private const val KEY_PLAN = "plan"
    private const val ACTION = "app.voidlock.REMINDER"

    fun ensureChannels(ctx: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        fun make(id: String, name: String, importance: Int) {
            if (nm.getNotificationChannel(id) == null) nm.createNotificationChannel(NotificationChannel(id, name, importance))
        }
        make(CH_CLASS, "Class reminders", NotificationManager.IMPORTANCE_HIGH)
        make(CH_EXAM, "Exam reminders", NotificationManager.IMPORTANCE_HIGH)
        make(CH_UPDATE, "App updates", NotificationManager.IMPORTANCE_DEFAULT)
    }

    fun allowed(ctx: Context): Boolean {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return false
        if (Build.VERSION.SDK_INT >= 33 && ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false
        return nm.areNotificationsEnabled()
    }

    fun canExact(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < 31) return true
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return false
        return am.canScheduleExactAlarms()
    }

    private fun pending(ctx: Context, id: String, title: String, text: String, channel: String): PendingIntent {
        val i = Intent(ctx, ReminderReceiver::class.java).setAction(ACTION)
            .putExtra("id", id).putExtra("title", title).putExtra("text", text).putExtra("channel", channel)
        return PendingIntent.getBroadcast(ctx, id.hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    /** Replaces the planned alarms by `json` (a JSON array, see the class comment). */
    fun schedule(ctx: Context, json: String) {
        ensureChannels(ctx)
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        try {                                            // forget the old plan
            val old = JSONArray(prefs.getString(KEY_PLAN, "[]"))
            for (k in 0 until old.length()) {
                val o = old.getJSONObject(k)
                am.cancel(pending(ctx, o.getString("id"), o.optString("title"), o.optString("text"), o.optString("channel", CH_CLASS)))
            }
        } catch (_: Exception) {
        }
        val now = System.currentTimeMillis()
        val keep = JSONArray()
        val arr = JSONArray(json)
        val exact = canExact(ctx)
        for (k in 0 until arr.length()) {
            val o = arr.getJSONObject(k)
            val at = o.getLong("at")
            if (at < now - 60_000) continue              // long gone
            val whenMs = if (at < now) now + 2_000 else at
            val pi = pending(ctx, o.getString("id"), o.optString("title"), o.optString("text"), o.optString("channel", CH_CLASS))
            if (exact) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMs, pi)
            else am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, whenMs, pi)   // without the exact-alarm permission: within a few minutes
            keep.put(o)
        }
        prefs.edit().putString(KEY_PLAN, keep.toString()).apply()
    }

    /** After a restart / app update: set the remembered alarms again. */
    fun restore(ctx: Context) {
        val plan = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_PLAN, null) ?: return
        try {
            schedule(ctx, plan)
        } catch (_: Exception) {
        }
    }

    fun show(ctx: Context, id: String, title: String, text: String, channel: String) {
        if (!allowed(ctx)) return
        ensureChannels(ctx)
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val n = Notification.Builder(ctx, if (Build.VERSION.SDK_INT >= 26) channel else CH_CLASS)
            .setSmallIcon(R.drawable.ic_stat_notify)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .setCategory(if (channel == CH_UPDATE) Notification.CATEGORY_RECOMMENDATION else Notification.CATEGORY_REMINDER)
            .build()
        nm.notify(id.hashCode(), n)
    }
}

/** The alarm fired: show the notification. */
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val id = intent.getStringExtra("id") ?: return
        Reminders.show(ctx, id, intent.getStringExtra("title") ?: "", intent.getStringExtra("text") ?: "", intent.getStringExtra("channel") ?: Reminders.CH_CLASS)
    }
}

/** Phone restarted or the app was updated: alarms are gone, set them again. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val a = intent.action
        if (a == Intent.ACTION_BOOT_COMPLETED || a == Intent.ACTION_MY_PACKAGE_REPLACED) Reminders.restore(ctx)
    }
}
