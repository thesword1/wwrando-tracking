package io.github.thesword1.wwrando.data

/**
 * Pure copies of the desktop's option-dependency rules
 * (`wwr_ui/randomizer_window.py ensure_valid_combination_of_options`). On Android a dependent
 * option is hidden instead of greyed out, and a hidden option sends its default value.
 */
object OptionDependencies {
    const val SWORD_MODE = "sword_mode"
    const val SWORDLESS = "Swordless"
    const val NO_STARTING_SWORD = "No Starting Sword"
    const val SWORDS_OPTIONAL = "Swords Optional"

    /** Option names that are hidden under the current effective values. */
    fun hiddenNames(effective: Map<String, Any>): Set<String> = buildSet {
        val progressionDungeons = effective["progression_dungeons"] as? Boolean ?: false
        if (!progressionDungeons) add("required_bosses")

        val requiredBosses = effective["required_bosses"] as? Boolean ?: false
        if (!requiredBosses) {
            add("num_required_bosses")
            add("included_dungeons")
            add("excluded_dungeons")
        }

        val puzzleCaves = effective["progression_puzzle_secret_caves"] as? Boolean ?: false
        val combatCaves = effective["progression_combat_secret_caves"] as? Boolean ?: false
        if (!(puzzleCaves && combatCaves)) add("randomize_secret_cave_inner_entrances")

        val numLocationHints = effective["num_location_hints"] as? Int ?: 0
        if (numLocationHints == 0) add("prioritize_remote_hints")

        val dungeonEntrances = listOf(
            "randomize_dungeon_entrances",
            "randomize_miniboss_entrances",
            "randomize_boss_entrances",
        ).any { effective[it] as? Boolean == true }
        val nonDungeonEntrances = listOf(
            "randomize_secret_cave_entrances",
            "randomize_secret_cave_inner_entrances",
            "randomize_fairy_fountain_entrances",
        ).any { effective[it] as? Boolean == true }
        if (!(dungeonEntrances && nonDungeonEntrances)) add("mix_entrances")
    }

    fun isVisible(name: String, effective: Map<String, Any>): Boolean = name !in hiddenNames(effective)

    /** Returns effective values with every hidden option reset to its default (as desktop does). */
    fun sanitized(effective: Map<String, Any>, defaults: Map<String, Any>): Map<String, Any> {
        val hidden = hiddenNames(effective)
        if (hidden.isEmpty()) return effective
        return effective.mapValues { (name, value) ->
            if (name in hidden) defaults.getValue(name) else value
        }
    }
}
