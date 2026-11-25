package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.OptionDef
import io.github.thesword1.wwrando.data.SettingsLogic
import io.github.thesword1.wwrando.service.RunState
import io.github.thesword1.wwrando.service.RunStateValue

/** Full-screen settings view: preset management plus one collapsible section per option group. */
@Composable
fun SettingsScreen(viewModel: SettingsViewModel, onBack: () -> Unit) {
    val runState by RunState.state.collectAsState()
    val runActive = runState is RunStateValue.Running
    viewModel.version // Any store mutation bumps this, so the screen re-reads the plain getters.

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Settings", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
        }

        PresetCard(viewModel = viewModel, runActive = runActive)

        viewModel.schema.groupBy { it.group }.forEach { (group, options) ->
            GroupSection(group = group, options = options, viewModel = viewModel, runActive = runActive)
        }
    }
}

@Composable
private fun PresetCard(viewModel: SettingsViewModel, runActive: Boolean) {
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
                OutlinedButton(onClick = { showSave = true }, enabled = !runActive) { Text("Save as…") }
                OutlinedButton(
                    onClick = { showDelete = true },
                    enabled = !runActive && active != SettingsLogic.DEFAULT_PRESET_NAME,
                ) { Text("Delete") }
                OutlinedButton(onClick = viewModel::resetToDefaults, enabled = !runActive) { Text("Reset to defaults") }
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

@Composable
private fun GroupSection(
    group: String,
    options: List<OptionDef>,
    viewModel: SettingsViewModel,
    runActive: Boolean,
) {
    var expanded by remember { mutableStateOf(false) }

    Card(Modifier.fillMaxWidth()) {
        Column {
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "▾ $group" else "▸ $group", style = MaterialTheme.typography.titleMedium)
            }
            if (expanded) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    options.forEach { option -> OptionRow(option, viewModel, runActive) }
                }
            }
        }
    }
}

@Composable
private fun OptionRow(option: OptionDef, viewModel: SettingsViewModel, runActive: Boolean) {
    var showDescription by remember { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(
                Modifier.weight(1f).clickable { showDescription = true },
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(optionLabel(option.name), style = MaterialTheme.typography.bodyLarge)
                Text(
                    option.description,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            when (option) {
                is OptionDef.Bool -> Switch(
                    checked = viewModel.effective(option.name) as Boolean,
                    onCheckedChange = { viewModel.set(option.name, it) },
                    enabled = !runActive,
                )
                is OptionDef.Enum -> Dropdown(
                    selected = viewModel.effective(option.name) as String,
                    options = option.choices,
                    enabled = !runActive,
                    onSelect = { viewModel.set(option.name, it) },
                )
                is OptionDef.IntOption -> IntStepper(
                    option = option,
                    value = viewModel.effective(option.name) as Int,
                    enabled = !runActive,
                    onChange = { viewModel.set(option.name, it) },
                )
                is OptionDef.Multi -> MultiButton(
                    option = option,
                    selected = viewModel.effective(option.name) as List<String>,
                    enabled = !runActive,
                    onChange = { viewModel.set(option.name, it) },
                )
            }
        }
    }

    if (showDescription) {
        AlertDialog(
            onDismissRequest = { showDescription = false },
            title = { Text(optionLabel(option.name)) },
            text = { Text(option.description) },
            confirmButton = { TextButton(onClick = { showDescription = false }) { Text("Close") } },
        )
    }
}

@Composable
private fun PresetDropdown(options: List<String>, enabled: Boolean, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }, enabled = enabled) { Text("Load") }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { preset ->
                DropdownMenuItem(text = { Text(preset) }, onClick = { expanded = false; onSelect(preset) })
            }
        }
    }
}

@Composable
private fun Dropdown(selected: String, options: List<String>, enabled: Boolean, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }, enabled = enabled) { Text(selected, maxLines = 1) }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { choice ->
                DropdownMenuItem(text = { Text(choice) }, onClick = { expanded = false; onSelect(choice) })
            }
        }
    }
}

@Composable
private fun IntStepper(option: OptionDef.IntOption, value: Int, enabled: Boolean, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { onChange(value - 1) }, enabled = enabled && value > option.minimum) { Text("−") }
        Text("$value", modifier = Modifier.padding(horizontal = 8.dp))
        OutlinedButton(onClick = { onChange(value + 1) }, enabled = enabled && value < option.maximum) { Text("+") }
    }
}

@Composable
private fun MultiButton(option: OptionDef.Multi, selected: List<String>, enabled: Boolean, onChange: (List<String>) -> Unit) {
    var showDialog by remember { mutableStateOf(false) }
    OutlinedButton(onClick = { showDialog = true }, enabled = enabled) { Text("${selected.size} selected") }
    if (showDialog) {
        MultiChoiceDialog(
            title = optionLabel(option.name),
            choices = option.choices,
            selected = selected,
            onDismiss = { showDialog = false },
            onConfirm = { onChange(it); showDialog = false },
        )
    }
}

@Composable
private fun MultiChoiceDialog(
    title: String,
    choices: List<String>,
    selected: List<String>,
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit,
) {
    var pending by remember(selected) { mutableStateOf(selected.toSet()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                choices.forEach { choice ->
                    Row(
                        Modifier.fillMaxWidth().clickable {
                            pending = if (choice in pending) pending - choice else pending + choice
                        },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = choice in pending,
                            onCheckedChange = { checked ->
                                pending = if (checked) pending + choice else pending - choice
                            },
                        )
                        Text(choice)
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { onConfirm(choices.filter { it in pending }) }) { Text("OK") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun SavePresetDialog(onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Save preset") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it; error = null },
                    label = { Text("Name") },
                    singleLine = true,
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val name = SettingsLogic.normalizePresetName(text)
                if (name == SettingsLogic.DEFAULT_PRESET_NAME || !SettingsLogic.isValidPresetName(name)) {
                    error = "Use 1-40 letters, digits, space, _ or -."
                } else {
                    onSave(name)
                }
            }) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

private fun optionLabel(name: String): String =
    name.split('_').joinToString(" ") { word -> word.replaceFirstChar { it.uppercase() } }
