package io.github.thesword1.wwrando.data

import android.content.Context
import org.json.JSONObject

/**
 * Runs android_run.py's permalink-only modes in Termux through [RandoCommandRunner]. Both modes
 * read one JSON object on stdin and print one JSON line on stdout; the caller parses the result.
 */
object PermalinkRunner {

    private const val TIMEOUT_MS = 60_000L

    suspend fun encode(context: Context, seed: String, settings: Map<String, Any>): PermalinkResult {
        val payload = JSONObject().apply {
            put("seed", seed)
            put("settings", JSONObject(settings))
        }
        return run(context, "--encode-permalink", payload)
    }

    suspend fun decode(context: Context, permalink: String): PermalinkResult {
        val payload = JSONObject().put("permalink", permalink)
        return run(context, "--decode-permalink", payload)
    }

    private suspend fun run(context: Context, mode: String, payload: JSONObject): PermalinkResult {
        val result = RandoCommandRunner.run(
            context = context,
            path = RandoBridge.VENV_PYTHON,
            arguments = arrayOf(RandoBridge.ANDROID_RUN, mode),
            stdin = payload.toString(),
            workdir = RandoBridge.WWRANDO_DIR,
            timeoutMs = TIMEOUT_MS,
        )
        val parsed = result?.stdout?.let(AdvancedLogic::parseResult)
        return when {
            result == null -> PermalinkResult(ok = false, error = "Permalink command timed out")
            parsed != null -> parsed
            !result.ok -> PermalinkResult(
                ok = false,
                error = "exit ${result.exitCode}: ${result.stderr.takeLast(300)}",
            )
            else -> PermalinkResult(ok = false, error = "No JSON result from permalink command")
        }
    }
}
