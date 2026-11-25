package io.github.thesword1.wwrando.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.provider.DocumentsContract
import androidx.core.app.NotificationCompat
import io.github.thesword1.wwrando.MainActivity
import io.github.thesword1.wwrando.data.IsoSource
import io.github.thesword1.wwrando.data.IsoVerify
import io.github.thesword1.wwrando.data.LoopbackBridge
import io.github.thesword1.wwrando.data.OutputsLogic
import io.github.thesword1.wwrando.data.ProgressEvent
import io.github.thesword1.wwrando.data.RandoCommandRunner
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.data.RandoPrefs
import io.github.thesword1.wwrando.data.RunOutputSink
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

/** Process-wide run state observed by the ViewModel (no service binding). */
sealed interface RunStateValue {
    data object Idle : RunStateValue
    data class Running(val progress: Int, val max: Int, val step: String) : RunStateValue
    data class Done(
        val seed: String,
        val seedHash: String,
        val permalink: String,
        val outputFolder: String,
    ) : RunStateValue
    data class Failed(val error: String) : RunStateValue
    data object Cancelled : RunStateValue
}

object RunState {
    private val _state = MutableStateFlow<RunStateValue>(RunStateValue.Idle)
    val state: StateFlow<RunStateValue> = _state.asStateFlow()
    fun set(value: RunStateValue) {
        _state.value = value
    }
}

/** SAF-backed ISO source: streams the picked content:// URI to the bridge. */
class AndroidIsoSource(
    private val resolver: android.content.ContentResolver,
    private val uri: Uri,
    override val size: Long,
) : IsoSource {
    override fun openStream(): InputStream =
        resolver.openInputStream(uri) ?: throw IOException("cannot open ISO stream")
}

/** SAF-backed output sink: creates one subfolder per run and a document per uploaded file. */
class AndroidRunOutputSink(
    private val resolver: android.content.ContentResolver,
    private val treeUri: Uri,
) : RunOutputSink {
    private var folderUri: Uri? = null
    private var folderName: String? = null
    private var currentUri: Uri? = null

    override fun open(subfolder: String, name: String): OutputStream {
        val folder = ensureFolder(subfolder)
        val docUri = DocumentsContract.createDocument(resolver, folder, "application/octet-stream", name)
            ?: throw IOException("cannot create output document")
        val stream = resolver.openOutputStream(docUri, "w")
            ?: run {
                runCatching { DocumentsContract.deleteDocument(resolver, docUri) }
                throw IOException("cannot open output document")
            }
        currentUri = docUri
        return stream
    }

    override fun delete(subfolder: String, name: String) {
        currentUri?.let { runCatching { DocumentsContract.deleteDocument(resolver, it) } }
        currentUri = null
    }

    override fun abort() {
        currentUri?.let { runCatching { DocumentsContract.deleteDocument(resolver, it) } }
        currentUri = null
        // A cancelled run leaves nothing behind: drop this run's subfolder and any files already in it.
        folderUri?.let { runCatching { DocumentsContract.deleteDocument(resolver, it) } }
        folderUri = null
        folderName = null
    }

    override fun close() = Unit

    override fun writeMeta(json: String) {
        val folder = folderUri ?: return
        val docUri = DocumentsContract.createDocument(
            resolver, folder, "application/octet-stream", OutputsLogic.META_FILE_NAME,
        ) ?: return
        val stream = resolver.openOutputStream(docUri, "w") ?: run {
            runCatching { DocumentsContract.deleteDocument(resolver, docUri) }
            return
        }
        runCatching {
            stream.use { it.write(json.toByteArray(Charsets.UTF_8)) }
        }.onFailure {
            runCatching { DocumentsContract.deleteDocument(resolver, docUri) }
        }
    }

    private fun ensureFolder(subfolder: String): Uri {
        folderUri?.let { if (folderName == subfolder) return it }
        // createDocument needs a document URI; a bare tree URI fails with "Invalid URI".
        val root = DocumentsContract.buildDocumentUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri))
        val created = DocumentsContract.createDocument(
            resolver, root, DocumentsContract.Document.MIME_TYPE_DIR, subfolder,
        ) ?: throw IOException("cannot create output subfolder")
        folderUri = created
        folderName = subfolder
        return created
    }
}

