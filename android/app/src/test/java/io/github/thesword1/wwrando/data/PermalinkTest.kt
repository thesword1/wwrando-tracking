package io.github.thesword1.wwrando.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PermalinkTest {

    @Test
    fun `accepts base64 permalinks within the length bounds`() {
        assertTrue(Permalink.isValid("QUJDRA=="))
        assertTrue(Permalink.isValid("aA=="))
        assertTrue(Permalink.isValid("A".repeat(4)))
        assertTrue(Permalink.isValid("A".repeat(2000)))
    }

    @Test
    fun `rejects blank short long and bad-characters values`() {
        assertFalse(Permalink.isValid(""))
        assertFalse(Permalink.isValid("ab"))
        assertFalse(Permalink.isValid("abc"))
        assertFalse(Permalink.isValid("A".repeat(2001)))
        assertFalse(Permalink.isValid("abc!def"))
        assertFalse(Permalink.isValid("abc def"))
        assertFalse(Permalink.isValid("abc\ndef"))
    }
}
