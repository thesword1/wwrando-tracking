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
        /** UI-only dropdown value; may be a user preset name while [colorPreset] is "Custom". */
        val presetSelection: String = DEFAULT_PRESET,
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
        return state.copy(customColors = custom, colorPreset = preset, presetSelection = CUSTOM_PRESET)
    }

    /** update_color_presets_list: keep the old preset if the new model also has it, else Default. */
    fun presetAfterSwitch(previous: String, presets: Map<String, Map<String, List<Int>>>): String =
        if (previous in presets) previous else DEFAULT_PRESET

    fun presetNames(
        state: State,
        metadata: ModelMetadata,
        userPresetNames: Set<String> = emptySet(),
    ): List<String> =
        listOf(DEFAULT_PRESET, CUSTOM_PRESET) +
            colorPresets(state, metadata).keys.filter { it !in RESERVED_PRESET_NAMES } +
            userPresetNames.sorted().filter { it !in RESERVED_PRESET_NAMES }

    /** Mirror of reset_color_selectors_to_model_default_colors: defaults + preset -> Default. */
    fun resetAllColors(state: State): State =
        state.copy(colorPreset = DEFAULT_PRESET, presetSelection = DEFAULT_PRESET, customColors = emptyMap())

    /**
     * Select a preset from the dropdown. Model presets keep their name in `colorPreset`; a user
     * preset becomes `custom_color_preset="Custom"` with its stored colours, while `presetSelection`
     * keeps the user preset name for the UI. Unknown names leave the state untouched.
     */
    fun selectPreset(
        state: State,
        name: String,
        metadata: ModelMetadata,
        userPresets: Map<String, Map<String, List<Int>>>,
    ): State {
        val modelPresets = colorPresets(state, metadata)
        return when {
            name == DEFAULT_PRESET -> state.copy(colorPreset = DEFAULT_PRESET, presetSelection = DEFAULT_PRESET)
            name == CUSTOM_PRESET -> state.copy(colorPreset = CUSTOM_PRESET, presetSelection = CUSTOM_PRESET)
            name in modelPresets -> state.copy(colorPreset = name, presetSelection = name)
            name in userPresets -> state.copy(
                colorPreset = CUSTOM_PRESET,
                presetSelection = name,
                customColors = userPresets.getValue(name),
            )
            else -> state
        }
    }

    /** Reserved/model preset names are refused; returns a user-facing error message, or null when OK. */
    fun validateUserPresetName(name: String, metadata: ModelMetadata, casual: Boolean): String? {
        val trimmed = name.trim()
        if (trimmed.isEmpty()) return "Enter a preset name."
        if (trimmed in RESERVED_PRESET_NAMES) return "\"$trimmed\" is reserved."
        if (trimmed in metadata.colorPresets(casual)) return "\"$trimmed\" is already a model preset."
        return null
    }

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
}
