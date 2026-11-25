package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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

/** Collapsible section with one row per option. Hidden options are skipped by [visible]. */
@Composable
fun SectionCard(
    title: String,
    options: List<OptionDef>,
    viewModel: SettingsViewModel,
    runActive: Boolean,
    visible: (String) -> Boolean = { true },
) {
    var expanded by remember { mutableStateOf(false) }
    val shown = options.filter { visible(it.name) }

    Card(Modifier.fillMaxWidth()) {
        Column {
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "▾ $title" else "▸ $title", style = MaterialTheme.typography.titleMedium)
            }
            if (expanded) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    shown.forEach { option ->
                        OptionRow(
                            option = option,
                            value = viewModel.effective(option.name),
                            enabled = !runActive,
                            onChange = { viewModel.set(option.name, it) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun OptionRow(option: OptionDef, value: Any, enabled: Boolean, onChange: (Any) -> Unit) {
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
                    checked = value as Boolean,
                    onCheckedChange = { onChange(it) },
                    enabled = enabled,
                )
                is OptionDef.Enum -> Dropdown(
                    selected = value as String,
                    options = option.choices,
                    enabled = enabled,
                    onSelect = { onChange(it) },
                )
                is OptionDef.IntOption -> IntStepper(
                    option = option,
                    value = value as Int,
                    enabled = enabled,
                    onChange = { onChange(it) },
                )
                is OptionDef.Multi -> MultiButton(
                    option = option,
                    selected = value as List<String>,
                    enabled = enabled,
                    onChange = { onChange(it) },
                )
                is OptionDef.ItemList -> Text(
                    "${(value as List<String>).size} selected",
                    style = MaterialTheme.typography.bodySmall,
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
fun Dropdown(selected: String, options: List<String>, enabled: Boolean, onSelect: (String) -> Unit) {
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
fun IntStepper(option: OptionDef.IntOption, value: Int, enabled: Boolean, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedButton(onClick = { onChange(value - 1) }, enabled = enabled && value > option.minimum) { Text("−") }
        Text("$value", modifier = Modifier.padding(horizontal = 8.dp))
        OutlinedButton(onClick = { onChange(value + 1) }, enabled = enabled && value < option.maximum) { Text("+") }
    }
}

@Composable
fun MultiButton(option: OptionDef.Multi, selected: List<String>, enabled: Boolean, onChange: (List<String>) -> Unit) {
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
fun MultiChoiceDialog(
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
fun PresetDropdown(options: List<String>, enabled: Boolean, onSelect: (String) -> Unit) {
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
fun SavePresetDialog(onDismiss: () -> Unit, onSave: (String) -> Unit) {
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

fun optionLabel(name: String): String =
    name.split('_').joinToString(" ") { word -> word.replaceFirstChar { it.uppercase() } }
