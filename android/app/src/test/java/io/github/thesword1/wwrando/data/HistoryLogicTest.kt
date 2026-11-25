package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HistoryLogicTest {

    private fun entry(time: Long, ok: Boolean = true, permalink: String = "") = HistoryEntry(
        time = time,
        ok = ok,
        seed = "seed",
        seedHash = "hash",
        permalink = permalink,
        preset = "Default",
        modified = false,
        error = "",
        folder = "folder",
    )

    @Test
    fun `parses a valid line and skips malformed lines`() {
        val line = HistoryLogic.toJson(entry(100L, permalink = "QUJDRA=="))
        val parsed = HistoryLogic.parseLine(line)
        assertEquals(100L, parsed?.time)
        assertEquals("hash", parsed?.seedHash)
        assertEquals("QUJDRA==", parsed?.permalink)

        assertNull(HistoryLogic.parseLine(""))
        assertNull(HistoryLogic.parseLine("   "))
        assertNull(HistoryLogic.parseLine("not json"))
        // A valid JSON object without a time is not a history record.
        assertNull(HistoryLogic.parseLine("""{"ok":true}"""))
    }

    @Test
    fun `sorts newest first`() {
        val older = entry(1L)
        val newer = entry(2L)
        assertEquals(listOf(newer, older), HistoryLogic.sortNewestFirst(listOf(older, newer)))
    }

    @Test
    fun `caps at 100 keeping the newest entries`() {
        val entries = (0 until 150).map { entry(it.toLong()) }
        val capped = HistoryLogic.cap(entries)
        assertEquals(HistoryLogic.MAX_ENTRIES, capped.size)
        assertEquals(149L, capped.first().time)
        assertEquals(50L, capped.last().time)
        assertTrue(capped.all { it.time >= 50L })
    }
}
