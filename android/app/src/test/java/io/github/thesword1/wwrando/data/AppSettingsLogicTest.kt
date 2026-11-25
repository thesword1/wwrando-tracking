package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppSettingsLogicTest {

    @Test
    fun `tracker defaults to on`() {
        assertTrue(AppSettingsLogic.defaults().tracker)
        assertTrue(AppSettingsLogic.parse("").tracker)
        assertTrue(AppSettingsLogic.parse("not json").tracker)
    }

    @Test
    fun `tracker persists off and survives a round trip`() {
        val json = AppSettingsLogic.toJson(AppSettings(tracker = false))
        assertFalse(AppSettingsLogic.parse(json).tracker)
    }

    @Test
    fun `unknown keys are ignored and known values win`() {
        val parsed = AppSettingsLogic.parse("""{"tracker":true,"unknown":1}""")
        assertEquals(AppSettings(tracker = true), parsed)
    }
}
