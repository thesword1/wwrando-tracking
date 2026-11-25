package io.github.thesword1.wwrando.data

import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * Pure validation/planning for custom model zip import, mirroring
 * `wwr_ui/cosmetic_tab.py install_custom_model_zip`: a single model dir, or a pack under
 * `<top>/models/<name>/`, each containing Link.arc + metadata.txt. No Android types.
 */
object ModelZip {
    val RESERVED_NAMES: Set<String> = setOf("Link", "Random", "Random (exclude Link)")
    val REQUIRED_FILES: List<String> = listOf("Link.arc", "metadata.txt")

    /** Mirrors the app-side model name rules: no reserved names, no "/", no "..", non-empty. */
    fun isValidModelName(name: String): Boolean =
        name.isNotEmpty() &&
            name !in RESERVED_NAMES &&
            "/" !in name &&
            "\\" !in name &&
            !name.contains("..") &&
            name != "." && name != ".."

    private fun unsafeEntry(name: String): Boolean =
        name.contains("..") || name.startsWith("/") || name.startsWith("\\")

    data class PlannedModel(val name: String, val entries: List<Pair<String, String>>)

    sealed interface PlanResult {
        data class Ok(val models: List<PlannedModel>) : PlanResult
        data class Error(val message: String) : PlanResult
    }

    fun plan(zip: ZipFile): PlanResult {
        val entries = zip.entries().toList().map { it.name }
        if (entries.isEmpty()) return PlanResult.Error("Archive is empty")
        for (name in entries) {
            if (unsafeEntry(name)) return PlanResult.Error("Invalid path in archive: $name")
        }

        val top = entries.first().substringBefore('/')
        val modelsPrefix = "$top/models/"
        val isPack = entries.any { it == "$top/models/" || it.startsWith(modelsPrefix) }

        val modelDirs: List<String> = if (isPack) {
            entries.mapNotNull { name ->
                if (!name.startsWith(modelsPrefix)) return@mapNotNull null
                val rest = name.removePrefix(modelsPrefix)
                if (rest.isEmpty()) null else rest.substringBefore('/').takeIf { it.isNotEmpty() }
                    ?.let { "$top/models/$it" }
            }.distinct()
        } else {
            listOf(top)
        }

        val models = ArrayList<PlannedModel>(modelDirs.size)
        for (dir in modelDirs) {
            val name = dir.substringAfterLast('/')
            if (!isValidModelName(name)) return PlanResult.Error("Invalid model name: $name")
            for (required in REQUIRED_FILES) {
                if (entries.none { it == "$dir/$required" }) {
                    return PlanResult.Error("Missing file: $dir/$required")
                }
            }
            val rel = entries.mapNotNull { entry ->
                if (entry == dir || !entry.startsWith("$dir/")) return@mapNotNull null
                val relative = entry.removePrefix("$dir/")
                if (relative.isEmpty()) null else Pair(entry, relative)
            }
            models += PlannedModel(name, rel)
        }
        return PlanResult.Ok(models)
    }

    /** Safe entry-name check reused when reading model zips back out (defense in depth). */
    fun isSafeZipEntryName(name: String): Boolean = !unsafeEntry(name)

    fun isDirectoryEntry(entry: ZipEntry): Boolean = entry.isDirectory || entry.name.endsWith("/")
}
