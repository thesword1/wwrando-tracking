package io.github.thesword1.wwrando

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.data.RandoCommandRunner
import io.github.thesword1.wwrando.data.RandoScriptInstallResult
import io.github.thesword1.wwrando.data.RandoScriptInstaller
import kotlinx.coroutines.launch

/**
 * Skeleton screen for the standalone WW Randomizer app: proves the Termux round-trip by installing a
 * trivial Python shim into Termux and running it back through RUN_COMMAND. The real randomize flow
 * replaces this once first-run setup and the CLI driver land.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                var status by remember { mutableStateOf("Ready.") }
                var running by remember { mutableStateOf(false) }
                val scope = rememberCoroutineScope()

                Column(
                    Modifier.fillMaxSize().padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("WW Randomizer (skeleton)", style = MaterialTheme.typography.headlineSmall)
                    Spacer(Modifier.height(16.dp))
                    Button(
                        enabled = !running,
                        onClick = {
                            scope.launch {
                                running = true
                                status = runHello()
                                running = false
                            }
                        },
                    ) { Text(if (running) "Running..." else "Run hello in Termux") }
                    Spacer(Modifier.height(16.dp))
                    Text(status)
                }
            }
        }
    }

    private suspend fun runHello(): String {
        if (!RandoBridge.isTermuxInstalled(this)) return "Termux is not installed."
        if (!RandoBridge.hasRunCommandPermission(this)) {
            return "RUN_COMMAND permission not granted to WW Randomizer."
        }

        val installer = RandoScriptInstaller(this)
        val hello = RandoScriptInstaller.bundledHello(this)
        val prefs = getSharedPreferences("rando", MODE_PRIVATE)
        when (val installed = installer.ensureInstalled(hello, prefs.getString("installed_hash", null))) {
            is RandoScriptInstallResult.Failed -> return installed.message
            is RandoScriptInstallResult.Installed ->
                prefs.edit().putString("installed_hash", installed.hash).apply()
            RandoScriptInstallResult.AlreadyCurrent -> Unit
        }

        val result = RandoCommandRunner.run(this, RandoBridge.PYTHON, arrayOf(RandoBridge.HELLO))
            ?: return "Command timed out."
        return if (result.ok) result.stdout.trim() else "Failed (exit ${result.exitCode}): ${result.stderr.takeLast(300)}"
    }
}
