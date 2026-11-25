package io.github.thesword1.wwrando.data

import org.json.JSONArray
import org.json.JSONObject

/** Result of a permalink encode/decode round through android_run.py. */
data class PermalinkResult(
    val ok: Boolean,
    val seed: String = "",
    val permalink: String = "",
    val settings: Map<String, Any> = emptyMap(),
    val error: String? = null,
)

/** Pure rules for the Advanced screen's permalink encode/decode plumbing. No Android types. */
object AdvancedLogic {
    /**
     * Parses the shim's one-JSON-line result from the last non-blank stdout line (noise such as
     * startup warnings may precede it). Returns null when there is no parseable JSON line.
     */
    fun parseResult(stdout: String): PermalinkResult? {
        val line = stdout.lineSequence().map { it.trim() }.lastOrNull { it.isNotBlank() } ?: return null
        val json = runCatching { JSONObject(line) }.getOrNull() ?: return null
        return PermalinkResult(
            ok = json.optBoolean("ok", false),
            seed = json.optString("seed", ""),
            permalink = json.optString("permalink", ""),
            settings = json.optJSONObject("settings")?.let(::mapFromJson) ?: emptyMap(),
            error = json.optString("error", "").takeIf { it.isNotBlank() },
        )
    }

    /**
     * Turns decoded permalink settings into the preset-scoped stored diff: defaults are dropped,
     * non-preset (Customize) and unknown names are ignored, invalid values are dropped.
     */
    fun decodedDiff(
        decoded: Map<String, Any>,
        schemaByName: Map<String, OptionDef>,
        defaults: Map<String, Any>,
    ): Map<String, Any> =
        decoded
            .filterKeys { RailSections.isPresetScoped(it) && schemaByName.containsKey(it) }
            .filter { (name, value) -> schemaByName[name]?.let { SettingsLogic.isValidValue(it, value) } == true }
            .let { SettingsLogic.diffAgainstDefaults(defaults, it) }

    /** org.json object -> plain Kotlin map, lists kept as lists of strings (JSON-ready values). */
    fun mapFromJson(json: JSONObject): Map<String, Any> {
        val out = LinkedHashMap<String, Any>()
        json.keys().forEach { key ->
            when (val value = json.get(key)) {
                is JSONArray -> out[key] = (0 until value.length()).map { value.getString(it) }
                else -> out[key] = value
            }
        }
        return out
    }
}
