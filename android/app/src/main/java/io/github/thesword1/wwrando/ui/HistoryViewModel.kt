package io.github.thesword1.wwrando.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import io.github.thesword1.wwrando.data.HistoryEntry
import io.github.thesword1.wwrando.data.HistoryStore

/** Holds the run-history list for the history screen (read-only; entries are appended by the service). */
class HistoryViewModel(application: Application) : AndroidViewModel(application) {

    private val store = HistoryStore(application)

    var entries by mutableStateOf<List<HistoryEntry>>(emptyList())
        private set

    init {
        refresh()
    }

    fun refresh() {
        entries = store.list()
    }

    fun clear() {
        store.clear()
        refresh()
    }
}
