package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.SettingsLogic

/** Home's preset selector: load/switch, save, delete, reset. Covers Logic + Tweaks + Starting items. */
@Composable
fun PresetCard(viewModel: SettingsViewModel, runActive: Boolean) {
    var showSave by remember { mutableStateOf(false) }
    var showDelete by remember { mutableStateOf(false) }
    val active = viewModel.activePresetName

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "Preset: $active${if (viewModel.isModified) " (modified)" else ""} · ${viewModel.changesCount} ${if (viewModel.changesCount == 1) "change" else "changes"}",
                style = MaterialTheme.typography.titleMedium,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                PresetDropdown(
                    options = viewModel.listPresets(),
                    enabled = !runActive,
                    onSelect = viewModel::loadPreset,
                )
                OutlinedButton(onClick = { showSave = true }, enabled = !runActive) { Text("Save preset") }
                OutlinedButton(
                    onClick = { showDelete = true },
                    enabled = !runActive && active != SettingsLogic.DEFAULT_PRESET_NAME,
                ) { Text("Delete") }
                OutlinedButton(onClick = viewModel::resetToDefaults, enabled = !runActive) { Text("Reset") }
            }
        }
    }

    if (showSave) {
        SavePresetDialog(
            onDismiss = { showSave = false },
            onSave = { name -> viewModel.savePreset(name)?.also { showSave = false } },
        )
    }
    if (showDelete) {
        AlertDialog(
            onDismissRequest = { showDelete = false },
            title = { Text("Delete preset?") },
            text = { Text("Delete the preset \"$active\"?") },
            confirmButton = {
                TextButton(onClick = {
                    showDelete = false
                    viewModel.deletePreset(active)
                }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { showDelete = false }) { Text("Cancel") } },
        )
    }
}
