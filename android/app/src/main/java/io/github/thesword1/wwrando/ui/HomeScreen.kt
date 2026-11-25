package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.TermuxStatus

/**
 * The home screen: Termux health, automatic setup status, and the real-run section. MainActivity only
 * hosts it; state lives in [RandoViewModel] (and the real run lives in RandoRunService).
 */
@Composable
fun HomeScreen(
    termuxStatus: TermuxStatus,
    permissionDenials: Int,
    viewModel: RandoViewModel,
    outputsViewModel: OutputsViewModel,
    settingsViewModel: SettingsViewModel,
    onRequestPermission: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onEditSettings: () -> Unit,
    onOpenHistory: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("WW Randomizer", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            TextButton(onClick = onOpenHistory) { Text("History") }
        }

        TermuxCard(
            status = termuxStatus,
            permissionDenials = permissionDenials,
            onRequestPermission = onRequestPermission,
            onOpenAppSettings = onOpenAppSettings,
        )

        SetupStatusCard(setup = viewModel.setup, ready = viewModel.setupInstalled, onRetry = viewModel::runSetup)

        SettingsCard(viewModel = settingsViewModel, onEditSettings = onEditSettings)

        RunSection(viewModel = viewModel, trackerEnabled = settingsViewModel.trackerEnabled())

        OutputsSection(viewModel = viewModel, outputsViewModel = outputsViewModel)
    }
}

@Composable
private fun TermuxCard(
    status: TermuxStatus,
    permissionDenials: Int,
    onRequestPermission: () -> Unit,
    onOpenAppSettings: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Termux", style = MaterialTheme.typography.titleMedium)
            when {
                !status.installed -> {
                    Text("Termux is not installed. Install it (0.118+) and grant the WW Randomizer RUN_COMMAND permission.")
                }
                !status.newEnough -> {
                    Text("Termux ${status.versionName ?: "?"} is too old. Update to 0.118 or newer.")
                }
                !status.runCommandGranted && permissionDenials < 2 -> {
                    Text("Termux needs permission to run the randomizer in the background.")
                    Button(onClick = onRequestPermission) { Text("Grant RUN_COMMAND permission") }
                }
                !status.runCommandGranted -> {
                    Text("RUN_COMMAND permission was denied. Open app settings to grant it, then set the Termux property allow-external-apps = true.")
                    Button(onClick = onOpenAppSettings) { Text("Open app settings") }
                }
                else -> Text("Termux ${status.versionName ?: ""} ready.")
            }
        }
    }
}

@Composable
private fun SetupStatusCard(setup: SetupUiState, ready: Boolean, onRetry: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Setup", style = MaterialTheme.typography.titleMedium)
            when {
                setup.error != null -> {
                    Text(
                        "Failed: ${setup.error}",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Button(onClick = onRetry) { Text("Retry") }
                }
                setup.running -> {
                    if (setup.stepTotal > 0) {
                        LinearProgressIndicator(
                            progress = { setup.stepIndex.toFloat() / setup.stepTotal },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    Text(setup.stepLabel.ifBlank { "Setting up..." })
                    setup.log.takeLast(6).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
                ready -> Text("Ready")
                else -> Text("Setup required.")
            }
        }
    }
}

@Composable
private fun SettingsCard(viewModel: SettingsViewModel, onEditSettings: () -> Unit) {
    viewModel.version // Re-read the plain getters whenever the store changes.
    val preset = viewModel.activePresetName
    val modified = viewModel.isModified
    val changes = viewModel.changesCount
    val tracker = viewModel.trackerEnabled()

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Settings", style = MaterialTheme.typography.titleMedium)
            Text(
                "Preset: $preset${if (modified) " (modified)" else ""} · $changes ${if (changes == 1) "change" else "changes"} · tracker ${if (tracker) "on" else "off"}",
                style = MaterialTheme.typography.bodySmall,
            )
            Button(onClick = onEditSettings) { Text("Edit settings") }
        }
    }
}
