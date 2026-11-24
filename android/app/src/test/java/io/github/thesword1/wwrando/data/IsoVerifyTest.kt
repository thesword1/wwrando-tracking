package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Test

class IsoVerifyTest {
    @Test
    fun md5MatchesKnownVector() {
        // MD5 of the empty string.
        assertEquals("d41d8cd98f00b204e9800998ecf8427e", IsoVerify.md5Hex(ByteArray(0)))
        // MD5 of "abc".
        assertEquals("900150983cd24fb0d6963f7d28e17f72", IsoVerify.md5Hex("abc".toByteArray()))
    }

    @Test
    fun cleanIsoMd5HasExpectedValue() {
        assertEquals("d8e4d45af2032a081a0f446384e9261b", IsoVerify.CLEAN_ISO_MD5)
    }
}
