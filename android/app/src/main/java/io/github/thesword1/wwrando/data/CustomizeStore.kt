package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persists the full Customize state in `filesDir/settings/customize.json` (PLAN 6b): player model,
 * casual clothes, custom voice/items toggles, colour preset and custom colours. These are merged
 * into the run diff but never into presets.
 */
class CustomizeStore(context: Context) {
    private val appContext = context.applicationContext
    private val file = File(File(appContext.filesDir, "settings"), "customize.json")

    fun state(): CustomizeLogic.State {
        if (!file.isFile) return CustomizeLogic.State()
        val json = runCatching { JSONObject(file.readText(Charsets.UTF_8)) }.getOrNull() ?: return CustomizeLogic.State()
        val colorPreset = json.optString("custom_color_preset").takeIf { it.isNotEmpty() }
            ?: CustomizeLogic.DEFAULT_PRESET
        return CustomizeLogic.State(
            playerModel = json.optString("custom_player_model").takeIf { it.isNotEmpty() }
                ?: CustomizeLogic.DEFAULT_MODEL,
            casualClothes = json.optBoolean("player_in_casual_clothes", false),
            disableVoice = json.optBoolean("disable_custom_player_voice", false),
            disableItems = json.optBoolean("disable_custom_player_items", false),
            colorPreset = colorPreset,
            customColors = readColors(json.optJSONObject("custom_colors")),
            presetSelection = json.optString("color_preset_selection").takeIf { it.isNotEmpty() }
                ?: colorPreset,
        )
    }

    fun save(state: CustomizeLogic.State) {
        val json = JSONObject()
            .put("custom_player_model", state.playerModel)
            .put("player_in_casual_clothes", state.casualClothes)
            .put("disable_custom_player_voice", state.disableVoice)
            .put("disable_custom_player_items", state.disableItems)
            .put("custom_color_preset", state.colorPreset)
            .put("custom_colors", colorsJson(state.customColors))
            .put("color_preset_selection", state.presetSelection)
        file.parentFile?.mkdirs()
        file.writeText(json.toString(), Charsets.UTF_8)
    }

    /** The complete Customize payload for the bridge's GET /settings route (PLAN: "unchanged"). */
    fun all(): Map<String, Any> {
        val s = state()
        return linkedMapOf(
            "custom_player_model" to s.playerModel,
            "player_in_casual_clothes" to s.casualClothes,
            "disable_custom_player_voice" to s.disableVoice,
            "disable_custom_player_items" to s.disableItems,
            "custom_color_preset" to s.colorPreset,
            "custom_colors" to s.customColors,
        )
    }

    private fun readColors(obj: JSONObject?): Map<String, List<Int>> {
        if (obj == null) return emptyMap()
        val out = LinkedHashMap<String, List<Int>>()
        obj.keys().forEach { key ->
            val array = obj.optJSONArray(key) ?: return@forEach
            if (array.length() != 3) return@forEach
            val color = (0 until 3).map { array.getInt(it) }
            if (color.all { it in 0..255 }) out[key] = color
        }
        return out
    }

    private fun colorsJson(colors: Map<String, List<Int>>): JSONObject {
        val obj = JSONObject()
        colors.forEach { (name, color) -> obj.put(name, JSONArray(color)) }
        return obj
    }
}
