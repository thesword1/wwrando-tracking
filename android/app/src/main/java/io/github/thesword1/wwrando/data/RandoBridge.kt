package io.github.thesword1.wwrando.data

import android.content.Context
import androidx.core.content.ContextCompat

/** Outcome of a Termux RUN_COMMAND call: the result bundle Termux delivers to our PendingIntent. */
data class RandoRunResult(val exitCode: Int, val stdout: String, val stderr: String, val error: String? = null) {
    val ok: Boolean get() = exitCode == 0
}

/**
 * Constants and Termux checks shared by the RUN_COMMAND plumbing and the first-run script install.
 * Mirrors :app's TermuxGhtoolBridge so the randomizer app stays fully independent of GameHub.
 */
object RandoBridge {
    const val PERMISSION_RUN_COMMAND = "com.termux.permission.RUN_COMMAND"

    const val TERMUX_HOME = "/data/data/com.termux/files/home"
    const val PYTHON = "/data/data/com.termux/files/usr/bin/python"
    const val WWRANDO_DIR = "$TERMUX_HOME/wwrando"
    const val HELLO = "$WWRANDO_DIR/hello.py"

    fun isTermuxInstalled(context: Context): Boolean = isInstalled(context, RandoCommandRunner.TERMUX_PACKAGE)

    fun hasRunCommandPermission(context: Context): Boolean =
        androidx.core.content.ContextCompat.checkSelfPermission(context, PERMISSION_RUN_COMMAND) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED

    fun isInstalled(context: Context, pkg: String): Boolean =
        runCatching { context.packageManager.getPackageInfo(pkg, 0) }.isSuccess
}
