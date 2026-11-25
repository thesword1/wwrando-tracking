package io.github.thesword1.wwrando.data

import org.yaml.snakeyaml.LoaderOptions
import org.yaml.snakeyaml.Yaml
import org.yaml.snakeyaml.constructor.SafeConstructor

/** Thrown when a metadata colour value cannot be parsed as 0xRRGGBB. */
class InvalidColorException(message: String) : Exception(message)

/**
 * Parsed player-model metadata, mirroring `customizer.get_model_metadata` (SnakeYAML after the
 * same old-format and tab fixes). A parse error becomes [errorMessage]; the UI then lists the
 * model with its error and hides its colours.
 */
data class ModelMetadata(
    val errorMessage: String? = null,
    val author: String? = null,
    val comment: String? = null,
    val casualClothesOptionText: String = "Casual Clothes",
    val disableCasualClothes: Boolean = false,
    val heroCustomColors: Map<String, IntArray> = emptyMap(),
    val casualCustomColors: Map<String, IntArray> = emptyMap(),
    val heroColorPresets: Map<String, Map<String, IntArray>> = emptyMap(),
    val casualColorPresets: Map<String, Map<String, IntArray>> = emptyMap(),
) {
    fun customColors(isCasual: Boolean): Map<String, IntArray> =
        if (isCasual) casualCustomColors else heroCustomColors

    fun colorPresets(isCasual: Boolean): Map<String, Map<String, IntArray>> =
        if (isCasual) casualColorPresets else heroColorPresets

    companion object {
        private val OLD_FORMAT = Regex("^[ \\t]+\\S[^:\\n]*:[ \\t]+\"?[0-9A-F]{6}\"?[ \\t]*$", setOf(RegexOption.MULTILINE, RegexOption.IGNORE_CASE))
        private val NEW_FORMAT = Regex("^[ \\t]+\\S[^:\\n]*:[ \\t]+0x[0-9A-F]{6}[ \\t]*$", setOf(RegexOption.MULTILINE, RegexOption.IGNORE_CASE))
        private val OLD_FORMAT_SUB = Regex("^([ \\t]+\\S[^:\\n]*:[ \\t]+)\"?([0-9A-F]{6})\"?[ \\t]*$", setOf(RegexOption.MULTILINE, RegexOption.IGNORE_CASE))
        private val HEX_STRING = Regex("^0x([0-9A-F]{6})$")

        private val yaml: Yaml = Yaml(SafeConstructor(LoaderOptions()))

        /** Mirror of customizer.parse_hex_color (accepts "0xRRGGBB" strings and hex ints). */
        fun parseHexColor(value: Any?): IntArray {
            val int = when (value) {
                is String -> {
                    val match = HEX_STRING.matchEntire(value.trim())
                        ?: throw InvalidColorException("invalid color: $value")
                    match.groupValues[1].toInt(16)
                }
                is Int -> value
                is Long -> value.toInt()
                else -> throw InvalidColorException("invalid color: $value")
            }
            if (int < 0 || int > 0xFFFFFF) throw InvalidColorException("invalid color: 0x%06X".format(int))
            return intArrayOf((int shr 16) and 0xFF, (int shr 8) and 0xFF, int and 0xFF)
        }

        fun parse(text: String): ModelMetadata {
            var fixed = text
            if (OLD_FORMAT.containsMatchIn(fixed) && !NEW_FORMAT.containsMatchIn(fixed)) {
                fixed = OLD_FORMAT_SUB.replace(fixed) { m -> "${m.groupValues[1]}0x${m.groupValues[2]}" }
            }
            fixed = fixed.replace("\t", "  ")

            val loaded: Any? = try {
                yaml.load<Any?>(fixed)
            } catch (e: Exception) {
                return ModelMetadata(errorMessage = e.message ?: "metadata parse failed")
            }
            if (loaded !is Map<*, *>) return ModelMetadata(errorMessage = "metadata is not a mapping")
            val map = @Suppress("UNCHECKED_CAST") (loaded as Map<String, Any?>)

            val hero = parseColorMap(map["hero_custom_colors"])
                ?: return ModelMetadata(errorMessage = colorError("hero_custom_colors", map["hero_custom_colors"]))
            val casual = parseColorMap(map["casual_custom_colors"])
                ?: return ModelMetadata(errorMessage = colorError("casual_custom_colors", map["casual_custom_colors"]))
            val heroPresets = parsePresetMap(map["hero_color_presets"])
                ?: return ModelMetadata(errorMessage = presetError("hero_color_presets", map["hero_color_presets"]))
            val casualPresets = parsePresetMap(map["casual_color_presets"])
                ?: return ModelMetadata(errorMessage = presetError("casual_color_presets", map["casual_color_presets"]))

            return ModelMetadata(
                author = map["author"] as? String,
                comment = map["comment"] as? String,
                casualClothesOptionText = (map["casual_clothes_option_text"] as? String) ?: "Casual Clothes",
                disableCasualClothes = map["disable_casual_clothes"] as? Boolean ?: false,
                heroCustomColors = hero,
                casualCustomColors = casual,
                heroColorPresets = heroPresets,
                casualColorPresets = casualPresets,
            )
        }

        private fun parseColorMap(value: Any?): Map<String, IntArray>? {
            if (value == null) return emptyMap()
            if (value !is Map<*, *>) return null
            val out = LinkedHashMap<String, IntArray>()
            for ((k, v) in value) {
                if (k !is String) return null
                out[k] = try {
                    parseHexColor(v)
                } catch (e: InvalidColorException) {
                    return null
                }
            }
            return out
        }

        private fun parsePresetMap(value: Any?): Map<String, Map<String, IntArray>>? {
            if (value == null) return emptyMap()
            if (value !is Map<*, *>) return null
            val out = LinkedHashMap<String, Map<String, IntArray>>()
            for ((k, v) in value) {
                if (k !is String) return null
                val preset = parseColorMap(v) ?: return null
                out[k] = preset
            }
            return out
        }

        private fun colorError(key: String, value: Any?) = "invalid base colors in $key: $value"
        private fun presetError(key: String, value: Any?) = "invalid preset colors in $key: $value"
    }
}
