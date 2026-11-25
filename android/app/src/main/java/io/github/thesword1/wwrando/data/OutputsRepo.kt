package io.github.thesword1.wwrando.data

import android.content.ContentResolver
import android.net.Uri
import android.provider.DocumentsContract
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** One viewable log file inside a seed folder. */
data class LogFile(val uri: Uri, val name: String, val label: String)

/** Metadata written into `wwrando-run.json` after a successful run. */
data class RunMeta(
    val seed: String = "",
    val seedHash: String = "",
    val permalink: String = "",
    val tracker: Boolean = false,
    val created: String = "",
    val appCommit: String = "",
)

/** One generated seed folder in the picked SAF output tree. */
data class SeedOutput(
    val folderUri: Uri,
    val folderName: String,
    val isoUri: Uri?,
    val isoSize: Long,
    val logs: List<LogFile>,
    val meta: RunMeta?,
    val modified: Long,
) {
    val title: String get() = meta?.seedHash?.takeIf { it.isNotBlank() } ?: folderName
}

/**
 * A SAF document child reduced to the fields the pure selection logic needs. documentId is a plain
 * string (the tree-relative id) so the selection rules stay unit-testable without a ContentResolver.
 */
data class ChildEntry(
    val documentId: String,
    val name: String,
    val size: Long,
    val mimeType: String?,
)

/** Pure selection/formatting rules for the outputs list (unit-testable, no Android deps). */
object OutputsLogic {
    const val META_FILE_NAME = "wwrando-run.json"

    private val CREATED_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss")
    private val DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")

    fun isIso(name: String): Boolean = name.lowercase().endsWith(".iso")
    fun isLog(name: String): Boolean = name.lowercase().endsWith(".txt")

    fun logLabel(name: String): String = when {
        name.contains("- Spoiler Log") -> "Spoiler log"
        name.contains("Non-Spoiler") -> "Non-spoiler log"
        else -> name
    }

    fun pickIso(children: List<ChildEntry>): ChildEntry? = children.firstOrNull { isIso(it.name) }

    fun pickLogs(children: List<ChildEntry>): List<ChildEntry> = children.filter { isLog(it.name) }

    fun findMetaEntry(children: List<ChildEntry>): ChildEntry? =
        children.firstOrNull { it.name.equals(META_FILE_NAME, ignoreCase = true) }

    /**
     * Missing/extra fields are tolerated; malformed JSON yields null. Parsed without org.json so the
     * unit test can run on the JVM (the android.jar org.json stubs are not mocked there).
     */
    fun parseRunMeta(json: String): RunMeta? {
        if (!json.contains("\"seed\"")) return null
        return RunMeta(
            seed = extractString(json, "seed") ?: "",
            seedHash = extractString(json, "seed_hash") ?: "",
            permalink = extractString(json, "permalink") ?: "",
            tracker = extractBool(json, "tracker") ?: false,
            created = extractString(json, "created") ?: "",
            appCommit = extractString(json, "app_commit") ?: "",
        )
    }

    private fun extractString(json: String, key: String): String? {
        val regex = Regex("\"${Regex.escape(key)}\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"")
        return regex.find(json)?.groupValues?.get(1)?.let { unescape(it) }
    }

    private fun extractBool(json: String, key: String): Boolean? {
        val regex = Regex("\"${Regex.escape(key)}\"\\s*:\\s*(true|false)")
        return regex.find(json)?.groupValues?.get(1)?.toBoolean()
    }

    private fun unescape(value: String): String {
        val out = StringBuilder(value.length)
        var i = 0
        while (i < value.length) {
            val c = value[i]
            if (c != '\\' || i + 1 >= value.length) {
                out.append(c)
                i++
                continue
            }
            val next = value[i + 1]
            when (next) {
                'n' -> { out.append('\n'); i += 2 }
                't' -> { out.append('\t'); i += 2 }
                'r' -> { out.append('\r'); i += 2 }
                'b' -> { out.append('\b'); i += 2 }
                'f' -> { out.append('\u000C'); i += 2 }
                'u' -> {
                    val hex = if (i + 5 < value.length) runCatching { value.substring(i + 2, i + 6).toInt(16) }.getOrNull() else null
                    if (hex != null) {
                        out.append(hex.toChar())
                        i += 6
                    } else {
                        out.append('u')
                        i += 2
                    }
                }
                else -> { out.append(next); i += 2 }
            }
        }
        return out.toString()
    }

    /** Sort key: metadata creation time when parseable, otherwise the folder's last-modified time. */
    fun newestFirstKey(meta: RunMeta?, modified: Long): Long = parseCreatedEpochMillis(meta?.created) ?: modified

    fun sortNewestFirst(outputs: List<SeedOutput>): List<SeedOutput> =
        outputs.sortedByDescending { newestFirstKey(it.meta, it.modified) }

    fun parseCreatedEpochMillis(created: String?): Long? {
        if (created.isNullOrBlank()) return null
        return runCatching {
            LocalDateTime.parse(created, CREATED_FORMATTER)
                .atZone(ZoneId.systemDefault())
                .toInstant()
                .toEpochMilli()
        }.getOrNull()
    }

    fun nowLocalIso(): String = LocalDateTime.now().format(CREATED_FORMATTER)

    fun formatOutputDate(meta: RunMeta?, modified: Long): String {
        meta?.created?.takeIf { it.isNotBlank() }?.let { created ->
            runCatching { LocalDateTime.parse(created, CREATED_FORMATTER).format(DATE_FORMATTER) }
                .getOrNull()?.let { return it }
        }
        return Instant.ofEpochMilli(modified).atZone(ZoneId.systemDefault()).toLocalDateTime().format(DATE_FORMATTER)
    }

    fun formatIsoSizeMb(bytes: Long): String = "%.1f MB".format(bytes / (1024.0 * 1024.0))
}

/**
 * Pure SAF repository for the generated-seed list. No database: every call queries the picked tree
 * through DocumentsContract on [Dispatchers.IO] and returns a Result so a revoked grant or provider
 * error is a failure value, never a crash.
 */
class OutputsRepo(private val resolver: ContentResolver) {

