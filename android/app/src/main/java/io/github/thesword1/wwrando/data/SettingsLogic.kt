package io.github.thesword1.wwrando.data

/** Pure diff/merge/validation rules for the settings screen. No Android types. */
object SettingsLogic {
    const val DEFAULT_PRESET_NAME = "Default"

    private val PRESET_NAME = Regex("^[A-Za-z0-9 _-]{1,40}$")

    fun normalizePresetName(raw: String): String = raw.trim()

    /** Validates a name for saving as a preset (1-40 chars from [A-Za-z0-9 _-]). */
    fun isValidPresetName(name: String): Boolean = PRESET_NAME.matches(normalizePresetName(name))

    fun defaultOf(option: OptionDef): Any = when (option) {
        is OptionDef.Bool -> option.default
        is OptionDef.Enum -> option.default
        is OptionDef.IntOption -> option.default
        is OptionDef.Multi -> option.default
    }

    fun defaults(schema: List<OptionDef>): Map<String, Any> = schema.associate { it.name to defaultOf(it) }

    /** Drops keys absent from [defaults] and entries equal to their default value. */
    fun diffAgainstDefaults(defaults: Map<String, Any>, values: Map<String, Any>): Map<String, Any> =
        values
            .filterKeys { defaults.containsKey(it) }
            .filter { (name, value) -> defaults[name] != value }

    fun effectiveValues(defaults: Map<String, Any>, diff: Map<String, Any>): Map<String, Any> =
        defaults + diff.filterKeys { defaults.containsKey(it) }

    fun dropUnknown(schemaNames: Set<String>, values: Map<String, Any>): Map<String, Any> =
        values.filterKeys { it in schemaNames }

    fun isValidValue(option: OptionDef, value: Any): Boolean = when (option) {
        is OptionDef.Bool -> value is Boolean
        is OptionDef.Enum -> value is String && value in option.choices
        is OptionDef.IntOption -> value is Int && value >= option.minimum && value <= option.maximum
        is OptionDef.Multi -> value is List<*> && value.all { it is String && it in option.choices }
    }

    fun isModified(current: Map<String, Any>, preset: Map<String, Any>): Boolean = current != preset
}
