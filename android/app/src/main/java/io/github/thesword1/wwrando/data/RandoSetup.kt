package io.github.thesword1.wwrando.data

import android.content.Context
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Drives the two Termux jobs the app supports today: first-run setup (setup.sh) and a headless dry
 * run (android_run.py). Each job opens a [LoopbackBridge], runs the Termux command, and resolves to
 * the final /done event; step/progress lines are forwarded to [onEvent] as they arrive.
 */
class RandoSetup(
    private val context: Context,
    private val scope: CoroutineScope,
) {
    @Volatile
    private var bridge: LoopbackBridge? = null

    fun closeBridge() {
        bridge?.close()
        bridge = null
    }

    fun installedHash(): String? =
        context.getSharedPreferences("rando", Context.MODE_PRIVATE).getString("installed_sha256", null)

    fun saveInstalledHash(hash: String) {
        context.getSharedPreferences("rando", Context.MODE_PRIVATE).edit().putString("installed_sha256", hash).apply()
    }

    fun bundledHash(): String = readAssetText("wwrando.sha256").trim()

    fun isSetupCurrent(): Boolean = !ScriptHash.installNeeded(bundledHash(), installedHash())

    /** Runs setup.sh in Termux; returns the final /done event (synthetic on timeout or Termux failure). */
    suspend fun runSetup(onEvent: (ProgressEvent) -> Unit): ProgressEvent.Done = withContext(Dispatchers.IO) {
        val archive = readAssetBytes("wwrando.tgz")
        val script = readAssetText("setup.sh")
        val hash = bundledHash()
        val localBridge = LoopbackBridge(archive)
        bridge = localBridge
        localBridge.start()
        val done = CompletableDeferred<ProgressEvent.Done>()
        val collector = scope.launch {
            localBridge.events.collect { event ->
                if (event is ProgressEvent.Done) done.complete(event) else onEvent(event)
            }
        }
        try {
            val command = "cat > '${RandoBridge.WWRANDO_DIR}/setup.sh' && " +
                "chmod +x '${RandoBridge.WWRANDO_DIR}/setup.sh' && " +
                "'${RandoBridge.WWRANDO_DIR}/setup.sh' ${localBridge.port} ${localBridge.token} $hash"
            val result = RandoCommandRunner.run(
                context = context,
                path = RandoBridge.SHELL,
                arguments = arrayOf("-c", command),
                stdin = script,
                workdir = RandoBridge.TERMUX_HOME,
                timeoutMs = SETUP_TIMEOUT_MS,
            )
            when {
                result == null -> ProgressEvent.Done(false, """{"ok":false,"error":"setup timed out"}""")
                !result.ok -> ProgressEvent.Done(
                    false,
                    """{"ok":false,"error":"exit ${result.exitCode}: ${result.stderr.takeLast(300)}"}""",
                )
                else -> withTimeoutOrNull(DONE_TIMEOUT_MS) { done.await() }
                    ?: ProgressEvent.Done(false, """{"ok":false,"error":"no final status from setup"}""")
            }
        } finally {
            collector.cancel()
            localBridge.close()
            if (bridge === localBridge) bridge = null
        }
    }

    /** Runs android_run.py in the installed venv; [seed] blank means autoseed. */
    suspend fun runDryRun(seed: String?, onEvent: (ProgressEvent) -> Unit): ProgressEvent.Done = withContext(Dispatchers.IO) {
        if (!isSetupCurrent()) {
            return@withContext ProgressEvent.Done(false, """{"ok":false,"error":"run setup first"}""")
        }
        val archive = readAssetBytes("wwrando.tgz")
        val localBridge = LoopbackBridge(archive)
        bridge = localBridge
        localBridge.start()
        val done = CompletableDeferred<ProgressEvent.Done>()
        val collector = scope.launch {
            localBridge.events.collect { event ->
                if (event is ProgressEvent.Done) done.complete(event) else onEvent(event)
            }
        }
        try {
            val arguments = buildList {
                add(RandoBridge.ANDROID_RUN)
                add("--port"); add(localBridge.port.toString())
                add("--token"); add(localBridge.token)
                add("--dry")
                add("--output-folder"); add(RandoBridge.OUTPUT_DIR)
                if (seed.isNullOrBlank()) {
                    add("--autoseed")
                } else {
                    add("--seed"); add(seed)
                }
            }
            val result = RandoCommandRunner.run(
                context = context,
                path = RandoBridge.VENV_PYTHON,
                arguments = arguments.toTypedArray(),
                workdir = RandoBridge.WWRANDO_DIR,
                timeoutMs = RUN_TIMEOUT_MS,
            )
            when {
                result == null -> ProgressEvent.Done(false, """{"ok":false,"error":"dry run timed out"}""")
                !result.ok -> ProgressEvent.Done(
                    false,
                    """{"ok":false,"error":"exit ${result.exitCode}: ${result.stderr.takeLast(300)}"}""",
                )
                else -> withTimeoutOrNull(DONE_TIMEOUT_MS) { done.await() }
                    ?: ProgressEvent.Done(false, """{"ok":false,"error":"no final status from run"}""")
            }
        } finally {
            collector.cancel()
            localBridge.close()
            if (bridge === localBridge) bridge = null
        }
    }

    /** Kills a running android_run.py and closes the bridge. Best-effort. */
    suspend fun cancel() {
        closeBridge()
        RandoCommandRunner.run(
            context = context,
            path = RandoBridge.SHELL,
            arguments = arrayOf("-c", "pkill -f android_run.py || true"),
            workdir = RandoBridge.TERMUX_HOME,
            timeoutMs = CANCEL_TIMEOUT_MS,
        )
    }

    private fun readAssetText(path: String): String =
        context.assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }

    private fun readAssetBytes(path: String): ByteArray =
        context.assets.open(path).use { it.readBytes() }

    companion object {
        private const val SETUP_TIMEOUT_MS = 20 * 60_000L
        private const val RUN_TIMEOUT_MS = 30 * 60_000L
        private const val DONE_TIMEOUT_MS = 20_000L
        private const val CANCEL_TIMEOUT_MS = 15_000L
    }
}
