package io.github.thesword1.wwrando

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.data.SelfCheckInput
import io.github.thesword1.wwrando.data.SelfCheckLogic
import io.github.thesword1.wwrando.ui.AppScaffold
import io.github.thesword1.wwrando.ui.HistoryScreen
import io.github.thesword1.wwrando.ui.HistoryViewModel
import io.github.thesword1.wwrando.ui.IsoStatus
import io.github.thesword1.wwrando.ui.OutputsViewModel
import io.github.thesword1.wwrando.ui.RandoViewModel
import io.github.thesword1.wwrando.ui.SettingsViewModel

/**
 * Thin host for the rail shell: it runs startup self-check/setup, drives the RUN_COMMAND and
 * notification permission requests, and overlays the run history. All setup/run state lives in the
 * ViewModels.
 */
class MainActivity : ComponentActivity() {
    private val viewModel: RandoViewModel by viewModels()
    private val outputsViewModel: OutputsViewModel by viewModels()
    private val settingsViewModel: SettingsViewModel by viewModels()
    private val historyViewModel: HistoryViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("rando", MODE_PRIVATE)
        setContent {
            MaterialTheme {
                var permissionDenials by remember { mutableIntStateOf(prefs.getInt("run_command_denials", 0)) }
                var termuxStatus by remember { mutableStateOf(RandoBridge.status(this)) }
                var showHistory by remember { mutableStateOf(false) }

                val permissionLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { isGranted ->
                    permissionDenials = if (isGranted) 0 else permissionDenials + 1
                    prefs.edit().putInt("run_command_denials", permissionDenials).apply()
                    termuxStatus = RandoBridge.status(this)
                    if (isGranted) viewModel.ensureSetup()
                }

                val notificationLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { _ -> }

                LaunchedEffect(Unit) {
                    if (termuxStatus.installed && !termuxStatus.runCommandGranted && permissionDenials < 2) {
                        permissionLauncher.launch(RandoBridge.PERMISSION_RUN_COMMAND)
                    }
                    val canNotify = ContextCompat.checkSelfPermission(
                        this@MainActivity, Manifest.permission.POST_NOTIFICATIONS,
                    ) == PackageManager.PERMISSION_GRANTED
                    if (!canNotify) notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }

                BackHandler(enabled = showHistory) { showHistory = false }

                if (showHistory) {
                    HistoryScreen(viewModel = historyViewModel, onBack = { showHistory = false })
                } else if (viewModel.setup.running) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                } else {
                    val selfCheck = SelfCheckLogic.issues(
                        SelfCheckInput(
                            termuxInstalled = termuxStatus.installed,
                            termuxNewEnough = termuxStatus.newEnough,
                            runCommandGranted = termuxStatus.runCommandGranted,
                            setupReady = viewModel.setupInstalled,
                            setupRunning = viewModel.setup.running,
                            setupError = viewModel.setup.error,
                            isoPicked = viewModel.iso.name != null,
                            isoVerified = viewModel.iso.status == IsoStatus.Verified,
                            outputPicked = viewModel.outputFolder != null,
                        ),
                    )
                    AppScaffold(
                        selfCheck = selfCheck,
                        permissionDenials = permissionDenials,
                        viewModel = viewModel,
                        outputsViewModel = outputsViewModel,
                        settingsViewModel = settingsViewModel,
                        onRequestPermission = { permissionLauncher.launch(RandoBridge.PERMISSION_RUN_COMMAND) },
                        onInstallTermux = { openTermuxStore() },
                        onOpenAppSettings = {
                            startActivity(
                                Intent(
                                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:$packageName"),
                                ),
                            )
                        },
                        onOpenHistory = {
                            historyViewModel.refresh()
                            showHistory = true
                        },
                    )
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // A fresh install (or a stale bundle) sets itself up; idempotent and skipped once Ready.
        viewModel.ensureSetup()
    }

    private fun openTermuxStore() {
        runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=com.termux")))
        }
    }
}
