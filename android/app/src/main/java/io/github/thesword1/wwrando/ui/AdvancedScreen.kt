package io.github.thesword1.wwrando.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

private const val REPO_URL = "https://github.com/thesword1/wwrando-tracking"
private const val UPSTREAM_URL = "https://github.com/LagoLunatic/wwrando"

/**
 * Advanced rail section: generate/copy a permalink for the current settings + Home seed, paste a
 * permalink to load its settings and seed, and an About card with version/build/links.
 */
@Composable
fun AdvancedScreen(
    settingsViewModel: SettingsViewModel,
    viewModel: RandoViewModel,
    advancedViewModel: AdvancedViewModel,
) {
    val context = LocalContext.current
    val diff = settingsViewModel.currentDiff()
    val seed = viewModel.seed
    val shownPermalink = if (advancedViewModel.isStale(diff, seed)) null else advancedViewModel.permalink
    var confirmLoad by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Advanced", style = MaterialTheme.typography.headlineSmall)

        PermalinkCard(
            permalink = shownPermalink,
            loading = advancedViewModel.loading,
            onGenerate = { advancedViewModel.generate(seed, diff, viewModel::onSeedChanged) },
            onCopy = { shownPermalink?.let { copyText(context, it) } },
        )

        PasteCard(
            pasteText = advancedViewModel.pasteText,
            loading = advancedViewModel.loading,
            error = advancedViewModel.pasteError,
            onPasteChanged = advancedViewModel::onPasteChanged,
            onLoad = {
                if (advancedViewModel.validatePaste()) confirmLoad = true
            },
        )

        AboutCard(context = context, info = advancedViewModel.about())
    }

    if (confirmLoad) {
        AlertDialog(
            onDismissRequest = { confirmLoad = false },
            title = { Text("Load permalink?") },
            text = { Text("Replace Logic, Tweaks and Starting items with the permalink's settings?") },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmLoad = false
                        advancedViewModel.load(
                            onSeed = viewModel::onSeedChanged,
                            applySettings = settingsViewModel::applyDecoded,
                        )
                    },
                ) { Text("Replace") }
            },
            dismissButton = { TextButton(onClick = { confirmLoad = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun PermalinkCard(
    permalink: String?,
    loading: Boolean,
    onGenerate: () -> Unit,
    onCopy: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Permalink", style = MaterialTheme.typography.titleMedium)
            Text(
                "Encodes the current Logic, Tweaks and Starting items plus the Home seed.",
                style = MaterialTheme.typography.bodySmall,
            )
            if (permalink != null) {
                OutlinedTextField(
                    value = permalink,
                    onValueChange = {},
                    readOnly = true,
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onGenerate, enabled = !loading) {
                    Text(if (loading) "Working..." else "Generate")
                }
                OutlinedButton(onClick = onCopy, enabled = permalink != null && !loading) {
                    Text("Copy")
                }
            }
        }
    }
}

@Composable
private fun PasteCard(
    pasteText: String,
    loading: Boolean,
    error: String?,
    onPasteChanged: (String) -> Unit,
    onLoad: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Load permalink", style = MaterialTheme.typography.titleMedium)
            Text(
                "Paste a permalink from the desktop app to load its settings and seed.",
                style = MaterialTheme.typography.bodySmall,
            )
            OutlinedTextField(
                value = pasteText,
                onValueChange = onPasteChanged,
                label = { Text("Permalink") },
                singleLine = true,
                isError = error != null,
                modifier = Modifier.fillMaxWidth(),
            )
            if (error != null) {
                Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onLoad, enabled = !loading) { Text("Load") }
        }
    }
}

@Composable
private fun AboutCard(context: Context, info: AboutInfo) {
    var showFullCommit by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("About", style = MaterialTheme.typography.titleMedium)
            Text("Version: ${info.versionName.ifBlank { "unknown" }}", style = MaterialTheme.typography.bodyMedium)

            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Build commit: ", style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = { showFullCommit = !showFullCommit }) {
                    Text(if (showFullCommit) info.bundledCommit else info.bundledCommit.take(7))
                }
            }
            if (showFullCommit) {
                Text(info.bundledCommit, style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = { copyText(context, info.bundledCommit) }) { Text("Copy build commit") }

            if (!info.installedCommit.isNullOrBlank()) {
                Text("Installed tree commit: ${info.installedCommit}", style = MaterialTheme.typography.bodyMedium)
            }
            Text(
                "Termux version: ${info.termuxVersion ?: "not installed"}",
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = { openUrl(context, REPO_URL) }) { Text("Repository: thesword1/wwrando-tracking") }
            TextButton(onClick = { openUrl(context, UPSTREAM_URL) }) { Text("Upstream: LagoLunatic/wwrando") }
        }
    }
}

private fun copyText(context: Context, text: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("text", text))
}

private fun openUrl(context: Context, url: String) {
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
}
