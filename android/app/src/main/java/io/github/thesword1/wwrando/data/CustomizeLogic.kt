package io.github.thesword1.wwrando.data

import kotlin.random.Random

/**
 * Pure customization rules mirroring `wwr_ui/cosmetic_tab.py` get_color/set_color/preset/randomize
 * semantics, so model/preset switching and colour changes behave exactly like the desktop tab.
 * No Android types: state is immutable and unit-tested directly.
 */
object CustomizeLogic {
    const val DEFAULT_MODEL = "Link"
    const val DEFAULT_PRESET = "Default"
    const val CUSTOM_PRESET = "Custom"
    val RESERVED_PRESET_NAMES: Set<String> = setOf(DEFAULT_PRESET, CUSTOM_PRESET)

    data class State(
        val playerModel: String = DEFAULT_MODEL,
        val casualClothes: Boolean = false,
        val disableVoice: Boolean = false,
        val disableItems: Boolean = false,
        val colorPreset: String = DEFAULT_PRESET,
        val customColors: Map<String, List<Int>> = emptyMap(),
    )

    fun isCasual(state: State, metadata: ModelMetadata): Boolean =
        state.casualClothes && !metadata.disableCasualClothes

    /** Default colours for the current model + hero/casual prefix (metadata custom_colors). */
    fun defaultColors(state: State, metadata: ModelMetadata): Map<String, List<Int>> =
        metadata.customColors(isCasual(state, metadata)).mapValues { it.value.toList() }

    fun colorPresets(state: State, metadata: ModelMetadata): Map<String, Map<String, List<Int>>> =
        metadata.colorPresets(isCasual(state, metadata)).mapValues { (_, preset) ->
            preset.mapValues { it.value.toList() }
        }

    /** Mirror of CosmeticTab.get_color. */
    fun getColor(
        state: State,
        metadata: ModelMetadata,
        defaultColors: Map<String, List<Int>>,
        colorName: String,
    ): List<Int> {
        val base = defaultColors[colorName] ?: listOf(255, 255, 255)
        return when (state.colorPreset) {
            DEFAULT_PRESET -> base
            CUSTOM_PRESET -> state.customColors[colorName] ?: base
            else -> colorPresets(state, metadata)[state.colorPreset]?.get(colorName) ?: base
        }
    }

    /** Mirror of CosmeticTab.set_color (save_color_as_custom with the auto-switch to Custom). */
    fun applyColorChange(
        state: State,
        metadata: ModelMetadata,
        defaultColors: Map<String, List<Int>>,
        colorName: String,
        newColor: List<Int>,
    ): State {
        val custom = state.customColors.toMutableMap()
        custom[colorName] = newColor
        var preset = state.colorPreset
        if (preset != CUSTOM_PRESET) {
            for (other in defaultColors.keys) {
                if (other == colorName) continue
                custom[other] = getColor(state, metadata, defaultColors, other)
            }
            preset = CUSTOM_PRESET
        }
        return state.copy(customColors = custom, colorPreset = preset)
    }

    /** update_color_presets_list: keep the old preset if the new model also has it, else Default. */
    fun presetAfterSwitch(previous: String, presets: Map<String, Map<String, List<Int>>>): String =
        if (previous in presets) previous else DEFAULT_PRESET

    fun presetNames(state: State, metadata: ModelMetadata): List<String> =
        listOf(DEFAULT_PRESET, CUSTOM_PRESET) +
            colorPresets(state, metadata).keys.filter { it !in RESERVED_PRESET_NAMES }

    /** get_random_h_and_v_shifts_for_custom_color, with the very-unsaturated value clamp. */
    fun randomHVShift(defaultColor: List<Int>, random: Random): Pair<Int, Int> {
        val hsv = ColorLogic.rgbToHsv(intArrayOf(defaultColor[0], defaultColor[1], defaultColor[2]))
        val v = hsv.v
        var minV = -40
        var maxV = 40
        if (hsv.s < 10) {
            minV = maxOf(-40, 0 - v)
            maxV = minOf(40, 100 - v)
        }
        return random.nextInt(0, 360) to random.nextInt(minV, maxV + 1)
    }

