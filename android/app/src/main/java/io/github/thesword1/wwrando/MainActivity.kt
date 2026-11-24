package io.github.thesword1.wwrando

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.ui.HomeScreen
import io.github.thesword1.wwrando.ui.RandoViewModel

/**
 * Thin host for the home screen: it checks Termux health, drives the RUN_COMMAND and notification
 * permission requests, and hands all setup/run state to [RandoViewModel].
 */
class MainActivity : ComponentActivity() {
    private val viewModel: RandoViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("rando", MODE_PRIVATE)

        setContent {
            MaterialTheme {
                var permissionDenials by remember { mutableIntStateOf(prefs.getInt("run_command_denials", 0)) }
                var granted by remember { mutableStateOf(RandoBridge.hasRunCommandPermission(this)) }
                var termuxStatus by remember { mutableStateOf(RandoBridge.status(this)) }

                val permissionLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { isGranted ->
                    granted = isGranted
                    permissionDenials = if (isGranted) 0 else permissionDenials + 1
                    prefs.edit().putInt("run_command_denials", permissionDenials).apply()
                    termuxStatus = RandoBridge.status(this)
                }

                val notificationLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { _ -> }

                LaunchedEffect(Unit) {
                    if (termuxStatus.installed && !granted && permissionDenials < 2) {
                        permissionLauncher.launch(RandoBridge.PERMISSION_RUN_COMMAND)
                    }
                    // Ask before the first run; denial must not block the run (the service still works).
                    val canNotify = ContextCompat.checkSelfPermission(
                        this@MainActivity, Manifest.permission.POST_NOTIFICATIONS,
                    ) == PackageManager.PERMISSION_GRANTED
                    if (!canNotify) notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }

                HomeScreen(
                    termuxStatus = termuxStatus,
                    permissionDenials = permissionDenials,
                    viewModel = viewModel,
                    onRequestPermission = { permissionLauncher.launch(RandoBridge.PERMISSION_RUN_COMMAND) },
                    onOpenAppSettings = {
                        startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:$packageName"),
                            ),
                        )
                    },
                )
            }
        }
    }
}
