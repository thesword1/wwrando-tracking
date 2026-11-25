package io.github.thesword1.wwrando.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import io.github.thesword1.wwrando.data.ShareLogic

/** Reads the app's bundled commit so Share/Copy can stamp `Build: <commit>`. */
fun readBuildCommit(context: Context): String = runCatching {
    context.assets.open("build_commit.txt").bufferedReader(Charsets.UTF_8).use { it.readText().trim() }
}.getOrDefault("")

/** Opens the system share sheet with the permalink/hash/build text. */
fun sharePermalink(context: Context, permalink: String, seedHash: String) {
    val text = ShareLogic.text(permalink, seedHash, readBuildCommit(context))
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(intent, null))
}

/** Copies the same permalink/hash/build text to the clipboard. */
fun copyPermalinkShare(context: Context, permalink: String, seedHash: String) {
    val text = ShareLogic.text(permalink, seedHash, readBuildCommit(context))
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("Permalink", text))
}
