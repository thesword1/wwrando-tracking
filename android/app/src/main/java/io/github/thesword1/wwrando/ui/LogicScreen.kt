package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.RailSections
import io.github.thesword1.wwrando.service.RunState
import io.github.thesword1.wwrando.service.RunStateValue

/** Logic rail section: desktop logic groups plus triforce shards and an advanced expandable. */
@Composable
fun LogicScreen(viewModel: SettingsViewModel) {
    val runState by RunState.state.collectAsState()
    val runActive = runState is RunStateValue.Running
    viewModel.version

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Logic", style = MaterialTheme.typography.headlineSmall)

        RailSections.logicGroups.forEach { group ->
            val options = group.options.mapNotNull { viewModel.schemaByName[it] }
            SectionCard(
                title = group.title,
                options = options,
                viewModel = viewModel,
                runActive = runActive,
                visible = viewModel::isVisible,
            )
        }

        AdvancedSettingsCard(viewModel = viewModel, runActive = runActive)
    }
}

@Composable
private fun AdvancedSettingsCard(viewModel: SettingsViewModel, runActive: Boolean) {
    var expanded by remember { mutableStateOf(false) }

    Card(Modifier.fillMaxWidth()) {
        Column {
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "▾ Advanced settings" else "▸ Advanced settings", style = MaterialTheme.typography.titleMedium)
            }
            if (expanded) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    RailSections.logicAdvancedGroups.forEach { group ->
                        val options = group.options.mapNotNull { viewModel.schemaByName[it] }
                            .filter { viewModel.isVisible(it.name) }
                        if (options.isEmpty()) return@forEach
                        Text(group.title, style = MaterialTheme.typography.titleSmall)
                        options.forEach { option ->
                            OptionRow(
                                option = option,
                                value = viewModel.effective(option.name),
                                enabled = !runActive,
                                onChange = { viewModel.set(option.name, it) },
                            )
                            if (option.name == "randomize_enemies") {
                                Text(
                                    "Warning: this can produce unbeatable or broken seeds.",
                                    color = MaterialTheme.colorScheme.error,
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
