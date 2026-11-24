package io.github.thesword1.wwrando.data

import android.content.Context
import androidx.core.content.ContextCompat

/** Outcome of a Termux RUN_COMMAND call: the result bundle Termux delivers to our PendingIntent. */
data class RandoRunResult(val exitCode: Int, val stdout: String, val stderr: String, val error: String? = null) {
    val ok: Boolean get() = exitCode == 0
}

/** Termux health facts the home screen needs to show install/permission guidance. */
data class TermuxStatus(
    val installed: Boolean,
    val versionName: String?,
    val newEnough: Boolean,
    val runCommandGranted: Boolean,
)

/**
 * Constants and Termux checks shared by the RUN_COMMAND plumbing and the first-run setup. Mirrors
 * :app's TermuxGhtoolBridge so the randomizer app stays fully independent of GameHub.
 */
object RandoBridge {
    const val PERMISSION_RUN_COMMAND = "com.termux.permission.RUN_COMMAND"
    /** RUN_COMMAND arrived in Termux 0.118; older builds cannot be driven by the app. */
    const val MIN_TERMUX_VERSION = 118

    const val TERMUX_HOME = "/data/data/com.termux/files/home"
    const val SHELL = "/data/data/com.termux/files/usr/bin/sh"
    const val WWRANDO_DIR = "$TERMUX_HOME/wwrando"
    const val VENV_PYTHON = "$WWRANDO_DIR/venv/bin/python"
    const val ANDROID_RUN = "$WWRANDO_DIR/current/android_run.py"
    const val OUTPUT_DIR = "$WWRANDO_DIR/output"

    fun isTermuxInstalled(context: Context): Boolean = isInstalled(context, RandoCommandRunner.TERMUX_PACKAGE)

    fun termuxVersion(context: Context): String? = runCatching {
        context.packageManager.getPackageInfo(RandoCommandRunner.TERMUX_PACKAGE, 0).versionName
    }.getOrNull()

    fun isTermuxNewEnough(version: String?): Boolean {
        val numbers = version?.split(Regex("[^0-9]+"))?.filter { it.isNotBlank() }?.mapNotNull { it.toIntOrNull() }
        if (numbers == null || numbers.size < 2) return false
        return numbers[0] > 0 || (numbers[0] == 0 && numbers[1] >= MIN_TERMUX_VERSION)
    }

    fun hasRunCommandPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, PERMISSION_RUN_COMMAND) ==
            android.content.pm.PackageManager.PERMISSION_GRANTED

    fun status(context: Context): TermuxStatus = TermuxStatus(
        installed = isTermuxInstalled(context),
        versionName = termuxVersion(context),
        newEnough = isTermuxNewEnough(termuxVersion(context)),
        runCommandGranted = hasRunCommandPermission(context),
    )

    fun isInstalled(context: Context, pkg: String): Boolean =
        runCatching { context.packageManager.getPackageInfo(pkg, 0) }.isSuccess
}
