package io.github.thesword1.wwrando.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SetupLogicTest {

    @Test
    fun `setup needed when nothing is installed yet`() {
        assertTrue(SetupLogic.setupNeeded(null, "abc"))
        assertTrue(SetupLogic.setupNeeded("", "abc"))
    }

    @Test
    fun `setup needed when the installed commit differs from the APK commit`() {
        assertTrue(SetupLogic.setupNeeded("def", "abc"))
    }

    @Test
    fun `setup not needed when the installed commit matches`() {
        assertFalse(SetupLogic.setupNeeded("abc", "abc"))
    }
}
