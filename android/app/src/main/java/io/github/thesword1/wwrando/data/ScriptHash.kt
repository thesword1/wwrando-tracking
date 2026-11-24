package io.github.thesword1.wwrando.data

import java.security.MessageDigest

/**
 * Identity and install decision for the Python shim bundled with the APK. Pure Kotlin so the
 * hash/version check is unit-testable without a device (mirrors :app's ScriptBundle).
 */
object ScriptHash {
    /** Lowercase SHA-256 hex of [content], used as the installed-script version marker. */
    fun sha256(content: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(content.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
    }

    /** True when the bundled script differs from the last installed hash, or nothing is installed yet. */
    fun installNeeded(bundledHash: String, installedHash: String?, force: Boolean = false): Boolean =
        force || installedHash != bundledHash
}
