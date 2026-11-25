package io.github.thesword1.wwrando.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OptionDependenciesTest {

    private val defaults: Map<String, Any> = mapOf(
        "progression_dungeons" to true,
        "progression_puzzle_secret_caves" to false,
        "progression_combat_secret_caves" to false,
        "required_bosses" to false,
        "num_required_bosses" to 0,
        "included_dungeons" to emptyList<String>(),
        "excluded_dungeons" to emptyList<String>(),
        "randomize_dungeon_entrances" to false,
        "randomize_miniboss_entrances" to false,
        "randomize_boss_entrances" to false,
        "randomize_secret_cave_entrances" to false,
        "randomize_secret_cave_inner_entrances" to false,
        "randomize_fairy_fountain_entrances" to false,
        "mix_entrances" to false,
        "num_location_hints" to 10,
        "prioritize_remote_hints" to false,
    )

    @Test
    fun `required bosses depends on progression dungeons`() {
        assertTrue(OptionDependencies.isVisible("required_bosses", defaults))
        assertFalse(
            OptionDependencies.isVisible(
                "required_bosses",
                defaults + ("progression_dungeons" to false),
            ),
        )
    }

    @Test
    fun `required boss dependents hide when required bosses is off`() {
        val effective = defaults + ("required_bosses" to false)
        assertFalse(OptionDependencies.isVisible("num_required_bosses", effective))
        assertFalse(OptionDependencies.isVisible("included_dungeons", effective))
        assertFalse(OptionDependencies.isVisible("excluded_dungeons", effective))
        assertTrue(OptionDependencies.isVisible("num_required_bosses", defaults + ("required_bosses" to true)))
    }

    @Test
    fun `inner secret cave entrances need both cave types`() {
        assertFalse(OptionDependencies.isVisible("randomize_secret_cave_inner_entrances", defaults))
        val both = defaults + ("progression_puzzle_secret_caves" to true) + ("progression_combat_secret_caves" to true)
        assertTrue(OptionDependencies.isVisible("randomize_secret_cave_inner_entrances", both))
    }

    @Test
    fun `mix entrances needs a dungeon and a non-dungeon entrance`() {
        assertFalse(OptionDependencies.isVisible("mix_entrances", defaults))
        val mixed = defaults + ("randomize_dungeon_entrances" to true) + ("randomize_fairy_fountain_entrances" to true)
        assertTrue(OptionDependencies.isVisible("mix_entrances", mixed))
    }

    @Test
    fun `prioritize remote hints needs location hints`() {
        assertFalse(OptionDependencies.isVisible("prioritize_remote_hints", defaults + ("num_location_hints" to 0)))
        assertTrue(OptionDependencies.isVisible("prioritize_remote_hints", defaults + ("num_location_hints" to 5)))
    }

    @Test
    fun `sanitized resets hidden options to defaults`() {
        val effective = defaults + ("required_bosses" to false) + ("num_required_bosses" to 2)
        val clean = OptionDependencies.sanitized(effective, defaults)
        assertFalse(clean.getValue("num_required_bosses") == 2)
        assertTrue(clean.getValue("num_required_bosses") == defaults.getValue("num_required_bosses"))
    }
}
