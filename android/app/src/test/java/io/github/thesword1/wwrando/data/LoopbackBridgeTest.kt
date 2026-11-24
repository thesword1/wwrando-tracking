package io.github.thesword1.wwrando.data

import java.net.HttpURLConnection
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
    fun `parser handles malformed lines`() {
        assertNull(ProgressLineParser.parseLine(""))
        assertNull(ProgressLineParser.parseLine("   "))
        assertNull(ProgressLineParser.parseLine("hello"))
        assertNull(ProgressLineParser.parseLine("PROGRESS abc/def x"))
        assertNull(ProgressLineParser.parseLine("STEP 1 x"))
        assertNull(ProgressLineParser.parseLine("STEP /5 label"))
        assertNull(ProgressLineParser.parseLine("PROGRESS 1/ x"))
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
}
