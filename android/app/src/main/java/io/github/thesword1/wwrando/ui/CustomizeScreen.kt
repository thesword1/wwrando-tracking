package io.github.thesword1.wwrando.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Casino
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.ColorLogic
import io.github.thesword1.wwrando.data.CustomizeLogic
import io.github.thesword1.wwrando.data.ModelMetadata

/** Customize rail section: model preview, model import/selection, toggles, presets and per-color edit. */
@Composable
fun CustomizeScreen(viewModel: CustomizeViewModel) {
    val state = viewModel.state
    viewModel.version
    val metadata = viewModel.metadata
    val defaults = viewModel.defaultColors
    val presets = viewModel.presetNames
    val installed = viewModel.installed

    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri?.let { viewModel.importModel(it) }
    }
    val savePresetLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri ->
        uri?.let { viewModel.saveColorPreset(it) }
    }
    val loadPresetLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri?.let { viewModel.loadColorPreset(it) }
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Customize", style = MaterialTheme.typography.headlineSmall)
        PreviewCard(preview = viewModel.preview, isRandom = viewModel.isRandomModel, metadata = metadata)

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Player model", style = MaterialTheme.typography.titleMedium)
                ModelDropdown(
                    selected = state.playerModel,
                    installed = installed,
                    onSelect = viewModel::selectModel,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { importLauncher.launch("*/*") }) { Text("Import model (.zip)") }
                    OutlinedButton(
                        onClick = { viewModel.deleteModel(state.playerModel) },
                        enabled = state.playerModel !in setOf("Link", "Random", "Random (exclude Link)"),
                    ) { Text("Delete model") }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Cosmetic options", style = MaterialTheme.typography.titleMedium)
                ToggleRow(
                    label = if (metadata.casualClothesOptionText.length > 28) {
                        metadata.casualClothesOptionText.take(28)
                    } else {
                        metadata.casualClothesOptionText
                    },
                    checked = state.casualClothes,
                    enabled = !metadata.disableCasualClothes,
                    onChange = viewModel::toggleCasual,
                )
                ToggleRow(
                    label = "Disable custom voice",
                    checked = state.disableVoice,
                    enabled = viewModel.voiceAvailable,
                    onChange = viewModel::toggleVoice,
                )
                ToggleRow(
                    label = "Disable custom items",
                    checked = state.disableItems,
                    enabled = state.playerModel != "Link",
                    onChange = viewModel::toggleItems,
                )
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Color preset", style = MaterialTheme.typography.titleMedium)
                Dropdown(selected = state.colorPreset, options = presets, enabled = true, onSelect = viewModel::selectPreset)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = { savePresetLauncher.launch("color-preset.txt") },
                        enabled = !viewModel.isRandomModel,
                    ) { Text("Save colors") }
                    OutlinedButton(onClick = { loadPresetLauncher.launch(arrayOf("text/plain", "application/octet-stream")) }) {
                        Text("Load colors")
                    }
                }
            }
        }

        if (viewModel.isRandomModel) {
            Card(Modifier.fillMaxWidth()) {
                Text(
                    "Colors are hidden for Random models.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(12.dp),
                )
            }
        } else if (metadata.errorMessage != null) {
            Card(Modifier.fillMaxWidth()) {
                Text(
                    "Syntax error in metadata.txt: ${metadata.errorMessage}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(12.dp),
                )
            }
        } else {
            ColorsCard(
                defaults = defaults,
                viewModel = viewModel,
            )
        }

        if (metadata.author != null || metadata.comment != null) {
            Text(
                listOfNotNull(
                    metadata.author?.let { "Author: $it" },
                    metadata.comment?.let { "Author's comment: $it" },
                ).joinToString("\n"),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }

    viewModel.error?.let { error ->
        AlertDialog(
            onDismissRequest = viewModel::clearError,
            title = { Text("Customize") },
            text = { Text(error) },
            confirmButton = { TextButton(onClick = viewModel::clearError) { Text("Close") } },
        )
    }
}

@Composable
private fun PreviewCard(preview: androidx.compose.ui.graphics.ImageBitmap?, isRandom: Boolean, metadata: ModelMetadata) {
    Card(Modifier.fillMaxWidth()) {
        Box(Modifier.fillMaxWidth().height(360.dp).padding(8.dp), contentAlignment = Alignment.Center) {
            when {
                preview != null -> Image(bitmap = preview, contentDescription = "Model preview")
                isRandom -> Text("No preview for Random models.", textAlign = TextAlign.Center)
                metadata.errorMessage != null -> Text("Preview unavailable.", textAlign = TextAlign.Center)
                else -> Text("No preview available.", textAlign = TextAlign.Center)
            }
        }
    }
}

