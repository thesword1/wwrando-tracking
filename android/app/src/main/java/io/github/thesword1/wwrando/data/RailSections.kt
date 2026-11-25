package io.github.thesword1.wwrando.data

/**
 * Pure layout of the redesigned Android rail. Option names are assigned here (not derived from the
 * schema `group`) because the redesign moves a few options (triforce shards into Logic, enemy rando
 * into Logic > Advanced) and splits the old "App"/tracker handling. This is unit-tested for
 * coverage: every schema option must be assigned to exactly one section or to Customize.
 */
object RailSections {
    data class Group(val title: String, val options: List<String>)

    /** Customize settings persist separately and are deliberately NOT in presets (PLAN 6). */
    val customizeOptions: Set<String> = setOf(
        "player_in_casual_clothes",
        "disable_custom_player_voice",
        "disable_custom_player_items",
    )

    val logicGroups: List<Group> = listOf(
        Group(
            "Progression Locations",
            listOf(
                "progression_dungeons",
                "progression_great_fairies",
                "progression_puzzle_secret_caves",
                "progression_combat_secret_caves",
                "progression_short_sidequests",
                "progression_long_sidequests",
                "progression_spoils_trading",
                "progression_minigames",
                "progression_free_gifts",
                "progression_mail",
                "progression_platforms_rafts",
                "progression_submarines",
                "progression_eye_reef_chests",
                "progression_big_octos_gunboats",
                "progression_triforce_charts",
                "progression_treasure_charts",
                "progression_expensive_purchases",
                "progression_misc",
                "progression_tingle_chests",
                "progression_battlesquid",
                "progression_savage_labyrinth",
                "progression_island_puzzles",
                "progression_dungeon_secrets",
            ),
        ),
        Group(
            "Item Randomizer Modes",
            listOf(
                "sword_mode",
                "randomize_smallkeys",
                "randomize_bigkeys",
                "randomize_mapcompass",
                "num_starting_triforce_shards",
                "chest_type_matches_contents",
                "trap_chests",
            ),
        ),
        Group(
            "Difficulty",
            listOf("hero_mode", "logic_obscurity", "logic_precision", "enable_tuner_logic"),
        ),
        Group(
            "Entrance Randomizer",
            listOf(
                "randomize_dungeon_entrances",
                "randomize_secret_cave_entrances",
                "randomize_miniboss_entrances",
                "randomize_boss_entrances",
                "randomize_secret_cave_inner_entrances",
                "randomize_fairy_fountain_entrances",
                "mix_entrances",
            ),
        ),
        Group(
            "Other Randomizers",
            listOf("randomize_enemy_palettes", "randomize_starting_island", "randomize_charts"),
        ),
    )

    /** Less-used logic settings, matching the desktop's advanced tab. */
    val logicAdvancedGroups: List<Group> = listOf(
        Group(
            "Required Bosses",
            listOf("required_bosses", "num_required_bosses", "included_dungeons", "excluded_dungeons"),
        ),
        Group("Enemy Randomization", listOf("randomize_enemies")),
    )

    val tweaksGroups: List<Group> = listOf(
        Group("Meta", listOf("do_not_generate_spoiler_log", "dry_run")),
        Group("In-Game Tracker", listOf("in_game_tracker")),
        Group(
            "Convenience Tweaks",
            listOf(
                "swift_sail",
                "instant_text_boxes",
                "reveal_full_sea_chart",
                "add_shortcut_warps_between_dungeons",
                "skip_rematch_bosses",
                "invert_camera_x_axis",
                "invert_sea_compass_x_axis",
                "remove_title_and_ending_videos",
                "remove_music",
                "switch_targeting_mode",
            ),
        ),
        Group(
            "Hints",
            listOf(
                "hoho_hints",
                "fishmen_hints",
                "korl_hints",
                "num_item_hints",
                "num_location_hints",
                "prioritize_remote_hints",
                "num_barren_hints",
                "num_path_hints",
                "cryptic_hints",
                "hint_importance",
            ),
        ),
    )

    val startingItemsOptions: List<String> = listOf(
        "starting_gear",
        "starting_hcs",
        "starting_pohs",
        "num_extra_starting_items",
    )

    fun isCustomize(name: String): Boolean = name in customizeOptions

    /** Preset scope = Logic + Tweaks + Starting items. Seed and permalink are not schema options. */
    fun isPresetScoped(name: String): Boolean = !isCustomize(name)

    fun allAssigned(): List<String> =
        (logicGroups + logicAdvancedGroups + tweaksGroups).flatMap { it.options } +
            startingItemsOptions + customizeOptions.toList()
}
