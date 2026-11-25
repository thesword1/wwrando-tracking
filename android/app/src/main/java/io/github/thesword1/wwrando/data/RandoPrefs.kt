package io.github.thesword1.wwrando.data

import android.content.Context
import android.content.SharedPreferences
import android.net.Uri

/** The user's picked clean ISO: SAF URI plus the facts used to decide whether it is verified. */
data class IsoPick(
    val uri: Uri,
    val name: String,
    val size: Long,
    val lastModified: Long,
    val verified: Boolean,
)

/**
 * Small SharedPreferences store for the SAF grants the real run needs (no shared storage). The
 * verified flag is keyed on (uri, size, lastModified) so re-picking the same file keeps the badge and
 * any change to the underlying file invalidates it.
 */
class RandoPrefs(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("rando", Context.MODE_PRIVATE)

    fun saveIso(uri: Uri, name: String, size: Long, lastModified: Long) {
        prefs.edit()
            .putString(KEY_ISO_URI, uri.toString())
            .putString(KEY_ISO_NAME, name)
            .putLong(KEY_ISO_SIZE, size)
            .putLong(KEY_ISO_MODIFIED, lastModified)
            .putString(KEY_ISO_VERIFIED_FOR, verificationKey(uri, size, lastModified))
            .putBoolean(KEY_ISO_VERIFIED, false)
            .apply()
    }

    fun loadIso(): IsoPick? {
        val uriText = prefs.getString(KEY_ISO_URI, null) ?: return null
        val name = prefs.getString(KEY_ISO_NAME, null) ?: return null
        val size = prefs.getLong(KEY_ISO_SIZE, -1L)
        val lastModified = prefs.getLong(KEY_ISO_MODIFIED, -1L)
        val uri = Uri.parse(uriText)
        val verified = prefs.getBoolean(KEY_ISO_VERIFIED, false) &&
            prefs.getString(KEY_ISO_VERIFIED_FOR, null) == verificationKey(uri, size, lastModified)
        return IsoPick(uri, name, size, lastModified, verified)
    }

    fun markIsoVerified(uri: Uri, size: Long, lastModified: Long) {
        prefs.edit()
            .putString(KEY_ISO_VERIFIED_FOR, verificationKey(uri, size, lastModified))
            .putBoolean(KEY_ISO_VERIFIED, true)
            .apply()
    }

    fun saveOutputTree(uri: Uri) {
        prefs.edit().putString(KEY_OUT_TREE, uri.toString()).apply()
    }

    fun loadOutputTree(): Uri? = prefs.getString(KEY_OUT_TREE, null)?.let { Uri.parse(it) }

    fun saveSeed(seed: String) {
        prefs.edit().putString(KEY_SEED, seed).apply()
    }

    fun loadSeed(): String = prefs.getString(KEY_SEED, "") ?: ""

    companion object {
        private const val KEY_ISO_URI = "iso_uri"
        private const val KEY_ISO_NAME = "iso_name"
        private const val KEY_ISO_SIZE = "iso_size"
        private const val KEY_ISO_MODIFIED = "iso_modified"
        private const val KEY_ISO_VERIFIED = "iso_verified"
        private const val KEY_ISO_VERIFIED_FOR = "iso_verified_for"
        private const val KEY_OUT_TREE = "out_tree_uri"
        private const val KEY_SEED = "seed"

        private fun verificationKey(uri: Uri, size: Long, lastModified: Long): String =
            "${uri}|$size|$lastModified"
    }
}
