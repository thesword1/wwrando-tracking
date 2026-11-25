package io.github.thesword1.wwrando.data

import org.json.JSONObject

/** App-level settings stored alongside, but outside, the randomizer options diff/presets. */
data class AppSettings(val tracker: Boolean = true)

/** Pure serialization for app settings (unit-testable, no Android types). */
object AppSettingsLogic {
    fun defaults(): AppSettings = AppSettings()

    fun toJson(settings: AppSettings): String = JSONObject()
        .put("tracker", settings.tracker)
        .toString()

    /** Missing, blank or malformed input yields defaults; unknown keys are ignored. */
    fun parse(json: String): AppSettings {
        val obj = runCatching { JSONObject(json) }.getOrNull() ?: return defaults()
        return AppSettings(tracker = obj.optBoolean("tracker", true))
    }
}
