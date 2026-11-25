package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists the preset-scoped settings diff (`filesDir/settings/current.json`) and named presets
 * (`filesDir/settings/presets/<name>.json`). Presets cover Logic + Tweaks + Starting items only;
 * Customize settings live in `customize.json`, persist separately, and are merged into the run diff
 * but never into presets (PLAN 6). Only non-default values are stored; unknown, invalid or out-of-
 * scope values are dropped on load.
 */
class SettingsStore(context: Context) {
    private val appContext = context.applicationContext
    private val dir = File(appContext.filesDir, "settings")
    private val presetsDir = File(dir, "presets")
    private val currentFile = File(dir, "current.json")
    private val customizeFile = File(dir, "customize.json")
    private val activeFile = File(dir, "active.txt")

    val schema: List<OptionDef> = OptionsSchema.parse(readAsset())
    private val schemaByName: Map<String, OptionDef> = schema.associateBy { it.name }
    private val defaults: Map<String, Any> = SettingsLogic.defaults(schema)
    private val schemaNames: Set<String> = schema.mapTo(HashSet()) { it.name }

    private var activePreset: String? = loadActivePreset()

    /** The stored preset-scoped diff (only non-default values), sanitized against option deps. */
    fun current(): Map<String, Any> = readMap(currentFile, RailSections::isPresetScoped)

    fun effective(name: String): Any = current()[name] ?: defaults.getValue(name)

    fun set(name: String, value: Any) {
        if (!RailSections.isPresetScoped(name)) return
        val option = schemaByName[name] ?: return
        if (!SettingsLogic.isValidValue(option, value)) return
        val diff = current().toMutableMap()
        if (defaults[name] == value) diff.remove(name) else diff[name] = value
        writeMap(currentFile, sanitize(diff))
    }

    fun resetToDefaults() {
        writeMap(currentFile, emptyMap())
    }

    fun listPresets(): List<String> =
        presetsDir.listFiles()
            ?.mapNotNull { file ->
                file.name.takeIf { file.isFile && it.endsWith(".json") }?.removeSuffix(".json")
            }
            ?.sorted()
            ?: emptyList()

    /** Saves the current diff as a preset. Returns the trimmed stored name, or null if invalid. */
    fun savePreset(rawName: String): String? {
        val name = SettingsLogic.normalizePresetName(rawName)
        if (name == SettingsLogic.DEFAULT_PRESET_NAME) return null
        if (!SettingsLogic.isValidPresetName(name)) return null
        presetsDir.mkdirs()
        writeMap(File(presetsDir, "$name.json"), current())
        activePreset = name
        writeActivePreset(name)
        return name
    }

    fun loadPreset(name: String): Boolean {
        if (name == SettingsLogic.DEFAULT_PRESET_NAME) {
            resetToDefaults()
            activePreset = null
            writeActivePreset(null)
            return true
        }
        val file = File(presetsDir, "$name.json")
        if (!file.isFile) return false
        writeMap(currentFile, sanitize(readMap(file, RailSections::isPresetScoped)))
        activePreset = name
        writeActivePreset(name)
        return true
    }

    fun deletePreset(name: String) {
        if (name == SettingsLogic.DEFAULT_PRESET_NAME) return
        File(presetsDir, "$name.json").delete()
        if (activePreset == name) {
            activePreset = null
            writeActivePreset(null)
        }
    }

    /** "Default" when no named preset is active. */
    fun activePresetName(): String = activePreset ?: SettingsLogic.DEFAULT_PRESET_NAME

    fun isModified(): Boolean =
        SettingsLogic.isModified(
            current(),
            activePreset?.let {
                sanitize(readMap(File(presetsDir, "$it.json"), RailSections::isPresetScoped))
            } ?: emptyMap(),
        )

    fun changesCount(): Int = current().size

    /** Customize settings, kept out of presets and merged into the run diff (see PLAN 6). */
    fun customize(): Map<String, Any> = readMap(customizeFile, RailSections::isCustomize)

    fun setCustomize(name: String, value: Any) {
        if (!RailSections.isCustomize(name)) return
        val option = schemaByName[name] ?: return
        if (!SettingsLogic.isValidValue(option, value)) return
        val diff = customize().toMutableMap()
        if (defaults[name] == value) diff.remove(name) else diff[name] = value
        writeMap(customizeFile, diff)
    }

    /** The complete run diff: preset-scoped settings plus Customize settings. */
    fun runDiff(): Map<String, Any> = sanitize(current() + customize())

    fun inGameTrackerEnabled(): Boolean = effective("in_game_tracker") as Boolean

    /** The diff as JSON for the loopback bridge's GET /settings route. */
    fun currentDiffJson(): String = JSONObject(runDiff()).toString()

    fun currentDiffJsonBytes(): ByteArray = currentDiffJson().toByteArray(Charsets.UTF_8)

    private fun sanitize(diff: Map<String, Any>): Map<String, Any> {
        var current = diff
        // Sword modes remove Hurricane Spin / Progressive Sword from the starting list (desktop rule).
        val swordMode = (defaults + current)[OptionDependencies.SWORD_MODE] as? String
        val gearOption = schemaByName["starting_gear"] as? OptionDef.ItemList
        if (swordMode != null && gearOption != null) {
            val gear = current["starting_gear"] as? List<*>
            if (gear != null) {
                val filtered = StartingItemsLogic.filteredStarting(gear.filterIsInstance<String>(), swordMode)
                current = if (filtered == gearOption.default) {
                    current - "starting_gear"
                } else {
                    current + ("starting_gear" to filtered)
                }
            }
        }
        val effective = SettingsLogic.effectiveValues(defaults, current)
        val clean = OptionDependencies.sanitized(effective, defaults)
        return SettingsLogic.diffAgainstDefaults(defaults, clean)
    }

    private fun readAsset(): String =
        appContext.assets.open("options_schema.json").bufferedReader(Charsets.UTF_8).use { it.readText() }

    private fun readMap(file: File, inScope: (String) -> Boolean): Map<String, Any> {
        if (!file.isFile) return emptyMap()
        val parsed = runCatching { mapFromJson(JSONObject(file.readText(Charsets.UTF_8))) }
            .getOrDefault(emptyMap())
        return parsed
            .filterKeys { it in schemaNames && inScope(it) }
            .filter { (name, value) ->
                schemaByName[name]?.let { SettingsLogic.isValidValue(it, value) } == true
            }
    }

    private fun writeMap(file: File, values: Map<String, Any>) {
        file.parentFile?.mkdirs()
        file.writeText(JSONObject(values).toString(), Charsets.UTF_8)
    }

    private fun mapFromJson(json: JSONObject): Map<String, Any> {
        val out = LinkedHashMap<String, Any>()
        json.keys().forEach { key ->
            when (val value = json.get(key)) {
                is JSONArray -> out[key] = (0 until value.length()).map { value.getString(it) }
                else -> out[key] = value
            }
        }
        return out
    }

    private fun loadActivePreset(): String? {
        if (!activeFile.isFile) return null
        return activeFile.readText(Charsets.UTF_8).trim()
            .takeIf { it.isNotEmpty() && File(presetsDir, "$it.json").isFile }
    }

    private fun writeActivePreset(name: String?) {
        if (name == null) activeFile.delete() else activeFile.writeText(name, Charsets.UTF_8)
    }
}
