package io.github.thesword1.wwrando.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.thesword1.wwrando.data.ProgressEvent
import io.github.thesword1.wwrando.data.RandoSetup
import kotlinx.coroutines.launch
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

/** Holds the home-screen state and owns the setup/dry-run Termux jobs (MainActivity stays a thin host). */
class RandoViewModel(application: Application) : AndroidViewModel(application) {

    private val engine = RandoSetup(application, viewModelScope)

    var setup by mutableStateOf(SetupUiState())
        private set
    var dryRun by mutableStateOf(DryRunUiState())
        private set

    val setupInstalled: Boolean get() = engine.isSetupCurrent()

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
