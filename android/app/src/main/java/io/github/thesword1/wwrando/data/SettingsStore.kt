package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists the settings diff (`filesDir/settings/current.json`) and named presets
 * (`filesDir/settings/presets/<name>.json`). Only non-default values are stored; unknown or
 * invalid values are dropped on load so a stale diff after an app update never breaks a run.
 */
class SettingsStore(context: Context) {
    private val appContext = context.applicationContext
    private val dir = File(appContext.filesDir, "settings")
    private val presetsDir = File(dir, "presets")
    private val currentFile = File(dir, "current.json")
    private val activeFile = File(dir, "active.txt")
    private val appFile = File(dir, "app.json")

    val schema: List<OptionDef> = OptionsSchema.parse(readAsset())
    private val defaults: Map<String, Any> = SettingsLogic.defaults(schema)
    private val schemaNames: Set<String> = schema.mapTo(HashSet()) { it.name }

    private var activePreset: String? = loadActivePreset()

    /** The stored diff (only non-default values), with stale keys dropped. */
    fun current(): Map<String, Any> = readMap(currentFile)

    fun set(name: String, value: Any) {
        val option = schema.firstOrNull { it.name == name } ?: return
        if (!SettingsLogic.isValidValue(option, value)) return
        val diff = current().toMutableMap()
        if (defaults[name] == value) diff.remove(name) else diff[name] = value
        writeMap(currentFile, diff)
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
        writeMap(currentFile, readMap(file))
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
        SettingsLogic.isModified(current(), activePreset?.let { readMap(File(presetsDir, "$it.json")) } ?: emptyMap())

    fun changesCount(): Int = current().size

    /** App-level settings, kept out of presets and the randomizer diff (see [AppSettingsLogic]). */
    fun trackerEnabled(): Boolean = readAppSettings().tracker

    fun setTrackerEnabled(enabled: Boolean) {
        val current = readAppSettings()
        if (current.tracker == enabled) return
        appFile.parentFile?.mkdirs()
        appFile.writeText(AppSettingsLogic.toJson(current.copy(tracker = enabled)), Charsets.UTF_8)
    }

    /** The diff as JSON for the loopback bridge's GET /settings route. */
    fun currentDiffJson(): String = JSONObject(current()).toString()

    fun currentDiffJsonBytes(): ByteArray = currentDiffJson().toByteArray(Charsets.UTF_8)

    private fun readAsset(): String =
        appContext.assets.open("options_schema.json").bufferedReader(Charsets.UTF_8).use { it.readText() }

    private fun readMap(file: File): Map<String, Any> {
        if (!file.isFile) return emptyMap()
        val parsed = runCatching { mapFromJson(JSONObject(file.readText(Charsets.UTF_8))) }
            .getOrDefault(emptyMap())
        return parsed
            .filterKeys { it in schemaNames }
            .filter { (name, value) -> schema.firstOrNull { it.name == name }?.let { SettingsLogic.isValidValue(it, value) } == true }
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

    private fun readAppSettings(): AppSettings {
        if (!appFile.isFile) return AppSettingsLogic.defaults()
        return AppSettingsLogic.parse(appFile.readText(Charsets.UTF_8))
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
