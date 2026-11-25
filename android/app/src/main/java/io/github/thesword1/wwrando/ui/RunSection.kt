package io.github.thesword1.wwrando.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.service.RunStateValue

/**
 * Real-run section: SAF ISO picker with in-app MD5 verification, SAF output-folder picker, and the
 * seed/tracker/cancel controls that drive the foreground service. Kept separate from HomeScreen.
 */
@Composable
fun RunSection(viewModel: RandoViewModel) {
    val iso = viewModel.iso
    val outputFolder = viewModel.outputFolder
    val runState by viewModel.runState.collectAsState()
    var seed by remember { mutableStateOf("") }
    var tracker by remember { mutableStateOf(true) }
    val context = LocalContext.current

    val isoPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            runCatching { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            val (name, size, modified) = queryIso(context, uri)
            viewModel.onIsoPicked(uri, name, size, modified)
        }
    }
    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    // Only READ/WRITE are valid here; adding FLAG_GRANT_PERSISTABLE_URI_PERMISSION throws
                    // IllegalArgumentException and the grant silently dies with the process.
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                )
            }
            viewModel.onOutputFolderPicked(uri)
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        IsoCard(state = iso, onPick = { isoPicker.launch(arrayOf("*/*")) })
        OutputFolderCard(selected = outputFolder != null, onPick = { folderPicker.launch(null) })
        RealRunCard(
            state = runState,
            isoVerified = iso.status == IsoStatus.Verified,
            outputPicked = outputFolder != null,
            seed = seed,
            onSeedChange = { seed = it },
            tracker = tracker,
            onTrackerChange = { tracker = it },
            onRun = { viewModel.startRealRun(seed, tracker) },
            onCancel = viewModel::cancelRealRun,
        )
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
    seed: String,
    onSeedChange: (String) -> Unit,
    tracker: Boolean,
    onTrackerChange: (Boolean) -> Unit,
    onRun: () -> Unit,
    onCancel: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Randomize", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = seed,
                onValueChange = onSeedChange,
                label = { Text("Seed (blank = autoseed)") },
                singleLine = true,
                enabled = state !is RunStateValue.Running,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Tracker", modifier = Modifier.weight(1f))
                Switch(checked = tracker, onCheckedChange = onTrackerChange, enabled = state !is RunStateValue.Running)
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
                    if (state.permalink.isNotBlank()) Text("Permalink: ${state.permalink}")
                    Text("Output: ${state.outputFolder}")
                }
                is RunStateValue.Failed -> Text(state.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                is RunStateValue.Cancelled -> Text("Cancelled", color = MaterialTheme.colorScheme.error)
                RunStateValue.Idle -> Unit
            }

            val enabled = isoVerified && outputPicked && state !is RunStateValue.Running
            Button(onClick = onRun, enabled = enabled) { Text("Randomize") }
            when {
                !isoVerified -> Text("Pick and verify a clean ISO first.", style = MaterialTheme.typography.bodySmall)
                !outputPicked -> Text("Pick an output folder first.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun queryIso(context: Context, uri: Uri): Triple<String, Long, Long> {
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