    private fun randomize(
        state: State,
        metadata: ModelMetadata,
        separately: Boolean,
        random: Random,
    ): State {
        val defaults = defaultColors(state, metadata)
        var next = state
        if (separately) {
            for ((name, default) in defaults) {
                val (h, v) = randomHVShift(default, random)
                next = applyColorChange(next, metadata, defaults, name, ColorLogic.hsvShiftColor(default.toIntArray(), h, v).toList())
            }
        } else {
            val h = random.nextInt(0, 360)
            val v = random.nextInt(-40, 41)
            for ((name, default) in defaults) {
                next = applyColorChange(next, metadata, defaults, name, ColorLogic.hsvShiftColor(default.toIntArray(), h, v).toList())
            }
        }
        return next
    }

    fun randomizeAllTogether(state: State, metadata: ModelMetadata, random: Random): State =
        randomize(state, metadata, separately = false, random = random)

    fun randomizeAllSeparately(state: State, metadata: ModelMetadata, random: Random): State =
        randomize(state, metadata, separately = true, random = random)

    fun randomizeOne(
        state: State,
        metadata: ModelMetadata,
        defaultColors: Map<String, List<Int>>,
        colorName: String,
        random: Random,
    ): State {
        val default = defaultColors[colorName] ?: return state
        val (h, v) = randomHVShift(default, random)
        val color = ColorLogic.hsvShiftColor(default.toIntArray(), h, v).toList()
        return applyColorChange(state, metadata, defaultColors, colorName, color)
    }

    fun resetOne(
        state: State,
        metadata: ModelMetadata,
        defaultColors: Map<String, List<Int>>,
        colorName: String,
    ): State {
        val default = defaultColors[colorName] ?: return state
        return if (getColor(state, metadata, defaultColors, colorName) != default) {
            applyColorChange(state, metadata, defaultColors, colorName, default)
        } else {
            state
        }
    }

    data class ColorPreset(
        val modelName: String,
        val colors: Map<String, List<Int>>,
        val isCasual: Boolean,
    )

    /** Encode a color preset in the desktop YAML format (model_name / colors / is_casual). */
    fun encodeColorPreset(preset: ColorPreset): String = buildString {
        append("model_name: ").append(preset.modelName).append('\n')
        append("colors:\n")
        for ((name, color) in preset.colors) {
            append("  ").append(name).append(": 0x")
            append(color[0].toString(16).uppercase().padStart(2, '0'))
            append(color[1].toString(16).uppercase().padStart(2, '0'))
            append(color[2].toString(16).uppercase().padStart(2, '0'))
            append('\n')
        }
        append("is_casual: ").append(if (preset.isCasual) "true" else "false").append('\n')
    }

    /** Decode the desktop color preset format; returns null when it cannot be parsed. */
    fun decodeColorPreset(text: String): ColorPreset? {
        var modelName: String? = null
        var isCasual = false
        val colors = LinkedHashMap<String, List<Int>>()
        var inColors = false
        for (rawLine in text.lineSequence()) {
            val line = rawLine.trimEnd()
            if (line.isBlank() || line.trimStart().startsWith("#")) continue
            val trimmed = line.trimStart()
            if (trimmed.startsWith("-")) continue // YAML list item (not used in this format)
            val indent = line.length - line.trimStart().length
            if (inColors && indent > 0) {
                val colon = trimmed.indexOf(':')
                if (colon <= 0) continue
                val name = trimmed.substring(0, colon).trim().removeSurrounding("\"", "'")
                val value = trimmed.substring(colon + 1).trim().removeSurrounding("\"", "'")
                if (name.isEmpty()) continue
                colors[name] = try {
                    ModelMetadata.parseHexColor(value).toList()
                } catch (e: InvalidColorException) {
                    return null
                }
                continue
            }
            val colon = trimmed.indexOf(':')
            if (colon <= 0) continue
            val key = trimmed.substring(0, colon).trim()
            val value = trimmed.substring(colon + 1).trim().removeSurrounding("\"", "'")
            when (key) {
                "model_name" -> modelName = value
                "is_casual" -> isCasual = value.lowercase() in setOf("true", "yes", "on")
                "colors" -> inColors = true
            }
        }
        val name = modelName ?: return null
        return ColorPreset(name, colors, isCasual)
    }
}
