package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.HistoryEntry
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Full-screen run history: newest first, with Clear history. */
@Composable
fun HistoryScreen(viewModel: HistoryViewModel, onBack: () -> Unit) {
    var confirmClear by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Run history", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            TextButton(onClick = onBack) { Text("Back") }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${viewModel.entries.size} run${if (viewModel.entries.size == 1) "" else "s"}",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.weight(1f),
            )
            TextButton(onClick = { confirmClear = true }, enabled = viewModel.entries.isNotEmpty()) {
                Text("Clear history")
            }
        }

        if (viewModel.entries.isEmpty()) {
            Text("No runs yet.", style = MaterialTheme.typography.bodySmall)
        }

        viewModel.entries.forEach { entry ->
            HistoryCard(entry = entry)
        }
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text("Clear history?") },
            text = { Text("Delete all recorded runs?") },
            confirmButton = {
                TextButton(onClick = {
                    confirmClear = false
                    viewModel.clear()
                }) { Text("Clear") }
            },
            dismissButton = { TextButton(onClick = { confirmClear = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun HistoryCard(entry: HistoryEntry) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                if (entry.ok) {
                    entry.seedHash.ifBlank { entry.seed.ifBlank { "Successful run" } }
                } else {
                    "Failed run"
                },
                style = MaterialTheme.typography.titleSmall,
                color = if (entry.ok) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error,
            )
            Text(
                buildString {
                    append(formatTime(entry.time))
                    if (!entry.ok && entry.error.isNotBlank()) {
                        append("  ")
                        append(entry.error.lineSequence().firstOrNull().orEmpty())
                    }
                    if (entry.preset.isNotBlank() && entry.ok) {
                        append("  ")
                        append(entry.preset)
                        if (entry.modified) append(" (modified)")
                    }
                },
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

private val HISTORY_DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")

private fun formatTime(epochMillis: Long): String =
    Instant.ofEpochMilli(epochMillis).atZone(ZoneId.systemDefault()).toLocalDateTime()
        .format(HISTORY_DATE_FORMAT)