@Composable
private fun ModelDropdown(selected: String, installed: List<String>, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val options = buildList {
        add("Link")
        addAll(installed)
        if (installed.isNotEmpty()) {
            add("Random")
            add("Random (exclude Link)")
        }
    }
    Box {
        OutlinedButton(onClick = { expanded = true }) { Text(selected, maxLines = 1) }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { choice ->
                DropdownMenuItem(text = { Text(choice) }, onClick = { expanded = false; onSelect(choice) })
            }
        }
    }
}

@Composable
private fun ToggleRow(label: String, checked: Boolean, enabled: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange, enabled = enabled)
    }
}

@Composable
private fun ColorsCard(defaults: Map<String, List<Int>>, viewModel: CustomizeViewModel) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Colors", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { viewModel.randomizeAll(false) }) { Text("Randomize colors (orderly)") }
                OutlinedButton(onClick = { viewModel.randomizeAll(true) }) { Text("Randomize colors (chaotic)") }
            }
            defaults.forEach { (name, default) ->
                ColorRow(
                    name = name,
                    current = CustomizeLogic.getColor(viewModel.state, viewModel.metadata, defaults, name),
                    default = default,
                    onPick = { color -> viewModel.setColor(name, color) },
                    onRandom = { viewModel.randomizeOne(name) },
                    onReset = { viewModel.resetOne(name) },
                )
            }
        }
    }
}

@Composable
private fun ColorRow(
    name: String,
    current: List<Int>,
    default: List<Int>,
    onPick: (List<Int>) -> Unit,
    onRandom: () -> Unit,
    onReset: () -> Unit,
) {
    var pickerOpen by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(name, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        Box(
            Modifier.size(28.dp).background(colorRgb(current), RoundedCornerShape(4.dp))
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(4.dp))
                .clickable { pickerOpen = true },
        )
        TextButton(onClick = onRandom) { Text("Random") }
        TextButton(onClick = onReset, enabled = current != default) { Text("Reset") }
    }
    if (pickerOpen) {
        ColorPickerDialog(
            initial = current,
            onDismiss = { pickerOpen = false },
            onConfirm = { onPick(it); pickerOpen = false },
        )
    }
}

@Composable
private fun ColorPickerDialog(initial: List<Int>, onDismiss: () -> Unit, onConfirm: (List<Int>) -> Unit) {
    var hsv by remember(initial) {
        mutableStateOf(ColorLogic.rgbToHsv(intArrayOf(initial[0], initial[1], initial[2])))
    }
    var hex by remember(initial) { mutableStateOf(hexOf(initial)) }
    var hexError by remember { mutableStateOf(false) }

    fun updateHsv(next: ColorLogic.Hsv) {
        hsv = next
        val rgb = ColorLogic.hsvToRgb(next)
        hex = hexOf(rgb.toList())
        hexError = false
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Select color") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(
                    Modifier.fillMaxWidth().height(40.dp).background(
                        colorRgb(ColorLogic.hsvToRgb(hsv).toList()),
                        RoundedCornerShape(6.dp),
                    ),
                )
                HsvSlider("Hue", hsv.h, 0, 359) { updateHsv(hsv.copy(h = it)) }
                HsvSlider("Saturation", hsv.s, 0, 100) { updateHsv(hsv.copy(s = it)) }
                HsvSlider("Value", hsv.v, 0, 100) { updateHsv(hsv.copy(v = it)) }
                OutlinedTextField(
                    value = hex,
                    onValueChange = { value ->
                        hex = value
                        val parsed = parseHex(value)
                        if (parsed == null) {
                            hexError = true
                        } else {
                            hexError = false
                            hsv = ColorLogic.rgbToHsv(intArrayOf(parsed[0], parsed[1], parsed[2]))
                        }
                    },
                    label = { Text("Hex") },
                    singleLine = true,
                    isError = hexError,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(ColorLogic.hsvToRgb(hsv).toList()) }) { Text("OK") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun HsvSlider(label: String, value: Int, minimum: Int, maximum: Int, onChange: (Int) -> Unit) {
    Column {
        Text("$label: $value", style = MaterialTheme.typography.bodySmall)
        Slider(
            value = value.toFloat(),
            onValueChange = { onChange(it.toInt()) },
            valueRange = minimum.toFloat()..maximum.toFloat(),
        )
    }
}

private fun colorRgb(color: List<Int>): Color = Color(color[0], color[1], color[2])

private fun hexOf(color: List<Int>): String =
    "#" + color.joinToString("") { it.toString(16).uppercase().padStart(2, '0') }

private fun parseHex(value: String): List<Int>? {
    val hex = value.removePrefix("#")
    if (hex.length != 6) return null
    val int = hex.toIntOrNull(16) ?: return null
    return listOf((int shr 16) and 0xFF, (int shr 8) and 0xFF, int and 0xFF)
}
