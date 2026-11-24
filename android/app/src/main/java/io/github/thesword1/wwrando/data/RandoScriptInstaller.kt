package io.github.thesword1.wwrando.data

import android.content.Context

/** Outcome of making the bundled Python shim the one Termux runs. */
sealed interface RandoScriptInstallResult {
    data object AlreadyCurrent : RandoScriptInstallResult
    data class Installed(val hash: String) : RandoScriptInstallResult
    data class Failed(val message: String) : RandoScriptInstallResult
}

/**
 * Installs the APK's bundled Python shim into Termux on first launch (and whenever the bundled hash
 * differs from the last installed one). The script body is fed on stdin to a shell that writes it to
 * ~/wwrando/ and chmods it; the RUN_COMMAND intent is reused from [RandoCommandRunner].
 */
class RandoScriptInstaller(private val context: Context) {

    suspend fun ensureInstalled(script: String, installedHash: String?, force: Boolean = false): RandoScriptInstallResult {
        val bundled = ScriptHash.sha256(script)
        if (!ScriptHash.installNeeded(bundled, installedHash, force)) return RandoScriptInstallResult.AlreadyCurrent

        if (!RandoBridge.isTermuxInstalled(context)) {
            return RandoScriptInstallResult.Failed("Termux is not installed")
        }
        if (!RandoBridge.hasRunCommandPermission(context)) {
            return RandoScriptInstallResult.Failed("RUN_COMMAND permission not granted to WW Randomizer")
        }

        val result = RandoCommandRunner.run(
            context = context.applicationContext,
            path = SHELL,
            arguments = arrayOf("-c", WRITE_COMMAND),
            stdin = script,
            workdir = RandoBridge.TERMUX_HOME,
            timeoutMs = INSTALL_TIMEOUT_MS,
        ) ?: return RandoScriptInstallResult.Failed("Script install timed out")

        if (!result.ok) {
            val detail = result.error ?: "exit ${result.exitCode}: ${result.stderr.takeLast(300)}"
            return RandoScriptInstallResult.Failed("Script install failed: $detail")
        }
        return RandoScriptInstallResult.Installed(bundled)
    }

    companion object {
        private const val SHELL = "/data/data/com.termux/files/usr/bin/sh"
        private const val INSTALL_TIMEOUT_MS = 120_000L

        /** Writes stdin to the shim target and chmods it; mkdir -p keeps it idempotent. */
        const val WRITE_COMMAND =
            "mkdir -p ${RandoBridge.WWRANDO_DIR} && cat > ${RandoBridge.HELLO} && chmod +x ${RandoBridge.HELLO}"

        fun bundledHello(context: Context): String =
            context.assets.open("python/hello.py").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
}
