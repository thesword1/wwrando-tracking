package io.github.thesword1.wwrando.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.thesword1.wwrando.data.DolphinLauncher
import io.github.thesword1.wwrando.data.LogFile
import io.github.thesword1.wwrando.data.OutputsRepo
import io.github.thesword1.wwrando.data.RandoPrefs
import io.github.thesword1.wwrando.data.SeedOutput
import kotlinx.coroutines.launch

data class LogsDialogState(val title: String, val files: List<LogFile>)

/** Holds the generated-seed list state (pure SAF, no DB) for the outputs section. */
class OutputsViewModel(application: Application) : AndroidViewModel(application) {

    private val repo = OutputsRepo(application.contentResolver)
    private val prefs = RandoPrefs(application)

    var outputs by mutableStateOf<List<SeedOutput>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var notice by mutableStateOf<String?>(null)
        private set
    var logsDialog by mutableStateOf<LogsDialogState?>(null)
        private set

    init {
        refresh()
    }

    fun refresh() {
        val tree = prefs.loadOutputTree() ?: return
        if (loading) return
        loading = true
        viewModelScope.launch {
            repo.list(tree)
                .onSuccess { outputs = it }
                .onFailure {
                    outputs = emptyList()
                    notice = "Cannot list outputs: ${it.message}"
                }
            loading = false
        }
    }

    fun play(context: Context, output: SeedOutput) {
        val uri = output.isoUri
        if (uri == null) {
            notice = "No ISO in this folder."
            return
        }
        notice = DolphinLauncher.launch(context, uri)
    }

    fun share(context: Context, output: SeedOutput) {
        val permalink = output.meta?.permalink?.takeIf { it.isNotBlank() } ?: return
        sharePermalink(context, permalink, output.meta?.seedHash.orEmpty())
    }

    fun copyShare(context: Context, output: SeedOutput) {
        val permalink = output.meta?.permalink?.takeIf { it.isNotBlank() } ?: return
        copyPermalinkShare(context, permalink, output.meta?.seedHash.orEmpty())
        notice = "Copied."
    }

    fun delete(output: SeedOutput) {
        viewModelScope.launch {
            repo.delete(output.folderUri)
                .onSuccess { refresh() }
                .onFailure { notice = "Delete failed: ${it.message}" }
        }
    }

    fun deleteOld() {
        val tree = prefs.loadOutputTree() ?: return
        viewModelScope.launch {
            repo.deleteOlderThanNewest(tree)
                .onSuccess { deleted ->
                    notice = if (deleted == 0) "No old seeds to delete." else "Deleted $deleted old seed(s)."
                    refresh()
                }
                .onFailure { notice = "Delete failed: ${it.message}" }
        }
    }

    fun openLogs(output: SeedOutput) {
        logsDialog = LogsDialogState(output.title, output.logs)
    }

    fun dismissLogs() {
        logsDialog = null
    }

    suspend fun readLogText(uri: Uri): String =
        repo.readText(uri).getOrElse { "Could not read log: ${it.message}" }
}
