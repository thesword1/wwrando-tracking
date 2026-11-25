package io.github.thesword1.wwrando.data

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.FilterOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.Socket
import java.net.URL
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LoopbackBridgeTest {

    private val treeBytes = "randomizer tree bytes".toByteArray()

    @Test
    fun `rejects missing token`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            assertEquals(403, request(bridge.port, "GET", "/tree", token = null).first)
            assertEquals(403, request(bridge.port, "POST", "/progress", body = "x", token = null).first)
        }
    }

    @Test
    fun `rejects bad token`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val code = request(bridge.port, "GET", "/tree?t=${"0".repeat(32)}", token = null).first
            assertEquals(403, code)
        }
    }

    @Test
    fun `serves tree bytes intact`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val (code, body) = request(bridge.port, "GET", "/tree?t=${bridge.token}", token = null)
            assertEquals(200, code)
            assertArrayEquals(treeBytes, body)
        }
    }

    @Test
    fun `accepts token via header`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val (code, body) = request(bridge.port, "GET", "/tree", token = bridge.token)
            assertEquals(200, code)
            assertArrayEquals(treeBytes, body)
        }
    }

    @Test
    fun `serves iso bytes with correct content length`() {
        val isoBytes = "fake iso bytes".toByteArray()
        val bridge = LoopbackBridge(treeBytes, isoSource = FakeIsoSource(isoBytes))
        bridge.use {
            it.start()
            val (status, headers, body) = rawExchange(
                it.port,
                "GET /iso?t=${it.token} HTTP/1.1\r\nHost: localhost\r\n\r\n",
            )
            assertTrue(status.startsWith("HTTP/1.1 200"))
            assertEquals(isoBytes.size.toLong().toString(), headers["content-length"])
            assertArrayEquals(isoBytes, body)
        }
    }

    @Test
    fun `serves settings json from the provider`() {
        val body = """{"progression_tingle_chests":true}""".toByteArray()
        LoopbackBridge(treeBytes, settingsProvider = { body }).use { bridge ->
            bridge.start()
            val (code, received) = request(bridge.port, "GET", "/settings?t=${bridge.token}", token = null)
            assertEquals(200, code)
            assertArrayEquals(body, received)
        }
    }

    @Test
    fun `settings route is 404 without a provider`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val (code, _) = request(bridge.port, "GET", "/settings?t=${bridge.token}", token = null)
            assertEquals(404, code)
        }
    }

    @Test
    fun `output rejects bad name`() {
        val sink = FakeOutputSink()
        LoopbackBridge(treeBytes, outputSink = sink).use { bridge ->
            bridge.start()
            val (code, _) = request(
                bridge.port, "POST",
                "/output?t=${bridge.token}&name=..%2Fevil&dir=run", body = "x", token = null,
            )
            assertEquals(403, code)
        }
    }

    @Test
    fun `output rejects bad token`() {
        val sink = FakeOutputSink()
        LoopbackBridge(treeBytes, outputSink = sink).use { bridge ->
            bridge.start()
            val (code, _) = request(
                bridge.port, "POST",
                "/output?t=${"0".repeat(32)}&name=a.iso&dir=run", body = "x", token = null,
            )
            assertEquals(403, code)
        }
    }

    @Test
    fun `output writes body intact`() {
        val sink = FakeOutputSink()
        LoopbackBridge(treeBytes, outputSink = sink).use { bridge ->
            bridge.start()
            val body = "WW Random test.iso payload"
            val (code, _) = request(
                bridge.port, "POST",
                "/output?t=${bridge.token}&name=WW%20Random.iso&dir=run", body = body, token = null,
            )
            assertEquals(200, code)
            assertArrayEquals(body.toByteArray(), sink.files["run/WW Random.iso"])
        }
    }

    @Test
    fun `output deletes partial document on short body`() {
        val sink = FakeOutputSink()
        LoopbackBridge(treeBytes, outputSink = sink).use { bridge ->
            bridge.start()
            val response = rawShortBody(
                bridge.port,
                "POST /output?t=${bridge.token}&name=a.iso&dir=run HTTP/1.1\r\n" +
                    "Content-Length: 100\r\nHost: localhost\r\n\r\nshort",
            )
            assertTrue(response.startsWith("HTTP/1.1 500"))
            assertTrue(sink.deleted.contains("run/a.iso"))
        }
    }

    @Test
    fun `parses progress lines into events and drops malformed ones`() = runBlocking {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val received = mutableListOf<ProgressEvent>()
            val collector = launch(start = CoroutineStart.UNDISPATCHED) {
                bridge.events.collect { received += it }
            }
            val body = "STEP 1/5 Installing packages\n" +
                "PROGRESS 10/430 Randomizing...\n" +
                "   \n" +
                "garbage line\n" +
                "SKIP up-to-date\n"
            val (code, _) = request(bridge.port, "POST", "/progress?t=${bridge.token}", body = body, token = null)
            assertEquals(200, code)
            withTimeout(5_000) { while (received.size < 3) delay(10) }
            collector.cancel()

            assertEquals(ProgressEvent.Step(1, 5, "Installing packages"), received[0])
            assertEquals(ProgressEvent.Progress(10, 430, "Randomizing..."), received[1])
            assertEquals(ProgressEvent.Info("SKIP up-to-date"), received[2])
        }
    }

    @Test
    fun `parses done status`() = runBlocking {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val received = mutableListOf<ProgressEvent>()
            val collector = launch(start = CoroutineStart.UNDISPATCHED) {
                bridge.events.collect { received += it }
            }
            val body = """{"ok":true,"step":5,"hash":"abc"}"""
            val (code, _) = request(bridge.port, "POST", "/done?t=${bridge.token}", body = body, token = null)
            assertEquals(200, code)
            withTimeout(5_000) { while (received.isEmpty()) delay(10) }
            collector.cancel()

            val done = received.first() as ProgressEvent.Done
            assertTrue(done.ok)
            assertEquals(body, done.body)
        }
    }

    @Test
    fun `rejects oversized request line`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val longPath = "x".repeat(9 * 1024)
            val response = rawRequest(bridge.port, "GET /$longPath HTTP/1.1\r\nHost: localhost\r\n\r\n")
            assertTrue(response.startsWith("HTTP/1.1 400"))
        }
    }

    @Test
    fun `rejects too many headers`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val request = buildString {
                append("GET /tree?t=${bridge.token} HTTP/1.1\r\n")
                repeat(65) { append("X-H$it: v\r\n") }
                append("\r\n")
            }
            val response = rawRequest(bridge.port, request)
            assertTrue(response.startsWith("HTTP/1.1 400"))
        }
    }

    @Test
    fun `rejects oversized body`() {
        LoopbackBridge(treeBytes).use { bridge ->
            bridge.start()
            val request = "POST /progress?t=${bridge.token} HTTP/1.1\r\nContent-Length: 2000000\r\n\r\n"
            val response = rawRequest(bridge.port, request)
            assertTrue(response.startsWith("HTTP/1.1 413"))
        }
    }

    @Test
    fun `parser handles malformed lines`() {
        assertNull(ProgressLineParser.parseLine(""))
        assertNull(ProgressLineParser.parseLine("   "))
        assertNull(ProgressLineParser.parseLine("hello"))
        assertNull(ProgressLineParser.parseLine("PROGRESS abc/def x"))
        assertNull(ProgressLineParser.parseLine("STEP 1 x"))
        assertNull(ProgressLineParser.parseLine("STEP /5 label"))
        assertNull(ProgressLineParser.parseLine("PROGRESS 1/ x"))
    }

    private class FakeIsoSource(private val bytes: ByteArray) : IsoSource {
        override val size: Long = bytes.size.toLong()
        override fun openStream(): InputStream = ByteArrayInputStream(bytes)
    }

    private class FakeOutputSink : RunOutputSink {
        val files = LinkedHashMap<String, ByteArray>()
        val deleted = mutableListOf<String>()

        override fun open(subfolder: String, name: String): OutputStream {
            val buffer = ByteArrayOutputStream()
            val key = "$subfolder/$name"
            return object : FilterOutputStream(buffer) {
                override fun close() {
                    files[key] = buffer.toByteArray()
                }
            }
        }

        override fun delete(subfolder: String, name: String) {
            deleted += "$subfolder/$name"
        }

        override fun abort() = Unit

        override fun close() = Unit
    }

    private fun rawExchange(port: Int, request: String): Triple<String, Map<String, String>, ByteArray> =
        Socket("127.0.0.1", port).use { socket ->
            socket.soTimeout = 5_000
            socket.getOutputStream().write(request.toByteArray())
            socket.getOutputStream().flush()
            val bytes = socket.getInputStream().readBytes()
            val headerEnd = indexOfDoubleCrlf(bytes)
            val headerText = String(bytes, 0, headerEnd, Charsets.US_ASCII)
            val body = bytes.copyOfRange(headerEnd + 4, bytes.size)
            val lines = headerText.split("\r\n")
            val headers = HashMap<String, String>()
            lines.drop(1).forEach { line ->
                val idx = line.indexOf(':')
                if (idx > 0) headers[line.substring(0, idx).trim().lowercase()] = line.substring(idx + 1).trim()
            }
            Triple(lines.firstOrNull() ?: "", headers, body)
        }

    private fun indexOfDoubleCrlf(bytes: ByteArray): Int {
        for (i in 0 until bytes.size - 3) {
            if (bytes[i] == '\r'.code.toByte() && bytes[i + 1] == '\n'.code.toByte() &&
                bytes[i + 2] == '\r'.code.toByte() && bytes[i + 3] == '\n'.code.toByte()
            ) {
                return i
            }
        }
        return bytes.size
    }

    private fun rawShortBody(port: Int, request: String): String =
        Socket("127.0.0.1", port).use { socket ->
            socket.soTimeout = 5_000
            socket.getOutputStream().write(request.toByteArray())
            socket.getOutputStream().flush()
            socket.shutdownOutput()
            socket.getInputStream().bufferedReader().use { it.readText() }
        }

    private fun request(port: Int, method: String, path: String, body: String? = null, token: String? = null): Pair<Int, ByteArray> {
        val conn = URL("http://127.0.0.1:$port$path").openConnection() as HttpURLConnection
        conn.requestMethod = method
        conn.connectTimeout = 5_000
        conn.readTimeout = 10_000
        if (token != null) conn.setRequestProperty("X-Ww-Token", token)
        if (body != null) {
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "text/plain")
            conn.outputStream.use { it.write(body.toByteArray()) }
        }
        val code = conn.responseCode
        val bytes = (if (code in 200..299) conn.inputStream else conn.errorStream)?.use { it.readBytes() } ?: ByteArray(0)
        conn.disconnect()
        return code to bytes
    }

    private fun rawRequest(port: Int, request: String): String =
        Socket("127.0.0.1", port).use { socket ->
            socket.soTimeout = 5_000
            socket.getOutputStream().write(request.toByteArray())
            socket.getOutputStream().flush()
            socket.getInputStream().bufferedReader().use { it.readText() }
        }
}
