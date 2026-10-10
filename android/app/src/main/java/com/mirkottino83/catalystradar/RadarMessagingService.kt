package com.mirkottino83.catalystradar

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class RadarMessagingService : FirebaseMessagingService() {
    private val channelId = "radar_catalysts"
    private val validHost = "mirkottino83-eng.github.io"
    private val home = "https://mirkottino83-eng.github.io/catalyst-radar/"

    override fun onMessageReceived(message: RemoteMessage) {
        val enabled = getSharedPreferences("catalyst_radar_push", MODE_PRIVATE)
            .getBoolean("enabled", false)
        if (!enabled) return
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return

        // The trusted scanner only sends data payloads (not notification payloads);
        // we create the OS notification after confirming this phone opted in.
        val data = message.data
        val title = data["title"]?.take(100) ?: return
        val body = data["body"]?.take(800) ?: return
        val uri = try { android.net.Uri.parse(data["url"] ?: home) }
                  catch (_: Exception) { android.net.Uri.parse(home) }
        val deepLink = if (uri.scheme == "https" && uri.host == validHost &&
            (uri.path == "/catalyst-radar" || uri.path?.startsWith("/catalyst-radar/") == true))
            uri.toString() else home

        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(
            NotificationChannel(
                channelId, getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply { description = getString(R.string.notification_channel_description) }
        )
        val intent = Intent(this, MainActivity::class.java)
            .putExtra("target_url", deepLink)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val uniqueId = data["alert_id"]?.hashCode() ?: System.currentTimeMillis().toInt()
        val action = PendingIntent.getActivity(
            this, uniqueId, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_radar)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(action)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        manager.notify(uniqueId, notification)
    }
}
