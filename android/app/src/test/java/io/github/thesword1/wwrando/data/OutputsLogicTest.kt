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
    fun `sort key prefers created then modified then folder timestamp`() {
        val created = OutputsLogic.parseCreatedEpochMillis("2026-11-24T20:07:10")!!
        val modified = OutputsLogic.parseCreatedEpochMillis("2026-11-24T19:00:00")!!
        val folderTs = OutputsLogic.parseFolderTimestampEpoch("hashA_20261124-185600")!!

        assertEquals(created, OutputsLogic.sortKey(RunMeta(created = "2026-11-24T20:07:10"), 0L, "hashA_20261124-185600"))
        assertEquals(modified, OutputsLogic.sortKey(null, modified, "hashA_20261124-185600"))
        assertEquals(folderTs, OutputsLogic.sortKey(null, 0L, "hashA_20261124-185600"))
        assertTrue(folderTs > 0L)
        assertNull(OutputsLogic.parseFolderTimestampEpoch("no-timestamp"))
    }

    @Test
    fun `sorts mixed meta and no-meta entries newest first`() {
        val oldest = OutputEntry("oldest", "hashA_20261124-185600", modified = 0L, meta = null)
        val middle = OutputEntry("middle", "hashB_20261124-185800", modified = 0L, meta = null)
        val newestLegacy = OutputEntry("newestLegacy", "hashC_20261124-191800", modified = 0L, meta = null)
        val newRun = OutputEntry("newRun", "hashD_20261124-200700", modified = 0L, meta = RunMeta(created = "2026-11-24T20:07:10"))

        val sorted = OutputsLogic.sortNewestFirst(listOf(oldest, newRun, middle, newestLegacy))
        assertEquals(listOf("newRun", "newestLegacy", "middle", "oldest"), sorted.map { it.id })
    }

    @Test
    fun `oldest to delete keeps the newest folder`() {
        val entries = listOf(
            OutputEntry("oldest", "hashA_20261124-185600", 0L, null),
            OutputEntry("newRun", "hashB_20261124-200700", 0L, RunMeta(created = "2026-11-24T20:07:10")),
            OutputEntry("middle", "hashC_20261124-185800", 0L, null),
        )
        assertEquals(listOf("middle", "oldest"), OutputsLogic.oldestToDelete(entries, keep = 1).map { it.id })
    }

    @Test
    fun `created is a parseable local iso timestamp`() {
        assertTrue(OutputsLogic.parseCreatedEpochMillis(OutputsLogic.nowLocalIso()) != null)
    }
}
