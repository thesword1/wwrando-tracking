package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScriptHashTest {
    @Test
    fun sha256MatchesKnownVector() {
        // SHA-256 of the empty string.
        assertEquals(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            ScriptHash.sha256(""),
        )
    }

    @Test
    fun installNeededWhenNothingInstalledYet() {
        assertTrue(ScriptHash.installNeeded("abc", null))
    }

    @Test
    fun installNeededWhenHashDiffers() {
        assertTrue(ScriptHash.installNeeded("abc", "def"))
    }

    @Test
    fun notNeededWhenHashMatches() {
        assertFalse(ScriptHash.installNeeded("abc", "abc"))
    }

    @Test
    fun forceReinstalls() {
        assertTrue(ScriptHash.installNeeded("abc", "abc", force = true))
    }
}
