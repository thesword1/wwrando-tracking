package io.github.thesword1.wwrando.data

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.SocketTimeoutException
import java.security.MessageDigest
import java.security.SecureRandom
import kotlin.concurrent.thread
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

/** Signals a request that exceeds the line/header limits and should be answered with 400. */
private class BadRequestException : Exception()

/**
 * Loopback HTTP server that hands Termux the bundled source archive and receives progress/status
 * without any shared storage. It binds to 127.0.0.1 on a random port and requires a random token on
 * every request (?t=... or X-Ww-Token). Only reachable from on-device processes (see the INTERNET
 * permission note in the manifest).
 */
class LoopbackBridge(
    private val treeBytes: ByteArray,
    private val isoSource: IsoSource? = null,
    private val outputSink: RunOutputSink? = null,
) : Closeable {

    private val serverSocket = ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))
    val port: Int get() = serverSocket.localPort
    val token: String = randomHex(32)

    private val _events = MutableSharedFlow<ProgressEvent>(extraBufferCapacity = 256)
    val events: SharedFlow<ProgressEvent> = _events

    @Volatile
    private var running = false

    fun start() {
        if (running) return
        running = true
        thread(name = "wwrando-loopback", isDaemon = true) { acceptLoop() }
    }

    private fun acceptLoop() {
        while (running && !serverSocket.isClosed) {
            val socket = try {
                serverSocket.accept()
            } catch (_: SocketException) {
                break
            }
            try {
                handle(socket)
            } catch (_: Exception) {
                // A single malformed request must not take down the bridge.
            } finally {
                runCatching { socket.close() }
            }
        }
    }

    private fun handle(socket: Socket) {
        socket.soTimeout = SOCKET_TIMEOUT_MS
        val input = BufferedInputStream(socket.getInputStream())
        val output = BufferedOutputStream(socket.getOutputStream())
        try {
            handleRequest(input, output)
        } catch (_: BadRequestException) {
            writeStatus(output, 400, "Bad Request")
        } catch (_: SocketTimeoutException) {
            // Idle or slow client: drop the connection.
        }
    }

    private fun handleRequest(input: InputStream, output: OutputStream) {
        val requestLine = readLine(input) ?: return
        val parts = requestLine.split(" ")
        if (parts.size < 3) throw BadRequestException()
        val method = parts[0]
        val target = parts[1]

        val headers = HashMap<String, String>()
        var headerCount = 0
        while (true) {
            val line = readLine(input) ?: break
            if (line.isEmpty()) break
            if (++headerCount > MAX_HEADERS) throw BadRequestException()
            val colon = line.indexOf(':')
            if (colon > 0) headers[line.substring(0, colon).trim().lowercase()] = line.substring(colon + 1).trim()
        }

        val supplied = tokenFromTarget(target) ?: headers["x-ww-token"]
        if (supplied == null || !MessageDigest.isEqual(supplied.toByteArray(), token.toByteArray())) {
            writeStatus(output, 403, "Forbidden")
            return
        }

        if (headers["expect"]?.equals("100-continue", ignoreCase = true) == true) {
            output.write("HTTP/1.1 100 Continue\r\n\r\n".toByteArray())
            output.flush()
        }

        val path = target.substringBefore('?')
        val contentLength = headers["content-length"]?.toLongOrNull()
        when {
            method == "GET" && path == "/tree" -> writeTree(output)
            method == "GET" && path == "/iso" -> writeIso(output)
            method == "POST" && path == "/output" -> handleOutput(input, output, target, contentLength)
            method == "POST" && path == "/progress" -> handleProgress(input, output, contentLength)
            method == "POST" && path == "/done" -> handleDone(input, output, contentLength)
            else -> writeStatus(output, 404, "Not Found")
        }
    }

    private fun writeIso(output: OutputStream) {
        val source = isoSource
        if (source == null) {
            writeStatus(output, 404, "Not Found")
            return
        }
        val header = "HTTP/1.1 200 OK\r\n" +
            "Content-Type: application/octet-stream\r\n" +
            "Content-Length: ${source.size}\r\n" +
            "Connection: close\r\n\r\n"
        output.write(header.toByteArray())
        output.flush()
        BridgeRoutes.writeIso(source, output)
    }

    private fun handleOutput(input: InputStream, output: OutputStream, target: String, contentLength: Long?) {
        val sink = outputSink
        if (sink == null) {
            writeStatus(output, 404, "Not Found")
            return
        }
        val name = queryParam(target, "name")?.let { BridgeRoutes.urlDecode(it) }
        val subfolder = queryParam(target, "dir")?.let { BridgeRoutes.urlDecode(it) }
        if (name == null || subfolder == null) {
            writeStatus(output, 400, "Bad Request")
            return
        }
        if (!BridgeRoutes.isValidOutputName(name) || !BridgeRoutes.isValidOutputName(subfolder)) {
            writeStatus(output, 403, "Forbidden")
            return
        }
        if (contentLength == null) {
            writeStatus(output, 411, "Length Required")
            return
        }
        val code = BridgeRoutes.writeOutput(input, contentLength, subfolder, name, sink)
        writeStatus(output, code, if (code == 200) "OK" else "Internal Server Error")
    }

    private fun handleProgress(input: InputStream, output: OutputStream, contentLength: Long?) {
        val body = readLimitedBody(input, output, contentLength) ?: return
        body.decodeToString().lineSequence().forEach { line ->
            ProgressLineParser.parseLine(line)?.let { _events.tryEmit(it) }
        }
        writeStatus(output, 200, "OK")
    }

    private fun handleDone(input: InputStream, output: OutputStream, contentLength: Long?) {
        val body = readLimitedBody(input, output, contentLength) ?: return
        _events.tryEmit(ProgressLineParser.parseDone(body.decodeToString()))
        writeStatus(output, 200, "OK")
    }

    /**
     * Reads a small body for /progress and /done, enforcing [MAX_BODY_BYTES]. On an oversized body it
     * writes the 413 response and returns null. The caller already handled the 100-continue exchange.
     */
    private fun readLimitedBody(input: InputStream, output: OutputStream, contentLength: Long?): ByteArray? {
        if (contentLength != null && contentLength > MAX_BODY_BYTES) {
            writeStatus(output, 413, "Payload Too Large")
            return null
        }
        return readBody(input, contentLength?.toInt())
    }

    private fun writeTree(output: OutputStream) {
        val header = "HTTP/1.1 200 OK\r\n" +
            "Content-Type: application/gzip\r\n" +
            "Content-Length: ${treeBytes.size}\r\n" +
            "Connection: close\r\n\r\n"
        output.write(header.toByteArray())
        output.write(treeBytes)
        output.flush()
    }

    private fun writeStatus(output: OutputStream, code: Int, reason: String) {
        output.write("HTTP/1.1 $code $reason\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
        output.flush()
    }

    override fun close() {
        running = false
        runCatching { serverSocket.close() }
    }

    companion object {
        private const val SOCKET_TIMEOUT_MS = 15_000
        private const val MAX_LINE_BYTES = 8 * 1024
        private const val MAX_HEADERS = 64
        private const val MAX_BODY_BYTES = 1024 * 1024

        private fun readLine(input: InputStream): String? {
            val bytes = StringBuilder()
            var count = 0
            while (true) {
                val b = input.read()
                if (b == -1) return if (bytes.isEmpty()) null else bytes.toString()
                if (b == '\n'.code) break
                if (b != '\r'.code) {
                    bytes.append(b.toChar())
                    if (++count > MAX_LINE_BYTES) throw BadRequestException()
                }
            }
            return bytes.toString()
        }

        private fun readBody(input: InputStream, contentLength: Int?): ByteArray {
            if (contentLength == null || contentLength <= 0) return ByteArray(0)
            val buffer = ByteArray(contentLength)
            var read = 0
            while (read < contentLength) {
                val n = input.read(buffer, read, contentLength - read)
                if (n == -1) break
                read += n
            }
            return buffer.copyOf(read)
        }

        private fun tokenFromTarget(target: String): String? = queryParam(target, "t")

        private fun queryParam(target: String, key: String): String? {
            val query = target.substringAfter('?', "")
            if (query.isEmpty()) return null
            return query.split('&').firstOrNull { it.startsWith("$key=") }?.removePrefix("$key=")
        }

        private fun randomHex(length: Int): String {
            val bytes = ByteArray(length / 2)
            SecureRandom().nextBytes(bytes)
            return bytes.joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
        }
    }
}
