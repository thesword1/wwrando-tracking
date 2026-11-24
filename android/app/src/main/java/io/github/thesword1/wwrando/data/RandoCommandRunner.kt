package io.github.thesword1.wwrando.data

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Bundle
import androidx.core.content.ContextCompat
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.resume

/**
 * The Termux RUN_COMMAND plumbing shared by randomizer calls and first-run script installs: it sends
 * a command as a foreground service and resumes with the result bundle Termux delivers to a
 * PendingIntent. A copy of :app's TermuxCommandRunner, adapted for the randomizer module.
 */
object RandoCommandRunner {

    private val counter = AtomicInteger(0)

    /** Runs [path] [arguments] in Termux; [stdin] is fed to the command when set. Null on timeout. */
    suspend fun run(
        context: Context,
        path: String,
        arguments: Array<String>,
        stdin: String? = null,
        workdir: String = RandoBridge.TERMUX_HOME,
        timeoutMs: Long = 5 * 60_000L,
    ): RandoRunResult? = withTimeoutOrNull(timeoutMs) {
        runNow(context, path, arguments, stdin, workdir)
    }

    private suspend fun runNow(
        context: Context,
        path: String,
        arguments: Array<String>,
        stdin: String?,
        workdir: String,
    ): RandoRunResult = suspendCancellableCoroutine { cont ->
        val requestId = counter.incrementAndGet()
        val action = "${context.packageName}.RANDO_RESULT.$requestId"
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                runCatching { context.unregisterReceiver(this) }
                val bundle: Bundle? = intent.getBundleExtra(RESULT_BUNDLE)
                val stdout = bundle?.getString(RESULT_STDOUT).orEmpty()
                val stderr = bundle?.getString(RESULT_STDERR).orEmpty()
                val exitCode = bundle?.getInt(RESULT_EXIT_CODE, -1) ?: -1
                val errMsg = bundle?.getString(RESULT_ERRMSG)?.takeIf { it.isNotBlank() }
                if (cont.isActive) cont.resume(RandoRunResult(exitCode, stdout, stderr, error = errMsg))
            }
        }
        ContextCompat.registerReceiver(context, receiver, IntentFilter(action), ContextCompat.RECEIVER_NOT_EXPORTED)
        cont.invokeOnCancellation { runCatching { context.unregisterReceiver(receiver) } }

        val callback = PendingIntent.getBroadcast(
            context, requestId,
            Intent(action).setPackage(context.packageName),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
        )
        val intent = Intent(ACTION_RUN_COMMAND).apply {
            component = ComponentName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE)
            putExtra(EXTRA_PATH, path)
            putExtra(EXTRA_ARGUMENTS, arguments)
            putExtra(EXTRA_WORKDIR, workdir)
            putExtra(EXTRA_BACKGROUND, true)
            putExtra(EXTRA_PENDING_INTENT, callback)
            if (stdin != null) putExtra(EXTRA_STDIN, stdin)
        }
        try {
            context.startForegroundService(intent)
        } catch (e: Exception) {
            runCatching { context.unregisterReceiver(receiver) }
            if (cont.isActive) cont.resume(
                RandoRunResult(-1, "", "", error = "Could not start Termux: ${e.message}")
            )
        }
    }

    const val TERMUX_PACKAGE = "com.termux"
    const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
    const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"

    const val EXTRA_PATH = "com.termux.RUN_COMMAND_PATH"
    const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
    const val EXTRA_STDIN = "com.termux.RUN_COMMAND_STDIN"
    const val EXTRA_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR"
    const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
    const val EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT"

    const val RESULT_BUNDLE = "result"
    const val RESULT_STDOUT = "stdout"
    const val RESULT_STDERR = "stderr"
    const val RESULT_EXIT_CODE = "exitCode"
    const val RESULT_ERRMSG = "errmsg"
}
