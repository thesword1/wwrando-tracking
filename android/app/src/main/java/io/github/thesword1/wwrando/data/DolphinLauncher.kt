package io.github.thesword1.wwrando.data

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri

/**
 * The exact launch request sent to Dolphin, expressed without an Intent so the unit test can assert
 * the package, component, extra and flags on plain values.
 */
data class DolphinLaunchSpec(
    val packageName: String,
    val componentClass: String,
    val autoStartFile: String,
    val dataUri: String,
    val flags: Int,
    val sendsRawUriClipData: Boolean,
)

/** Launches a generated ISO in Dolphin through a granted `content://` URI. */
object DolphinLauncher {
    const val EXTRA_AUTO_START = "AutoStartFile"
    const val DOLPHIN_MAIN_ACTIVITY = "org.dolphinemu.dolphinemu.ui.main.MainActivity"
    val PACKAGES = listOf("org.dolphinemu.dolphinemu", "org.dolphinemu.mmjr")

    fun buildSpec(packageName: String, isoUriString: String): DolphinLaunchSpec = DolphinLaunchSpec(
        packageName = packageName,
        componentClass = DOLPHIN_MAIN_ACTIVITY,
        autoStartFile = isoUriString,
        dataUri = isoUriString,
        flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or
            Intent.FLAG_ACTIVITY_NEW_TASK or
            Intent.FLAG_ACTIVITY_CLEAR_TASK,
        sendsRawUriClipData = true,
    )

    fun buildIntent(packageName: String, isoUri: Uri): Intent {
        val spec = buildSpec(packageName, isoUri.toString())
        return Intent(Intent.ACTION_MAIN).apply {
            component = ComponentName(spec.packageName, spec.componentClass)
            putExtra(EXTRA_AUTO_START, spec.autoStartFile)
            data = Uri.parse(spec.dataUri)
            flags = spec.flags
            clipData = ClipData.newRawUri("iso", isoUri)
        }
    }

    fun isInstalled(context: Context, packageName: String): Boolean =
        runCatching { context.packageManager.getPackageInfo(packageName, 0) }.isSuccess

    fun firstInstalled(context: Context): String? = PACKAGES.firstOrNull { isInstalled(context, it) }

    /** Launches Dolphin for [isoUri]; returns a user-facing error string, or null on success. */
    fun launch(context: Context, isoUri: Uri): String? {
        val packageName = firstInstalled(context)
        if (packageName != null) {
            val result = runCatching { context.startActivity(buildIntent(packageName, isoUri)) }
            if (result.isSuccess) return null
            if (result.exceptionOrNull() !is ActivityNotFoundException) {
                return "Could not launch Dolphin"
            }
        }
        return openWithChooser(context, isoUri)
    }

    private fun openWithChooser(context: Context, isoUri: Uri): String? {
        val view = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(isoUri, "application/octet-stream")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        return runCatching {
            context.startActivity(Intent.createChooser(view, "Open ISO"))
            null
        }.getOrElse { "Dolphin not found" }
    }
}
