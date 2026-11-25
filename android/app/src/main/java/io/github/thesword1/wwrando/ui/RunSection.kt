package io.github.thesword1.wwrando.ui

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.service.RunStateValue

/**
 * Real-run section: seed box + New seed, SAF ISO picker with in-app MD5 verification, SAF
 * output-folder picker, and the Randomize/cancel controls. The picker launchers are owned by
 * HomeScreen so the Self-Check card can trigger the same actions.
 */
@Composable
fun RunSection(
    viewModel: RandoViewModel,
    seed: String,
    onSeedChanged: (String) -> Unit,
    onNewSeed: () -> Unit,
    onPickIso: () -> Unit,
    onPickOutput: () -> Unit,
) {
    val iso = viewModel.iso
    val outputFolder = viewModel.outputFolder
    val ready = viewModel.setupInstalled
    val runState by viewModel.runState.collectAsState()

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SeedCard(seed = seed, onSeedChanged = onSeedChanged, onNewSeed = onNewSeed)
        IsoCard(state = iso, onPick = onPickIso)
        OutputFolderCard(selected = outputFolder != null, onPick = onPickOutput)
        RealRunCard(
            state = runState,
            isoVerified = iso.status == IsoStatus.Verified,
            outputPicked = outputFolder != null,
            ready = ready,
            onRun = { viewModel.startRealRun(seed) },
            onCancel = viewModel::cancelRealRun,
        )
    }
}

@Composable
private fun SeedCard(seed: String, onSeedChanged: (String) -> Unit, onNewSeed: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Seed", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = seed,
                onValueChange = onSeedChanged,
                label = { Text("Seed name (blank = autoseed)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Button(onClick = onNewSeed) { Text("New seed") }
        }
    }
}

@Composable
private fun IsoCard(state: IsoUiState, onPick: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Clean ISO", style = MaterialTheme.typography.titleMedium)
            if (state.name == null) {
                Text("No ISO picked yet.")
            } else {
                Text("${state.name} (${formatBytes(state.size)})")
                when (state.status) {
                    IsoStatus.Verifying -> {
                        if (state.size > 0) {
                            LinearProgressIndicator(
                                progress = { state.progress.toFloat() / state.size },
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                        Text("Checking MD5...")
                    }
                    IsoStatus.Verified -> Text("Verified (correct clean ISO)", color = MaterialTheme.colorScheme.primary)
                    IsoStatus.Wrong -> Text("Wrong ISO", color = MaterialTheme.colorScheme.error)
                    IsoStatus.Unreadable -> Text("Unreadable", color = MaterialTheme.colorScheme.error)
                    IsoStatus.None -> Text("Not verified")
                }
            }
            Button(onClick = onPick, enabled = state.status != IsoStatus.Verifying) {
                Text(if (state.name == null) "Pick clean ISO" else "Change")
            }
        }
    }
}

@Composable
private fun OutputFolderCard(selected: Boolean, onPick: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Output folder", style = MaterialTheme.typography.titleMedium)
            Text(if (selected) "Selected (SAF tree)." else "No output folder picked yet.")
            Button(onClick = onPick) { Text(if (selected) "Change" else "Pick output folder") }
        }
    }
}

@Composable
private fun RealRunCard(
    state: RunStateValue,
    isoVerified: Boolean,
    outputPicked: Boolean,
    ready: Boolean,
    onRun: () -> Unit,
    onCancel: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Randomize", style = MaterialTheme.typography.titleMedium)

            val enabled = isoVerified && outputPicked && ready && state !is RunStateValue.Running
            Button(onClick = onRun, enabled = enabled) { Text("Randomize") }

            when (state) {
                is RunStateValue.Running -> {
                    if (state.max > 0) {
                        LinearProgressIndicator(
                            progress = { state.progress.toFloat() / state.max },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    Text(state.step.ifBlank { "Randomizing..." })
                    OutlinedButton(onClick = onCancel) { Text("Cancel") }
                }
                is RunStateValue.Done -> {
                    Text("Seed hash: ${state.seedHash}")
                    Text("Output: ${state.outputFolder}")
                }
                is RunStateValue.Failed -> Text(state.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                is RunStateValue.Cancelled -> Text("Cancelled", color = MaterialTheme.colorScheme.error)
                RunStateValue.Idle -> Unit
            }

            when {
                !ready -> Text("Setup is not ready yet.", style = MaterialTheme.typography.bodySmall)
                !isoVerified -> Text("Pick and verify a clean ISO first.", style = MaterialTheme.typography.bodySmall)
                !outputPicked -> Text("Pick an output folder first.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

internal fun queryIso(context: Context, uri: Uri): Triple<String, Long, Long> {
    var name = "clean.iso"
    var size = 0L
    var modified = 0L
    runCatching {
        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (nameIdx >= 0) name = cursor.getString(nameIdx) ?: name
                if (sizeIdx >= 0) size = cursor.getLong(sizeIdx)
                val modifiedIdx = cursor.getColumnIndex("last_modified")
                if (modifiedIdx >= 0) modified = cursor.getLong(modifiedIdx)
            }
        }
    }
    return Triple(name, size, modified)
}

private fun formatBytes(bytes: Long): String = when {
    bytes >= 1L shl 30 -> "%.2f GB".format(bytes / (1L shl 30).toDouble())
    bytes >= 1L shl 20 -> "%.1f MB".format(bytes / (1L shl 20).toDouble())
    else -> "$bytes B"
}
