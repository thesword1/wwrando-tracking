package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OutputsLogicTest {

    @Test
    fun `labels spoiler and non-spoiler logs`() {
        assertEquals("Spoiler log", OutputsLogic.logLabel("WW Random abc - Spoiler Log.txt"))
        assertEquals("Non-spoiler log", OutputsLogic.logLabel("WW Random abc - Non-Spoiler Log.txt"))
        assertEquals("readme.txt", OutputsLogic.logLabel("readme.txt"))
    }

    @Test
    fun `picks iso logs and meta from a child list`() {
        val children = listOf(
            ChildEntry("d1", "WW Random abc - Spoiler Log.txt", 1234, "text/plain"),
            ChildEntry("d2", "WW Random abc.iso", 1_450_000_000, "application/octet-stream"),
            ChildEntry("d3", "WW Random abc - Non-Spoiler Log.txt", 999, "text/plain"),
            ChildEntry("d4", "wwrando-run.json", 200, "application/json"),
        )
        assertEquals("d2", OutputsLogic.pickIso(children)?.documentId)
        assertEquals(listOf("d1", "d3"), OutputsLogic.pickLogs(children).map { it.documentId })
        assertEquals("d4", OutputsLogic.findMetaEntry(children)?.documentId)
    }

    @Test
    fun `iso match is case-insensitive`() {
        val children = listOf(ChildEntry("d1", "game.ISO", 10, null))
        assertEquals("d1", OutputsLogic.pickIso(children)?.documentId)
    }

    @Test
    fun `parses meta with missing and extra fields`() {
        val full = OutputsLogic.parseRunMeta(
            """{"seed":"s","seed_hash":"h","permalink":"p","tracker":true,"created":"2026-11-24T10:00:00","app_commit":"abc","extra":1}""",
        )
        assertEquals("s", full?.seed)
        assertEquals("h", full?.seedHash)
        assertEquals("p", full?.permalink)
        assertTrue(full?.tracker == true)
        assertEquals("abc", full?.appCommit)

        val missing = OutputsLogic.parseRunMeta("""{"seed":"s"}""")
        assertEquals("s", missing?.seed)
        assertEquals("", missing?.seedHash)
        assertFalse(missing?.tracker == true)
        assertNull(OutputsLogic.parseRunMeta("not json"))
    }

    @Test
    fun `sorts newest first by created then modified`() {
        val older = RunMeta(created = "2026-11-24T09:00:00")
        val newer = RunMeta(created = "2026-11-24T11:00:00")
        assertTrue(OutputsLogic.newestFirstKey(newer, 0L) > OutputsLogic.newestFirstKey(older, 0L))

        // Blank or unparseable created falls back to the folder's last-modified time.
        assertEquals(42L, OutputsLogic.newestFirstKey(RunMeta(created = ""), 42L))
        assertEquals(42L, OutputsLogic.newestFirstKey(RunMeta(created = "not-a-date"), 42L))
    }

    @Test
    fun `created is a parseable local iso timestamp`() {
        assertTrue(OutputsLogic.parseCreatedEpochMillis(OutputsLogic.nowLocalIso()) != null)
    }
}
