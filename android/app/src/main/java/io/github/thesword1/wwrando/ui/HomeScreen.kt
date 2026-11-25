package io.github.thesword1.wwrando.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.SelfCheckFix
import io.github.thesword1.wwrando.data.SelfCheckIssue
import io.github.thesword1.wwrando.service.RunStateValue

/**
 * Home rail section, in order: Self-Check, ISO + output folder, Randomize, Preset, Seed, outputs.
 */
@Composable
fun HomeScreen(
    selfCheck: List<SelfCheckIssue>,
    permissionDenials: Int,
    viewModel: RandoViewModel,
    outputsViewModel: OutputsViewModel,
    settingsViewModel: SettingsViewModel,
    onRequestPermission: () -> Unit,
    onInstallTermux: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onOpenHistory: () -> Unit,
) {
    val context = LocalContext.current
    val runState by viewModel.runState.collectAsState()
    val runActive = runState is RunStateValue.Running

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
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                )
            }
            viewModel.onOutputFolderPicked(uri)
        }
    }

    val onFix: (SelfCheckFix) -> Unit = { fix ->
        when (fix) {
            SelfCheckFix.InstallTermux, SelfCheckFix.UpdateTermux -> onInstallTermux()
            SelfCheckFix.GrantRunCommand -> onRequestPermission()
            SelfCheckFix.RunSetup -> viewModel.runSetup()
            SelfCheckFix.PickIso -> isoPicker.launch(arrayOf("*/*"))
            SelfCheckFix.PickOutputFolder -> folderPicker.launch(null)
        }
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("WW Randomizer", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
            TextButton(onClick = onOpenHistory) { Text("History") }
        }

        SelfCheckCard(
            issues = selfCheck,
            permissionDenials = permissionDenials,
            onFix = onFix,
            onOpenAppSettings = onOpenAppSettings,
        )

        IsoOutputRow(
            iso = viewModel.iso,
            outputSelected = viewModel.outputFolder != null,
            onPickIso = { isoPicker.launch(arrayOf("*/*")) },
            onPickOutput = { folderPicker.launch(null) },
        )

        RandomizeCard(
            state = runState,
            isoVerified = viewModel.iso.status == IsoStatus.Verified,
            outputPicked = viewModel.outputFolder != null,
            ready = viewModel.setupInstalled,
            onRun = { viewModel.startRealRun(viewModel.seed) },
            onCancel = viewModel::cancelRealRun,
        )

        PresetCard(viewModel = settingsViewModel, runActive = runActive)

        SeedCard(
            seed = viewModel.seed,
            onSeedChanged = viewModel::onSeedChanged,
            onNewSeed = viewModel::newSeed,
        )

        OutputsSection(viewModel = viewModel, outputsViewModel = outputsViewModel)
    }
}
