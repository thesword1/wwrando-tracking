package io.github.thesword1.wwrando

import android.content.Intent
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
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.ui.HomeScreen
import io.github.thesword1.wwrando.ui.RandoViewModel

/**
 * Thin host for the home screen: it only checks Termux health, drives the RUN_COMMAND permission
 * request, and hands all setup/run state to [RandoViewModel].
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

                LaunchedEffect(Unit) {
                    if (termuxStatus.installed && !granted && permissionDenials < 2) {
                        permissionLauncher.launch(RandoBridge.PERMISSION_RUN_COMMAND)
                    }
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
