package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import org.json.JSONObject

/** One finished run (success or failure; cancels are never recorded). */
data class HistoryEntry(
    val time: Long,
    val ok: Boolean,
    val seed: String,
    val seedHash: String,
    val permalink: String,
    val preset: String,
    val modified: Boolean,
    val error: String,
    val folder: String,
)

/** Pure serialization/capping rules for the run history (unit-testable, no Android types). */
object HistoryLogic {
    const val MAX_ENTRIES = 100

    fun toJson(entry: HistoryEntry): String = JSONObject()
        .put("time", entry.time)
        .put("ok", entry.ok)
        .put("seed", entry.seed)
        .put("seed_hash", entry.seedHash)
        .put("permalink", entry.permalink)
        .put("preset", entry.preset)
        .put("modified", entry.modified)
        .put("error", entry.error)
        .put("folder", entry.folder)
        .toString()

    /** Parses one JSONL line. Returns null for blank or malformed lines (never throws). */
    fun parseLine(line: String): HistoryEntry? {
        if (line.isBlank()) return null
        val json = runCatching { JSONObject(line) }.getOrNull() ?: return null
        if (!json.has("time")) return null
        return HistoryEntry(
            time = json.optLong("time", 0L),
            ok = json.optBoolean("ok", false),
            seed = json.optString("seed", ""),
            seedHash = json.optString("seed_hash", ""),
            permalink = json.optString("permalink", ""),
            preset = json.optString("preset", ""),
            modified = json.optBoolean("modified", false),
            error = json.optString("error", ""),
            folder = json.optString("folder", ""),
        )
    }

    fun sortNewestFirst(entries: List<HistoryEntry>): List<HistoryEntry> =
        entries.sortedByDescending { it.time }

    /** Newest [MAX_ENTRIES] entries (the oldest are dropped). */
    fun cap(entries: List<HistoryEntry>): List<HistoryEntry> =
        sortNewestFirst(entries).take(MAX_ENTRIES)
}

/** Appends finished runs to `filesDir/history.jsonl`, capped at [HistoryLogic.MAX_ENTRIES]. */
class HistoryStore(context: Context) {
    private val file = File(context.applicationContext.filesDir, "history.jsonl")

    fun list(): List<HistoryEntry> {
        if (!file.isFile) return emptyList()
        val entries = file.readLines().mapNotNull { HistoryLogic.parseLine(it) }
        return HistoryLogic.sortNewestFirst(entries)
    }

    fun append(entry: HistoryEntry) {
        writeAll(HistoryLogic.cap(list() + entry))
    }

    fun clear() {
        file.delete()
    }

    private fun writeAll(entries: List<HistoryEntry>) {
        file.writeText(entries.joinToString("\n") { HistoryLogic.toJson(it) } + "\n", Charsets.UTF_8)
    }
}
