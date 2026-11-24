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
import java.security.SecureRandom
import kotlin.concurrent.thread
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

/**
 * Loopback HTTP server that hands Termux the bundled source archive and receives progress/status
 * without any shared storage. It binds to 127.0.0.1 on a random port and requires a random token on
 * every request (?t=... or X-Ww-Token). Only reachable from on-device processes (see the INTERNET
 * permission note in the manifest).
 */
class LoopbackBridge(private val treeBytes: ByteArray) : Closeable {

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
        val input = BufferedInputStream(socket.getInputStream())
        val output = BufferedOutputStream(socket.getOutputStream())

        val requestLine = readLine(input) ?: return
        val parts = requestLine.split(" ")
        if (parts.size < 3) {
            writeStatus(output, 400, "Bad Request")
            return
        }
        val method = parts[0]
        val target = parts[1]

        val headers = HashMap<String, String>()
        while (true) {
            val line = readLine(input) ?: break
            if (line.isEmpty()) break
            val colon = line.indexOf(':')
            if (colon > 0) headers[line.substring(0, colon).trim().lowercase()] = line.substring(colon + 1).trim()
        }

        val queryToken = tokenFromTarget(target)
        if ((queryToken ?: headers["x-ww-token"]) != token) {
            writeStatus(output, 403, "Forbidden")
            return
        }

        if (headers["expect"]?.equals("100-continue", ignoreCase = true) == true) {
            output.write("HTTP/1.1 100 Continue\r\n\r\n".toByteArray())
            output.flush()
        }

        val path = target.substringBefore('?')
        val body = readBody(input, headers["content-length"]?.toIntOrNull())
        when {
            method == "GET" && path == "/tree" -> writeTree(output)
            method == "POST" && path == "/progress" -> {
                body?.decodeToString()?.lineSequence()?.forEach { line ->
                    ProgressLineParser.parseLine(line)?.let { _events.tryEmit(it) }
                }
                writeStatus(output, 200, "OK")
            }
            method == "POST" && path == "/done" -> {
                _events.tryEmit(ProgressLineParser.parseDone(body?.decodeToString().orEmpty()))
                writeStatus(output, 200, "OK")
            }
            else -> writeStatus(output, 404, "Not Found")
        }
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
        private fun readLine(input: InputStream): String? {
            val bytes = StringBuilder()
            while (true) {
                val b = input.read()
                if (b == -1) return if (bytes.isEmpty()) null else bytes.toString()
                if (b == '\n'.code) break
                if (b != '\r'.code) bytes.append(b.toChar())
            }
            return bytes.toString()
        }

        private fun readBody(input: InputStream, contentLength: Int?): ByteArray? {
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

        private fun tokenFromTarget(target: String): String? {
            val query = target.substringAfter('?', "")
            if (query.isEmpty()) return null
            return query.split('&').firstOrNull { it.startsWith("t=") }?.removePrefix("t=")
        }

        private fun randomHex(length: Int): String {
            val bytes = ByteArray(length / 2)
            SecureRandom().nextBytes(bytes)
            return bytes.joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
        }
    }
}
