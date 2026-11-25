package io.github.thesword1.wwrando.ui

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
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.OptionDef
import io.github.thesword1.wwrando.data.StartingItemsLogic
import io.github.thesword1.wwrando.service.RunState
import io.github.thesword1.wwrando.service.RunStateValue

/** Starting items rail section: the item picker plus the desktop's Starting Health and Items group. */
@Composable
fun StartingItemsScreen(viewModel: SettingsViewModel) {
    val runState by RunState.state.collectAsState()
    val runActive = runState is RunStateValue.Running
    viewModel.version

    val gearOption = viewModel.schemaByName["starting_gear"] as? OptionDef.ItemList
    val startingGear = viewModel.effective("starting_gear") as List<String>
    val swordMode = viewModel.effective("sword_mode") as String
    val hcs = viewModel.effective("starting_hcs") as Int
    val pohs = viewModel.effective("starting_pohs") as Int
    val extra = viewModel.effective("num_extra_starting_items") as Int

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Starting items", style = MaterialTheme.typography.headlineSmall)

        ItemsCard(
            option = gearOption,
            startingGear = startingGear,
            swordMode = swordMode,
            enabled = !runActive,
            onAdd = { item -> viewModel.set("starting_gear", startingGear + item) },
            onRemove = { item ->
                val list = startingGear.toMutableList()
                list.remove(item)
                viewModel.set("starting_gear", list)
            },
        )

        HealthCard(
            hcs = hcs,
            pohs = pohs,
            extra = extra,
            enabled = !runActive,
            onHcs = { viewModel.set("starting_hcs", it) },
            onPohs = { viewModel.set("starting_pohs", it) },
            onExtra = { viewModel.set("num_extra_starting_items", it) },
        )
    }
}

@Composable
private fun ItemsCard(
    option: OptionDef.ItemList?,
    startingGear: List<String>,
    swordMode: String,
    enabled: Boolean,
    onAdd: (String) -> Unit,
    onRemove: (String) -> Unit,
) {
    var pickerOpen by remember { mutableStateOf(false) }
    val counts = StartingItemsLogic.counts(startingGear)
    val available = option?.let { StartingItemsLogic.availableCounts(it, startingGear, swordMode) } ?: emptyMap()

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Starting Items", style = MaterialTheme.typography.titleMedium)
            if (counts.isEmpty()) {
                Text("Nothing starts unless added.", style = MaterialTheme.typography.bodySmall)
            } else {
                counts.entries.sortedBy { it.key }.forEach { (item, count) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (count > 1) "$item x$count" else item,
                            style = MaterialTheme.typography.bodyLarge,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(onClick = { onRemove(item) }, enabled = enabled) { Text("Remove") }
                    }
                }
            }

            Box {
                OutlinedButton(onClick = { pickerOpen = true }, enabled = enabled && available.isNotEmpty()) {
                    Text("Add item")
                }
                DropdownMenu(expanded = pickerOpen, onDismissRequest = { pickerOpen = false }) {
                    available.entries.sortedBy { it.key }.forEach { (item, left) ->
                        DropdownMenuItem(
                            text = { Text(if (left > 1) "$item ($left left)" else item) },
                            onClick = { pickerOpen = false; onAdd(item) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HealthCard(
    hcs: Int,
    pohs: Int,
    extra: Int,
    enabled: Boolean,
    onHcs: (Int) -> Unit,
    onPohs: (Int) -> Unit,
    onExtra: (Int) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Starting Health and Items", style = MaterialTheme.typography.titleMedium)
            Text(StartingItemsLogic.healthLabel(pohs, hcs), style = MaterialTheme.typography.bodySmall)

            HealthStepperRow("Heart Containers", hcs, 1, 9, enabled, onHcs)
            HealthStepperRow("Heart Pieces", pohs, 0, 44, enabled, onPohs)
            HealthStepperRow("Extra Random Starting Items", extra, 0, 3, enabled, onExtra)
        }
    }
}

@Composable
private fun HealthStepperRow(
    label: String,
    value: Int,
    minimum: Int,
    maximum: Int,
    enabled: Boolean,
    onChange: (Int) -> Unit,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
        OutlinedButton(onClick = { onChange(value - 1) }, enabled = enabled && value > minimum) { Text("−") }
        Text("$value", modifier = Modifier.padding(horizontal = 8.dp))
        OutlinedButton(onClick = { onChange(value + 1) }, enabled = enabled && value < maximum) { Text("+") }
    }
}
