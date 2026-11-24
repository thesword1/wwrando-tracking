package io.github.thesword1.wwrando.data

/**
 * Events streamed by the loopback bridge while a Termux job runs. setup.sh emits [Step] (and
 * [Info] for "SKIP up-to-date"); android_run.py emits [Progress]; both POST a final [Done].
 */
sealed interface ProgressEvent {
    data class Step(val index: Int, val total: Int, val label: String) : ProgressEvent
    data class Progress(val done: Int, val max: Int, val description: String) : ProgressEvent
    data class Info(val text: String) : ProgressEvent
    data class Done(val ok: Boolean, val body: String) : ProgressEvent
}

/** Pure parser for the bridge's text protocol so the Android unit tests can cover it without a device. */
object ProgressLineParser {
    private val STEP = Regex("""^STEP\s+(\d+)/(\d+)\s+(.*)$""")
    private val PROGRESS = Regex("""^PROGRESS\s+(\d+)/(\d+)\s*(.*)$""")
    private val DONE_OK = Regex(""""ok"\s*:\s*(true|false)""")

    /** Parses one progress-line. Returns null for blank or malformed lines (never throws). */
    fun parseLine(line: String): ProgressEvent? {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) return null
        STEP.matchEntire(trimmed)?.let { m ->
            return ProgressEvent.Step(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3])
        }
        PROGRESS.matchEntire(trimmed)?.let { m ->
            return ProgressEvent.Progress(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3])
        }
        if (trimmed.startsWith("SKIP ")) return ProgressEvent.Info(trimmed)
        return null
    }

    /** Extracts the ok flag from a /done JSON body (the rest of the body is kept for the log/result). */
    fun parseDone(body: String): ProgressEvent.Done {
        val ok = DONE_OK.find(body)?.groupValues?.get(1) == "true"
        return ProgressEvent.Done(ok, body)
    }
}