/**
 * Foreground service (dataSync) that owns the loopback bridge and the Termux run.sh job for a real
 * run, so the run survives the activity going to background. Dry runs stay in the ViewModel.
 */
class RandoRunService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    @Volatile
    private var bridge: LoopbackBridge? = null

    @Volatile
    private var sink: RunOutputSink? = null

    @Volatile
    private var cancelled = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_CANCEL) {
            cancelRun()
            return START_NOT_STICKY
        }
        val seed = intent?.getStringExtra(EXTRA_SEED) ?: ""
        val tracker = intent?.getBooleanExtra(EXTRA_TRACKER, true) ?: true
        ensureChannel()
        startForegroundCompat(buildNotification("Starting...", 0, 0))
        RunState.set(RunStateValue.Running(0, 0, "Starting"))
        scope.launch { runReal(seed, tracker) }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        closeBridge()
        super.onDestroy()
    }

    private suspend fun runReal(seed: String, tracker: Boolean) {
        val prefs = RandoPrefs(this)
        val iso = prefs.loadIso()
        val outTree = prefs.loadOutputTree()
        if (iso == null || outTree == null) {
            failRun("Pick a clean ISO and an output folder first.")
            return
        }
        if (!iso.verified) {
            failRun("ISO is not verified.")
            return
        }
        val installed = getSharedPreferences("rando", MODE_PRIVATE).getString("installed_sha256", null)
        val bundled = readAssetText("wwrando.sha256").trim()
        if (installed != bundled) {
            failRun("Run setup first.")
            return
        }

        val treeBytes = readAssetBytes("wwrando.tgz")
        val localSink = AndroidRunOutputSink(contentResolver, outTree)
        val localBridge = LoopbackBridge(
            treeBytes,
            isoSource = AndroidIsoSource(contentResolver, iso.uri, iso.size),
            outputSink = localSink,
        )
        bridge = localBridge
        sink = localSink
        localBridge.start()

        val done = CompletableDeferred<ProgressEvent.Done>()
        val collector = scope.launch {
            localBridge.events.collect { event ->
                when (event) {
                    is ProgressEvent.Done -> done.complete(event)
                    is ProgressEvent.Progress -> onProgress(event.done, event.max, event.description)
                    is ProgressEvent.Step -> onStep(event.label)
                    is ProgressEvent.Info -> Unit
                }
            }
        }
        try {
            val script = readAssetText("run.sh")
            val command = "cat > '${RandoBridge.WWRANDO_DIR}/run.sh' && " +
                "chmod +x '${RandoBridge.WWRANDO_DIR}/run.sh' && " +
                "'${RandoBridge.WWRANDO_DIR}/run.sh' ${localBridge.port} ${localBridge.token} " +
                "${iso.size} ${IsoVerify.CLEAN_ISO_MD5} ${shellQuote(seed)} ${if (tracker) "1" else "0"}"
            val result = RandoCommandRunner.run(
                context = this,
                path = RandoBridge.SHELL,
                arguments = arrayOf("-c", command),
                stdin = script,
                workdir = RandoBridge.TERMUX_HOME,
                timeoutMs = RUN_TIMEOUT_MS,
            )
            val doneEvent = withTimeoutOrNull(DONE_TIMEOUT_MS) { done.await() }
            val final = when {
                doneEvent != null -> doneEvent
                result == null -> ProgressEvent.Done(false, """{"ok":false,"error":"run timed out"}""")
                !result.ok -> ProgressEvent.Done(
                    false,
                    """{"ok":false,"error":"exit ${result.exitCode}: ${result.stderr.takeLast(300)}"}""",
                )
                else -> ProgressEvent.Done(false, """{"ok":false,"error":"no final status from run"}""")
            }
            finishRun(final, tracker)
        } finally {
            collector.cancel()
            closeBridge()
            sink = null
        }
    }

    private fun finishRun(done: ProgressEvent.Done, tracker: Boolean) {
        if (cancelled) {
            RunState.set(RunStateValue.Cancelled)
            stopSelf()
            return
        }
        val json = runCatching { JSONObject(done.body) }.getOrNull()
        if (done.ok && json != null) {
            val seed = json.optString("seed", "")
            val seedHash = json.optString("seed_hash", "")
            val permalink = json.optString("permalink", "")
            val outputFolder = json.optString("output_folder", "")
            writeRunMeta(seed, seedHash, permalink, tracker)
            RunState.set(RunStateValue.Done(seed, seedHash, permalink, outputFolder))
            notify("Done: $seedHash")
        } else {
            val error = json?.optString("error")?.takeIf { it.isNotBlank() } ?: done.body
            RunState.set(RunStateValue.Failed(error))
            notify("Randomizer failed")
        }
        stopSelf()
    }

    /** Persists run metadata into the output subfolder; a failure is logged, never fails the run. */
    private fun writeRunMeta(seed: String, seedHash: String, permalink: String, tracker: Boolean) {
        val currentSink = sink ?: return
        val appCommit = runCatching { readAssetText("build_commit.txt").trim() }.getOrDefault("")
        val meta = JSONObject()
            .put("seed", seed)
            .put("seed_hash", seedHash)
            .put("permalink", permalink)
            .put("tracker", tracker)
            .put("created", OutputsLogic.nowLocalIso())
            .put("app_commit", appCommit)
        runCatching { currentSink.writeMeta(meta.toString()) }
    }

    private fun onProgress(done: Int, max: Int, description: String) {
        if (cancelled) return
        RunState.set(RunStateValue.Running(done, max, description))
        getSystemService(NotificationManager::class.java)
            ?.notify(NOTIF_ID, buildNotification(description, done, max))
    }

    private fun onStep(label: String) {
        if (cancelled) return
        RunState.set(RunStateValue.Running(currentProgress(), currentMax(), label))
        getSystemService(NotificationManager::class.java)
            ?.notify(NOTIF_ID, buildNotification(label, currentProgress(), currentMax()))
    }

    private fun currentProgress(): Int = (RunState.state.value as? RunStateValue.Running)?.progress ?: 0
    private fun currentMax(): Int = (RunState.state.value as? RunStateValue.Running)?.max ?: 0

    private fun failRun(error: String) {
        RunState.set(RunStateValue.Failed(error))
        notify("Randomizer failed")
        stopSelf()
    }

    private fun cancelRun() {
        cancelled = true
        RunState.set(RunStateValue.Cancelled)
        scope.launch {
            RandoCommandRunner.run(
                context = this@RandoRunService,
                path = RandoBridge.SHELL,
                arguments = arrayOf(
                    "-c",
                    "pkill -f run.sh; pkill -f android_run.py; pkill -f 'curl.*127.0.0.1' || true",
                ),
                workdir = RandoBridge.TERMUX_HOME,
                timeoutMs = CANCEL_TIMEOUT_MS,
            )
        }
        sink?.abort()
        closeBridge()
        stopSelf()
    }

    private fun closeBridge() {
        bridge?.close()
        bridge = null
    }

    private fun notify(text: String) {
        getSystemService(NotificationManager::class.java)?.notify(NOTIF_ID, buildNotification(text, 0, 0))
    }

    private fun buildNotification(text: String, progress: Int, max: Int): Notification {
        val cancelIntent = PendingIntent.getService(
            this, 1,
            Intent(this, RandoRunService::class.java).setAction(ACTION_CANCEL),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val contentIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Randomizer run")
            .setContentText(text)
            .setContentIntent(contentIntent)
            .addAction(0, "Cancel", cancelIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
        if (max > 0) {
            builder.setProgress(max, progress, false)
        } else {
            builder.setProgress(0, 0, true)
        }
        return builder.build()
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun startForegroundCompat(notification: Notification) {
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIF_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, notification)
        }
    }

    private fun readAssetText(path: String): String =
        assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }

    private fun readAssetBytes(path: String): ByteArray =
        assets.open(path).use { it.readBytes() }

    companion object {
        const val ACTION_CANCEL = "io.github.thesword1.wwrando.action.CANCEL_RUN"
        const val EXTRA_SEED = "seed"
        const val EXTRA_TRACKER = "tracker"

        private const val CHANNEL_ID = "randomizer_run"
        private const val CHANNEL_NAME = "Randomizer run"
        private const val NOTIF_ID = 41
        private const val RUN_TIMEOUT_MS = 45 * 60_000L
        private const val DONE_TIMEOUT_MS = 30_000L
        private const val CANCEL_TIMEOUT_MS = 15_000L

        fun shellQuote(value: String): String = "'" + value.replace("'", "'\\''") + "'"
    }
}
