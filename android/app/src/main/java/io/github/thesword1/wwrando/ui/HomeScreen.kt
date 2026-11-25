package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.TermuxStatus

/**
 * The home screen: Termux health, first-run setup, and the real-run section. MainActivity only hosts
 * it; state lives in [RandoViewModel] (and the real run lives in RandoRunService).
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
) {
    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("WW Randomizer", style = MaterialTheme.typography.headlineSmall)

        TermuxCard(
            status = termuxStatus,
            permissionDenials = permissionDenials,
            onRequestPermission = onRequestPermission,
            onOpenAppSettings = onOpenAppSettings,
        )

        SetupCard(setup = viewModel.setup, installed = viewModel.setupInstalled, onRun = viewModel::runSetup)

        SettingsCard(viewModel = settingsViewModel, onEditSettings = onEditSettings)

        RunSection(viewModel = viewModel)

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
private fun SetupCard(setup: SetupUiState, installed: Boolean, onRun: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("First-run setup", style = MaterialTheme.typography.titleMedium)
            Text(if (installed) "Installed and up to date." else "Randomizer sources are not installed yet.")
            if (setup.running) {
                if (setup.stepTotal > 0) {
                    LinearProgressIndicator(
                        progress = { setup.stepIndex.toFloat() / setup.stepTotal },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                Text(setup.stepLabel.ifBlank { "Working..." })
            }
            setup.log.takeLast(6).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (setup.error != null) {
                Text(setup.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onRun, enabled = !setup.running) { Text(if (installed) "Re-run setup" else "Run setup") }
        }
    }
}

@Composable
private fun SettingsCard(viewModel: SettingsViewModel, onEditSettings: () -> Unit) {
    viewModel.version // Re-read the plain getters whenever the store changes.
    val preset = viewModel.activePresetName
    val modified = viewModel.isModified
    val changes = viewModel.changesCount

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Settings", style = MaterialTheme.typography.titleMedium)
            Text(
                "Preset: $preset${if (modified) " (modified)" else ""} · $changes ${if (changes == 1) "change" else "changes"}",
                style = MaterialTheme.typography.bodySmall,
            )
            Button(onClick = onEditSettings) { Text("Edit settings") }
        }
    }
}
