package io.github.thesword1.wwrando.ui

import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.github.thesword1.wwrando.data.LogFile
import io.github.thesword1.wwrando.data.OutputsLogic
import io.github.thesword1.wwrando.data.SeedOutput
import io.github.thesword1.wwrando.service.RunStateValue

/**
 * Generated-seed list shown once an output tree is granted: refresh, Delete old, and per-seed
 * Play / Logs / Copy permalink / Delete. Kept out of HomeScreen and RandoViewModel for size.
 */
@Composable
fun OutputsSection(viewModel: RandoViewModel, outputsViewModel: OutputsViewModel) {
    val outputFolder = viewModel.outputFolder
    if (outputFolder == null) return
    val runState by viewModel.runState.collectAsState()

    // Re-list when the tree changes and as soon as a real run finishes.
    LaunchedEffect(outputFolder) { outputsViewModel.refresh() }
    LaunchedEffect(runState) {
        if (runState is RunStateValue.Done) outputsViewModel.refresh()
    }

    val context = LocalContext.current
    var pendingDelete by remember { mutableStateOf<SeedOutput?>(null) }
    var confirmDeleteOld by remember { mutableStateOf(false) }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "Generated seeds (${outputsViewModel.outputs.size})",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = outputsViewModel::refresh, enabled = !outputsViewModel.loading) { Text("Refresh") }
                TextButton(
                    onClick = { confirmDeleteOld = true },
                    enabled = outputsViewModel.outputs.size > 1,
                ) { Text("Delete old") }
            }
            if (outputsViewModel.loading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            outputsViewModel.notice?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            if (outputsViewModel.outputs.isEmpty() && !outputsViewModel.loading) {
                Text("No seeds yet.", style = MaterialTheme.typography.bodySmall)
            }
            outputsViewModel.outputs.forEach { output ->
                SeedOutputCard(
                    output = output,
                    onPlay = { outputsViewModel.play(context, output) },
                    onLogs = { outputsViewModel.openLogs(output) },
                    onShare = { outputsViewModel.share(context, output) },
                    onCopy = { outputsViewModel.copyShare(context, output) },
                    onDelete = { pendingDelete = output },
                )
            }
        }
    }

    outputsViewModel.logsDialog?.let { dialog ->
        LogsDialog(dialog.title, dialog.files, outputsViewModel::readLogText, outputsViewModel::dismissLogs)
    }

    pendingDelete?.let { output ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Delete seed?") },
            text = { Text("Delete ${output.title} and its ISO and logs?") },
            confirmButton = {
                TextButton(onClick = {
                    pendingDelete = null
                    outputsViewModel.delete(output)
                }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("Cancel") } },
        )
    }

    if (confirmDeleteOld) {
        AlertDialog(
            onDismissRequest = { confirmDeleteOld = false },
            title = { Text("Delete old seeds?") },
            text = { Text("Delete all but the newest seed?") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDeleteOld = false
                    outputsViewModel.deleteOld()
                }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { confirmDeleteOld = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun SeedOutputCard(
    output: SeedOutput,
    onPlay: () -> Unit,
    onLogs: () -> Unit,
    onShare: () -> Unit,
    onCopy: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(output.title, style = MaterialTheme.typography.titleSmall)
            Text(
                buildString {
                    append(output.meta?.seed?.takeIf { it.isNotBlank() } ?: output.folderName)
                    append("  ")
                    append(OutputsLogic.formatOutputDate(output.meta, output.modified))
                    if (output.isoSize > 0) {
                        append("  ")
                        append(OutputsLogic.formatIsoSizeMb(output.isoSize))
                    }
                },
                style = MaterialTheme.typography.bodySmall,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Button(onClick = onPlay, enabled = output.isoUri != null) { Text("Play") }
                Button(onClick = onLogs, enabled = output.logs.isNotEmpty()) { Text("Logs") }
                if (!output.meta?.permalink.isNullOrBlank()) {
                    Button(onClick = onShare) { Text("Share") }
                    Button(onClick = onCopy) { Text("Copy") }
                }
                TextButton(onClick = onDelete) { Text("Delete") }
            }
        }
    }
}

@Composable
private fun LogsDialog(
    title: String,
    files: List<LogFile>,
    readLogText: suspend (Uri) -> String,
    onDismiss: () -> Unit,
) {
    var selectedIndex by remember { mutableIntStateOf(0) }
    val selected = files.getOrNull(selectedIndex)

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Card(Modifier.fillMaxSize().padding(8.dp)) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                if (files.size > 1) {
                    TabRow(selectedTabIndex = selectedIndex.coerceAtMost(files.lastIndex)) {
                        files.forEachIndexed { index, file ->
                            Tab(
                                selected = selectedIndex == index,
                                onClick = { selectedIndex = index },
                                text = { Text(file.label, maxLines = 1) },
                            )
                        }
                    }
                }
                if (selected != null) {
                    val text by produceState(initialValue = "Loading...", selected.uri) {
                        value = readLogText(selected.uri)
                    }
                    SelectionContainer {
                        Text(
                            text,
                            fontFamily = FontFamily.Monospace,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f)
                                .verticalScroll(rememberScrollState()),
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                    TextButton(onClick = onDismiss) { Text("Close") }
                }
            }
        }
    }
}
