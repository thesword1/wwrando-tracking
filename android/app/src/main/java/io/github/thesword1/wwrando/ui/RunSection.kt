package io.github.thesword1.wwrando.ui

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.service.RunStateValue

/** ISO and output folder as two compact side-by-side fields. */
@Composable
fun IsoOutputRow(
    iso: IsoUiState,
    outputSelected: Boolean,
    onPickIso: () -> Unit,
    onPickOutput: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        CompactIsoCard(state = iso, onPick = onPickIso, modifier = Modifier.weight(1f))
        CompactOutputCard(selected = outputSelected, onPick = onPickOutput, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun CompactIsoCard(state: IsoUiState, onPick: () -> Unit, modifier: Modifier = Modifier) {
    Card(modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Clean ISO", style = MaterialTheme.typography.titleSmall)
            Text(
                when (state.status) {
                    IsoStatus.Verifying -> "Checking MD5..."
                    IsoStatus.Verified -> "Verified"
                    IsoStatus.Wrong -> "Wrong ISO"
                    IsoStatus.Unreadable -> "Unreadable"
                    IsoStatus.None -> state.name ?: "Not picked"
                },
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (state.status == IsoStatus.Verifying && state.size > 0) {
                LinearProgressIndicator(
                    progress = { state.progress.toFloat() / state.size },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            TextButton(onClick = onPick, enabled = state.status != IsoStatus.Verifying) {
                Text(if (state.name == null) "Pick ISO" else "Change")
            }
        }
    }
}

@Composable
private fun CompactOutputCard(selected: Boolean, onPick: () -> Unit, modifier: Modifier = Modifier) {
    Card(modifier.fillMaxWidth()) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Output folder", style = MaterialTheme.typography.titleSmall)
            Text(if (selected) "Selected" else "Not picked", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onPick) { Text(if (selected) "Change" else "Pick") }
        }
    }
}

@Composable
fun SeedCard(seed: String, onSeedChanged: (String) -> Unit, onNewSeed: () -> Unit) {
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

/** The main action: a large, centered, primary Randomize button. */
@Composable
fun RandomizeCard(
    state: RunStateValue,
    isoVerified: Boolean,
    outputPicked: Boolean,
    ready: Boolean,
    onRun: () -> Unit,
    onCancel: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.fillMaxWidth().padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            val enabled = isoVerified && outputPicked && ready && state !is RunStateValue.Running
            Button(
                onClick = onRun,
                enabled = enabled,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                Text("Randomize", style = MaterialTheme.typography.titleLarge)
            }

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
