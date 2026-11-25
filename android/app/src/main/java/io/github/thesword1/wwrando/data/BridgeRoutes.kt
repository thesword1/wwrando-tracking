package io.github.thesword1.wwrando.data

import java.io.Closeable
import java.io.InputStream
import java.io.OutputStream
import java.net.URLDecoder

/** Streams the user-picked ISO to the loopback bridge without loading it into memory. */
interface IsoSource {
    val size: Long
    fun openStream(): InputStream
}

/**
 * Writes uploaded output files into a per-run subfolder of the user's SAF tree. The app implements
 * this with DocumentsContract; unit tests use an in-memory fake so no ContentResolver is needed.
 */
interface RunOutputSink : Closeable {
    /** Opens [name] in [subfolder] for writing, creating the subfolder on first use. */
    fun open(subfolder: String, name: String): OutputStream

    /** Deletes a partially-written document after a short body or I/O error. */
    fun delete(subfolder: String, name: String)

    /** Called on cancel: removes the in-progress document and this run's subfolder. */
    fun abort()

    /** Writes a small metadata JSON into the run's subfolder; failures are ignored by callers. */
    fun writeMeta(json: String) {}
}

/**
 * Route handlers for the real-run endpoints (GET /iso, POST /output), kept out of LoopbackBridge so
 * both stay small. Pure JVM code: only java.io/java.net types, no Android framework.
 */
object BridgeRoutes {
    private val OUTPUT_NAME = Regex("^[A-Za-z0-9._ -]{1,128}$")
    private const val COPY_BUFFER = 64 * 1024

    fun isValidOutputName(name: String): Boolean =
        OUTPUT_NAME.matches(name) && name.trim('.', ' ').isNotEmpty()

    /** Decodes a URL-encoded query value (run.sh encodes filenames with spaces, etc.). */
    fun urlDecode(value: String): String = URLDecoder.decode(value, Charsets.UTF_8.name())

    /** Streams the whole ISO into [output]. The caller has already written the headers. */
    fun writeIso(source: IsoSource, output: OutputStream) {
        val buffer = ByteArray(COPY_BUFFER)
        source.openStream().use { stream ->
            while (true) {
                val n = stream.read(buffer)
                if (n == -1) break
                output.write(buffer, 0, n)
            }
        }
        output.flush()
    }

    /**
     * Streams the request body into [sink]. Returns 200 on a complete body, 411 when the client sent
     * no Content-Length, and 500 (after deleting the partial document) on a short body or I/O error.
     */
    fun writeOutput(
        input: InputStream,
        contentLength: Long?,
        subfolder: String,
        name: String,
        sink: RunOutputSink,
    ): Int {
        if (contentLength == null || contentLength < 0) return 411
        val document = try {
            sink.open(subfolder, name)
        } catch (_: Exception) {
            return 500
        }
        var ok = false
        try {
            val buffer = ByteArray(COPY_BUFFER)
            var written = 0L
            while (written < contentLength) {
                val want = minOf(buffer.size.toLong(), contentLength - written).toInt()
                val n = input.read(buffer, 0, want)
                if (n == -1) break
                document.write(buffer, 0, n)
                written += n
            }
            if (written == contentLength) {
                document.flush()
                ok = true
            }
        } catch (_: Exception) {
            ok = false
        } finally {
            runCatching { document.close() }
            if (!ok) runCatching { sink.delete(subfolder, name) }
        }
        return if (ok) 200 else 500
    }
}
