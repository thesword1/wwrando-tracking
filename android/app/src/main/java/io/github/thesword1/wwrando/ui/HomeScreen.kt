package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.TermuxStatus

/**
 * The whole home screen: Termux health, first-run setup, and a dry-run section. Kept as one
 * composable file so MainActivity only hosts it; the state lives in [RandoViewModel].
 */
@Composable
fun HomeScreen(
    termuxStatus: TermuxStatus,
    permissionDenials: Int,
    viewModel: RandoViewModel,
    onRequestPermission: () -> Unit,
    onOpenAppSettings: () -> Unit,
) {
    val setup = viewModel.setup
    val dryRun = viewModel.dryRun
    var seed by remember { mutableStateOf("") }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("WW Randomizer", style = MaterialTheme.typography.headlineSmall)

        TermuxCard(
            status = termuxStatus,
            permissionDenials = permissionDenials,
            onRequestPermission = onRequestPermission,
            onOpenAppSettings = onOpenAppSettings,
        )

        SetupCard(setup = setup, installed = viewModel.setupInstalled, onRun = viewModel::runSetup)

        DryRunCard(
            state = dryRun,
            seed = seed,
            installed = viewModel.setupInstalled,
            onSeedChange = { seed = it },
            onRun = { viewModel.runDryRun(seed) },
            onCancel = viewModel::cancel,
        )
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
            RowButtons(
                running = setup.running,
                primaryLabel = if (installed) "Re-run setup" else "Run setup",
                onRun = onRun,
            )
        }
    }
}

@Composable
private fun DryRunCard(
    state: DryRunUiState,
    seed: String,
    installed: Boolean,
    onSeedChange: (String) -> Unit,
    onRun: () -> Unit,
    onCancel: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Dry run", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = seed,
                onValueChange = onSeedChange,
                label = { Text("Seed (blank = autoseed)") },
                singleLine = true,
                enabled = !state.running,
                modifier = Modifier.fillMaxWidth(),
            )
            if (state.running) {
                if (state.max > 0) {
                    LinearProgressIndicator(
                        progress = { state.done.toFloat() / state.max },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                Text(state.description.ifBlank { "Randomizing..." })
                OutlinedButton(onClick = onCancel) { Text("Cancel") }
            }
            state.result?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (state.error != null) {
                Text(state.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onRun, enabled = installed && !state.running) { Text("Dry run") }
            if (!installed) Text("Run setup first.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun RowButtons(running: Boolean, primaryLabel: String, onRun: () -> Unit) {
    Button(onClick = onRun, enabled = !running) { Text(if (running) "Working..." else primaryLabel) }
}
