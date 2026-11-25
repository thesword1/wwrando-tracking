package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/**
 * Owns `filesDir/models/<name>.zip`: SAF imports are normalized here (single model or a pack split
 * into one zip per model, entries relative to the model dir), and metadata/preview/sound files are
 * read straight out of each zip. The built-in Link model is served from APK assets (`link/`).
 */
class ModelStore(
    private val dir: File,
    private val linkMetadataProvider: () -> String? = { null },
    private val linkEntryProvider: (String) -> ByteArray? = { null },
) {
    sealed interface ImportResult {
        data class Ok(val installed: Int) : ImportResult
        data class Error(val message: String) : ImportResult
    }

    data class ModelInfo(val name: String, val md5: String, val size: Long)

    /** Installed model names (sorted, never reserved names). */
    fun list(): List<String> = runCatching {
        dir.listFiles()
            ?.filter { it.isFile && it.name.endsWith(".zip") }
            ?.map { it.name.removeSuffix(".zip") }
            ?.filter { ModelZip.isValidModelName(it) }
            ?.sorted()
            ?: emptyList()
    }.getOrDefault(emptyList())

    fun modelInfos(): List<ModelInfo> = list().mapNotNull { name ->
        val file = zipFile(name)
        if (!file.isFile) return@mapNotNull null
        ModelInfo(name, md5(file), file.length())
    }

    fun zipFile(name: String): File = File(dir, "$name.zip")

    fun md5Of(name: String): String? = zipFile(name).takeIf { it.isFile }?.let { md5(it) }

    fun delete(name: String) {
        zipFile(name).delete()
    }

    fun importZip(source: InputStream): ImportResult {
        dir.mkdirs()
        val temp = File(dir, ".import-${System.nanoTime()}.tmp")
        return try {
            temp.outputStream().use { out -> source.copyTo(out) }
            val zip = ZipFile(temp)
            try {
                when (val plan = ModelZip.plan(zip)) {
                    is ModelZip.PlanResult.Error -> ImportResult.Error(plan.message)
                    is ModelZip.PlanResult.Ok -> {
                        for (model in plan.models) writeModelZip(zip, model)
                        ImportResult.Ok(plan.models.size)
                    }
                }
            } finally {
                runCatching { zip.close() }
            }
        } catch (e: Exception) {
            ImportResult.Error(e.message ?: "failed to import model zip")
        } finally {
            runCatching { temp.delete() }
        }
    }

    private fun writeModelZip(source: ZipFile, model: ModelZip.PlannedModel) {
        dir.mkdirs()
        val target = zipFile(model.name)
        val tmp = File(dir, "${model.name}.zip.tmp")
        runCatching { target.delete() }
        ZipOutputStream(tmp.outputStream().buffered()).use { out ->
            for ((sourcePath, relativePath) in model.entries) {
                val entry = source.getEntry(sourcePath) ?: continue
                if (ModelZip.isDirectoryEntry(entry)) {
                    val dirPath = if (relativePath.endsWith("/")) relativePath else "$relativePath/"
                    out.putNextEntry(ZipEntry(dirPath))
                    out.closeEntry()
                    continue
                }
                out.putNextEntry(ZipEntry(relativePath))
                source.getInputStream(entry).use { input -> copy(input, out) }
                out.closeEntry()
            }
        }
        if (!tmp.renameTo(target)) {
            tmp.copyTo(target, overwrite = true)
            tmp.delete()
        }
    }

    private fun copy(input: InputStream, output: OutputStream) {
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val n = input.read(buffer)
            if (n == -1) break
            output.write(buffer, 0, n)
        }
    }

    fun readEntry(name: String, path: String): ByteArray? =
        runCatching {
            ZipFile(zipFile(name)).use { zip ->
                zip.getEntry(path)?.let { entry -> zip.getInputStream(entry).use { it.readBytes() } }
            }
        }.getOrNull()

    fun metadata(name: String): ModelMetadata = when (name) {
        "Random", "Random (exclude Link)" -> ModelMetadata()
        "Link" -> {
            val text = linkMetadataProvider() ?: return ModelMetadata()
            ModelMetadata.parse(text)
        }
        else -> {
            val text = readEntry(name, "metadata.txt")?.toString(Charsets.UTF_8) ?: return ModelMetadata()
            ModelMetadata.parse(text)
        }
    }

    fun previewBase(name: String, prefix: String): ByteArray? = when (name) {
        "Link" -> linkEntryProvider("link_preview/preview_$prefix.png")
        "Random", "Random (exclude Link)" -> null
        else -> readEntry(name, "preview/preview_$prefix.png")
    }

    fun previewMask(name: String, prefix: String, colorName: String): ByteArray? = when (name) {
        "Link" -> linkEntryProvider("link_preview/preview_${prefix}_$colorName.png")
        else -> readEntry(name, "preview/preview_${prefix}_$colorName.png")
    }

    /** Mirrors disable_invalid_cosmetic_options: Random always has voice; others need both files. */
    fun hasCustomVoice(name: String): Boolean = when (name) {
        "Random", "Random (exclude Link)" -> true
        else -> readEntry(name, "sound/JaiInit.aaf") != null && readEntry(name, "sound/voice_0.aw") != null
    }

    companion object {
        fun from(context: Context): ModelStore {
            val app = context.applicationContext
            return ModelStore(
                File(app.filesDir, "models"),
                linkMetadataProvider = {
                    runCatching {
                        app.assets.open("link/link_metadata.txt").bufferedReader(Charsets.UTF_8).use { it.readText() }
                    }.getOrNull()
                },
                linkEntryProvider = { path ->
                    runCatching { app.assets.open("link/$path").use { it.readBytes() } }.getOrNull()
                },
            )
        }

        private fun md5(file: File): String {
            val digest = MessageDigest.getInstance("MD5")
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val n = input.read(buffer)
                    if (n == -1) break
                    digest.update(buffer, 0, n)
                }
            }
            return digest.digest().joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
        }
    }
}
