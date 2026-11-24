package io.github.thesword1.wwrando.data

import java.security.MessageDigest

/** Pure MD5 helpers shared by the ISO picker pre-verification (unit-testable, no Android deps). */
object IsoVerify {
    /**
     * MD5 of the North American Wind Waker ISO the randomizer accepts. Copied from
     * randomizer.py:CLEAN_WIND_WAKER_ISO_MD5 and asserted equal by test/test_android_constants.py.
     */
    const val CLEAN_ISO_MD5 = "d8e4d45af2032a081a0f446384e9261b"

    /** Hex-encoded MD5 of [bytes]. */
    fun md5Hex(bytes: ByteArray): String =
        MessageDigest.getInstance("MD5").digest(bytes).joinToString("") {
            (it.toInt() and 0xff).toString(16).padStart(2, '0')
        }
}
