package com.mirkottino83.catalystradar

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import org.json.JSONObject

class MainActivity : Activity() {
    companion object {
        private const val HOME = "https://mirkottino83-eng.github.io/catalyst-radar/"
        private const val HOST = "mirkottino83-eng.github.io"
        private const val ASK_NOTIFICATIONS = 900
        private const val TOPIC_NEWS = "catalyst-alerts"
        private const val TOPIC_MACRO = "tech-macro"
        private const val PREFS = "catalyst_radar_push"
        private const val KEY_ENABLED = "enabled"
    }
    private lateinit var browser: WebView
    private var pendingEnable = false
    private var busy = false

    private fun prefs() = getSharedPreferences(PREFS, MODE_PRIVATE)
    private fun enabled() = prefs().getBoolean(KEY_ENABLED, false)
    private fun configured() = FirebaseApp.getApps(this).isNotEmpty()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        browser = WebView(this)
        browser.settings.javaScriptEnabled = true
        browser.settings.domStorageEnabled = true
        browser.settings.allowFileAccess = false
        browser.settings.allowContentAccess = false
        browser.settings.javaScriptCanOpenWindowsAutomatically = false
        browser.settings.setSupportMultipleWindows(false)
        browser.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
        browser.webChromeClient = WebChromeClient()
        browser.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                if (!request.isForMainFrame) return false
                val uri = request.url
                if (uri.scheme == "https" && uri.host == HOST &&
                    (uri.path == "/catalyst-radar" || uri.path?.startsWith("/catalyst-radar/") == true)) {
                    return false
                }
                // External sites are not permitted in the JS-enabled native WebView.
                if (uri.scheme == "https" || uri.scheme == "http") {
                    try { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                    catch (_: ActivityNotFoundException) { }
                }
                return true
            }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                super.onReceivedError(view, request, error)
                if (!request.isForMainFrame) return
                if (request.url.scheme != "https" || request.url.host != HOST) return
                // Main document only: a failing third-party chart must not hide the dashboard.
                val offline = """
                    <!doctype html><html lang="it"><head><meta name="viewport"
                    content="width=device-width, initial-scale=1"></head>
                    <body style="background:#070b14;color:#e8f0f9;font:16px system-ui;
                    text-align:center;padding:48px 20px">
                    <h1>Catalyst Radar</h1>
                    <p>Connessione non disponibile. I dati non sono aggiornati.</p>
                    <p>Il monitoraggio sui server continua indipendentemente dal telefono.</p>
                    <p><a href="$HOME" style="color:#63dbec">Riprova a collegarti</a></p>
                    </body></html>
                """.trimIndent()
                view.loadDataWithBaseURL(null, offline, "text/html", "UTF-8", null)
            }
            override fun onPageFinished(view: WebView, url: String?) {
                super.onPageFinished(view, url)
                if (url?.startsWith(HOME) == true) sendStatus("ready")
            }
        }

        // Unlike addJavascriptInterface, this listener is restricted to the
        // single trusted origin and the main frame, not TradingView iframes.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(
                browser, "CatalystRadarNative", setOf("https://$HOST")
            ) { _, message, origin, isMainFrame, _ ->
                if (!isMainFrame || origin.scheme != "https" || origin.host != HOST) return@addWebMessageListener
                val json = try { JSONObject(message.data ?: "{}") } catch (_: Exception) { return@addWebMessageListener }
                runOnUiThread {
                    when (json.optString("type")) {
                        "getState" -> sendStatus("ready")
                        "setNotifications" -> if (json.has("enabled")) setNotifications(json.optBoolean("enabled"))
                    }
                }
            }
        }
        setContentView(browser)
        val initial = intent?.getStringExtra("target_url")?.let(::safeUrl) ?: HOME
        browser.loadUrl(initial)
        if (configured() && enabled()) ensureSubscriptions()
    }

    private fun safeUrl(candidate: String): String {
        val parsed = try { Uri.parse(candidate) } catch (_: Exception) { return HOME }
        return if (parsed.scheme == "https" && parsed.host == HOST &&
            (parsed.path == "/catalyst-radar" || parsed.path?.startsWith("/catalyst-radar/") == true))
            candidate else HOME
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        browser.loadUrl(intent.getStringExtra("target_url")?.let(::safeUrl) ?: HOME)
    }

    private fun sendStatus(status: String, error: String? = null) {
        val json = JSONObject()
            .put("enabled", enabled())
            .put("available", configured())
            .put("status", status)
            .put("busy", busy)
            .put("error", error ?: JSONObject.NULL)
        browser.evaluateJavascript(
            "window.dispatchEvent(new CustomEvent('CatalystRadarNativeState',{detail:$json}));",
            null
        )
    }

    private fun setNotifications(turnOn: Boolean) {
        if (busy) return
        if (!configured()) {
            sendStatus("unavailable", "Firebase non configurato: completa la configurazione Android.")
            return
        }
        if (!turnOn) {
            // Locally suppress all remote messages before async unsubscription.
            prefs().edit().putBoolean(KEY_ENABLED, false).apply()
            busy = true
            sendStatus("updating")
            unsubscribeAll()
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            pendingEnable = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), ASK_NOTIFICATIONS)
            return
        }
        busy = true
        sendStatus("updating")
        subscribeAll()
    }

    private fun subscribeAll() {
        FirebaseMessaging.getInstance().subscribeToTopic(TOPIC_NEWS).addOnCompleteListener { news ->
            if (!news.isSuccessful) {
                busy = false
                sendStatus("error", "Impossibile attivare gli avvisi, controlla la connessione.")
                return@addOnCompleteListener
            }
            FirebaseMessaging.getInstance().subscribeToTopic(TOPIC_MACRO).addOnCompleteListener { macro ->
                if (macro.isSuccessful) {
                    prefs().edit().putBoolean(KEY_ENABLED, true).apply()
                    busy = false
                    sendStatus("enabled")
                } else {
                    FirebaseMessaging.getInstance().unsubscribeFromTopic(TOPIC_NEWS)
                    busy = false
                    sendStatus("error", "Attivazione incompleta. Riprova.")
                }
            }
        }
    }

    private fun unsubscribeAll() {
        FirebaseMessaging.getInstance().unsubscribeFromTopic(TOPIC_NEWS).addOnCompleteListener { news ->
            FirebaseMessaging.getInstance().unsubscribeFromTopic(TOPIC_MACRO).addOnCompleteListener { macro ->
                busy = false
                if (news.isSuccessful && macro.isSuccessful) sendStatus("disabled")
                else sendStatus("disabled", "Avvisi bloccati su questo dispositivo; rimozione canali da ritentare.")
            }
        }
    }

    private fun ensureSubscriptions() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            prefs().edit().putBoolean(KEY_ENABLED, false).apply()
            return
        }
        FirebaseMessaging.getInstance().subscribeToTopic(TOPIC_NEWS).addOnCompleteListener {
            if (it.isSuccessful) FirebaseMessaging.getInstance().subscribeToTopic(TOPIC_MACRO)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != ASK_NOTIFICATIONS || !pendingEnable) return
        pendingEnable = false
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            busy = true
            sendStatus("updating")
            subscribeAll()
        } else sendStatus("permission_denied", "Autorizza le notifiche nelle impostazioni Android.")
    }

    @Deprecated("Back handling for classic Activity")
    override fun onBackPressed() {
        if (::browser.isInitialized && browser.canGoBack()) browser.goBack()
        else super.onBackPressed()
    }
}