    suspend fun list(treeUri: Uri): Result<List<SeedOutput>> = withContext(Dispatchers.IO) {
        runCatching { listInternal(treeUri) }
    }

    suspend fun readText(uri: Uri, maxBytes: Int = DEFAULT_MAX_BYTES): Result<String> =
        withContext(Dispatchers.IO) { runCatching { readTextInternal(uri, maxBytes) } }

    suspend fun delete(folderUri: Uri): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            if (!DocumentsContract.deleteDocument(resolver, folderUri)) {
                throw IOException("deleteDocument returned false")
            }
        }
    }

    suspend fun deleteOlderThanNewest(treeUri: Uri, keep: Int = 1): Result<Int> =
        withContext(Dispatchers.IO) {
            runCatching {
                val sorted = OutputsLogic.sortNewestFirst(listInternal(treeUri))
                var deleted = 0
                for (output in sorted.drop(keep)) {
                    if (DocumentsContract.deleteDocument(resolver, output.folderUri)) deleted++
                }
                deleted
            }
        }

    private fun listInternal(treeUri: Uri): List<SeedOutput> {
        val treeDocId = DocumentsContract.getTreeDocumentId(treeUri)
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, treeDocId)
        return queryChildren(childrenUri)
            .filter { it.mimeType == DocumentsContract.Document.MIME_TYPE_DIR }
            .mapNotNull { folder -> buildSeedOutput(treeUri, folder) }
    }

    private fun buildSeedOutput(treeUri: Uri, folder: ChildRecord): SeedOutput? {
        val folderUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, folder.documentId)
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, folder.documentId)
        val children = queryChildren(childrenUri).map { ChildEntry(it.documentId, it.name, it.size, it.mimeType) }

        val iso = OutputsLogic.pickIso(children)
        val logs = OutputsLogic.pickLogs(children)
        // Folders with neither an ISO nor logs are skipped (old or unrelated directories).
        if (iso == null && logs.isEmpty()) return null

        val meta = OutputsLogic.findMetaEntry(children)?.let { entry ->
            val metaUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, entry.documentId)
            runCatching { readTextInternal(metaUri, META_MAX_BYTES) }
                .getOrNull()
                ?.let(OutputsLogic::parseRunMeta)
        }

        return SeedOutput(
            folderUri = folderUri,
            folderName = folder.name,
            isoUri = iso?.let { DocumentsContract.buildDocumentUriUsingTree(treeUri, it.documentId) },
            isoSize = iso?.size ?: 0L,
            logs = logs.map { entry ->
                LogFile(
                    uri = DocumentsContract.buildDocumentUriUsingTree(treeUri, entry.documentId),
                    name = entry.name,
                    label = OutputsLogic.logLabel(entry.name),
                )
            },
            meta = meta,
            modified = folder.modified,
        )
    }

    private fun queryChildren(uri: Uri): List<ChildRecord> {
        val records = mutableListOf<ChildRecord>()
        resolver.query(uri, PROJECTION, null, null, null)?.use { cursor ->
            while (cursor.moveToNext()) {
                val docId = cursor.getString(0) ?: continue
                records += ChildRecord(
                    documentId = docId,
                    name = cursor.getString(1) ?: docId,
                    mimeType = cursor.getString(2),
                    size = if (cursor.isNull(3)) 0L else cursor.getLong(3),
                    modified = if (cursor.isNull(4)) 0L else cursor.getLong(4),
                )
            }
        }
        return records
    }

    private fun readTextInternal(uri: Uri, maxBytes: Int): String {
        val input = resolver.openInputStream(uri) ?: throw IOException("cannot open document")
        input.use { stream ->
            val buffer = ByteArray(minOf(READ_BUFFER, maxBytes))
            val out = ByteArrayOutputStream(minOf(maxBytes, 1 shl 20).coerceAtLeast(256))
            var total = 0
            while (total < maxBytes) {
                val want = minOf(buffer.size, maxBytes - total)
                val n = stream.read(buffer, 0, want)
                if (n == -1) break
                out.write(buffer, 0, n)
                total += n
            }
            val truncated = stream.read() != -1
            val text = String(out.toByteArray(), Charsets.UTF_8)
            return if (truncated) text + TRUNCATION_NOTE else text
        }
    }

    private data class ChildRecord(
        val documentId: String,
        val name: String,
        val mimeType: String?,
        val size: Long,
        val modified: Long,
    )

    private companion object {
        val PROJECTION = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_LAST_MODIFIED,
        )
        const val DEFAULT_MAX_BYTES = 2 * 1024 * 1024
        const val META_MAX_BYTES = 64 * 1024
        const val READ_BUFFER = 64 * 1024
        const val TRUNCATION_NOTE = "\n\n[... truncated ...]"
    }
}
