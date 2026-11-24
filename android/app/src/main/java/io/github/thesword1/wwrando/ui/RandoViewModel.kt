package io.github.thesword1.wwrando.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.thesword1.wwrando.data.IsoVerify
import io.github.thesword1.wwrando.data.ProgressEvent
import io.github.thesword1.wwrando.data.RandoPrefs
import io.github.thesword1.wwrando.data.RandoSetup
import io.github.thesword1.wwrando.service.RandoRunService
import io.github.thesword1.wwrando.service.RunState
import io.github.thesword1.wwrando.service.RunStateValue
import java.security.MessageDigest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext
import org.json.JSONObject

data class SetupUiState(
    val running: Boolean = false,
    val stepIndex: Int = 0,
    val stepTotal: Int = 0,
    val stepLabel: String = "",
    val log: List<String> = emptyList(),
    val error: String? = null,
    val finished: Boolean = false,
)

data class DryRunUiState(
    val running: Boolean = false,
    val done: Int = 0,
    val max: Int = 0,
    val description: String = "",
    val result: String? = null,
    val error: String? = null,
)

enum class IsoStatus { None, Verifying, Verified, Wrong, Unreadable }

data class IsoUiState(
    val name: String? = null,
    val size: Long = 0,
    val status: IsoStatus = IsoStatus.None,
    val progress: Long = 0,
)

/** Holds the home-screen state and owns the setup/dry-run Termux jobs; the real run is a service. */
class RandoViewModel(application: Application) : AndroidViewModel(application) {

    private val engine = RandoSetup(application, viewModelScope)
    private val prefs = RandoPrefs(application)
    private var verifyJob: Job? = null

    var setup by mutableStateOf(SetupUiState())
        private set
    var dryRun by mutableStateOf(DryRunUiState())
        private set
    var iso by mutableStateOf(IsoUiState())
        private set
    var outputFolder: Uri? by mutableStateOf(null)
        private set

    val runState: StateFlow<RunStateValue> get() = RunState.state
    val setupInstalled: Boolean get() = engine.isSetupCurrent()

    init {
        prefs.loadIso()?.let { pick ->
            iso = IsoUiState(pick.name, pick.size, if (pick.verified) IsoStatus.Verified else IsoStatus.None, 0)
        }
        outputFolder = prefs.loadOutputTree()
    }

    fun runSetup() {
        if (setup.running) return
        viewModelScope.launch {
            setup = SetupUiState(running = true)
            val done = engine.runSetup { event -> onSetupEvent(event) }
            if (!setup.running) return@launch // cancelled
            if (done.ok) engine.saveInstalledHash(engine.bundledHash())
            setup = setup.copy(running = false, finished = true, error = if (done.ok) null else done.body)
        }
    }

    fun runDryRun(seed: String) {
        if (dryRun.running) return
        viewModelScope.launch {
            dryRun = DryRunUiState(running = true)
            val done = engine.runDryRun(seed.ifBlank { null }) { event -> onRunEvent(event) }
            if (!dryRun.running) return@launch // cancelled
            dryRun = dryRun.copy(
                running = false,
                result = if (done.ok) formatResult(done.body) else null,
                error = if (done.ok) null else done.body,
            )
        }
    }

    fun cancel() {
        if (setup.running) setup = setup.copy(running = false, error = "Cancelled")
        if (dryRun.running) dryRun = dryRun.copy(running = false)
        viewModelScope.launch { engine.cancel() }
    }

    /** Stores a newly picked ISO and starts its MD5 pre-verification in the app (cancellable). */
    fun onIsoPicked(uri: Uri, name: String, size: Long, lastModified: Long) {
        verifyJob?.cancel()
        prefs.saveIso(uri, name, size, lastModified)
        iso = IsoUiState(name, size, IsoStatus.Verifying, 0)
        verifyJob = viewModelScope.launch(Dispatchers.IO) {
            val md5 = computeMd5(uri) { read ->
                iso = iso.copy(progress = read)
            }
            when {
                md5 == null -> iso = iso.copy(status = IsoStatus.Unreadable)
                md5 == IsoVerify.CLEAN_ISO_MD5 -> {
                    prefs.markIsoVerified(uri, size, lastModified)
                    iso = iso.copy(status = IsoStatus.Verified)
                }
                else -> iso = iso.copy(status = IsoStatus.Wrong)
            }
        }
    }

    fun onOutputFolderPicked(uri: Uri) {
        prefs.saveOutputTree(uri)
        outputFolder = uri
    }

    fun startRealRun(seed: String, tracker: Boolean) {
        // Clear the previous run's result/error immediately so it never lingers on screen.
        RunState.set(RunStateValue.Running(0, 0, "Starting"))
        val intent = Intent(getApplication(), RandoRunService::class.java)
            .putExtra(RandoRunService.EXTRA_SEED, seed.ifBlank { "" })
            .putExtra(RandoRunService.EXTRA_TRACKER, tracker)
        getApplication<Application>().startForegroundService(intent)
    }

    fun cancelRealRun() {
        getApplication<Application>().startService(
            Intent(getApplication(), RandoRunService::class.java).setAction(RandoRunService.ACTION_CANCEL),
        )
    }

    private suspend fun computeMd5(uri: Uri, onProgress: (Long) -> Unit): String? =
        withContext(Dispatchers.IO) {
            val resolver = getApplication<Application>().contentResolver
            val stream = resolver.openInputStream(uri) ?: return@withContext null
            try {
                val digest = MessageDigest.getInstance("MD5")
                val buffer = ByteArray(1 shl 20)
                var read = 0L
                stream.use { input ->
                    while (true) {
                        coroutineContext.ensureActive()
                        val n = input.read(buffer)
                        if (n == -1) break
                        digest.update(buffer, 0, n)
                        read += n
                        onProgress(read)
                    }
                }
                digest.digest().joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                null
            }
        }

    private fun onSetupEvent(event: ProgressEvent) {
        if (!setup.running) return
        setup = when (event) {
            is ProgressEvent.Step -> setup.copy(
                stepIndex = event.index,
                stepTotal = event.total,
                stepLabel = event.label,
                log = appendLog(setup.log, "Step ${event.index}/${event.total} ${event.label}"),
            )
            is ProgressEvent.Info -> setup.copy(log = appendLog(setup.log, event.text))
            is ProgressEvent.Progress -> setup.copy(
                stepLabel = event.description,
                log = appendLog(setup.log, event.description),
            )
            is ProgressEvent.Done -> setup
        }
    }

    private fun onRunEvent(event: ProgressEvent) {
        if (!dryRun.running) return
        dryRun = when (event) {
            is ProgressEvent.Progress -> dryRun.copy(done = event.done, max = event.max, description = event.description)
            is ProgressEvent.Step -> dryRun.copy(description = event.label)
            is ProgressEvent.Info -> dryRun
            is ProgressEvent.Done -> dryRun
        }
    }

    private fun appendLog(log: List<String>, line: String): List<String> =
        (log + line).takeLast(12)

    private fun formatResult(body: String): String = runCatching {
        val json = JSONObject(body)
        buildString {
            append("Seed: ").append(json.optString("seed", "?"))
            append("\nHash: ").append(json.optString("seed_hash", "?"))
            val permalink = json.optString("permalink", "")
            if (permalink.isNotBlank()) append("\nPermalink: ").append(permalink)
        }
    }.getOrElse { body }
}
