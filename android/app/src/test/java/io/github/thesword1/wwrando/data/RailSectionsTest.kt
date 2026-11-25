package io.github.thesword1.wwrando.data

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RailSectionsTest {

    private val schema = OptionsSchema.parse(readRealAsset())
    private val names = schema.map { it.name }.toSet()

    @Test
    fun `customize options are excluded from preset scope`() {
        assertTrue(RailSections.customizeOptions.all { RailSections.isCustomize(it) })
        assertTrue(RailSections.customizeOptions.all { !RailSections.isPresetScoped(it) })
        assertTrue(schema.filter { !RailSections.isCustomize(it.name) }.all { RailSections.isPresetScoped(it.name) })
    }

    @Test
    fun `non-schema customize keys can never enter presets`() {
        // custom_player_model / custom_color_preset / custom_colors are not schema options, so the
        // preset-scoped current.json (which only stores schema-validated options) can never hold them.
        val nonSchema = setOf("custom_player_model", "custom_color_preset", "custom_colors")
        assertTrue(nonSchema.all { it !in names })
    }

    @Test
    fun `every schema option is assigned to exactly one section`() {
        val assigned = RailSections.allAssigned()
        assertEquals(assigned.size, assigned.toSet().size)
        assertEquals(names, assigned.toSet())
        // Seed is not a schema option, so it can never be in presets.
        assertFalse(names.contains("seed"))
    }

    @Test
    fun `starting items and logic tweaks are covered`() {
        assertTrue(RailSections.startingItemsOptions.contains("starting_gear"))
        assertTrue(RailSections.startingItemsOptions.contains("starting_hcs"))
        assertTrue(RailSections.startingItemsOptions.contains("starting_pohs"))
        assertTrue(RailSections.startingItemsOptions.contains("num_extra_starting_items"))
        assertTrue(RailSections.logicAdvancedGroups.flatMap { it.options }.contains("randomize_enemies"))
        assertTrue(RailSections.tweaksGroups.flatMap { it.options }.contains("in_game_tracker"))
    }

    private fun readRealAsset(): String {
        val candidates = listOf(
            "src/main/assets/options_schema.json",
            "../app/src/main/assets/options_schema.json",
            "android/app/src/main/assets/options_schema.json",
        )
        val file = candidates.map(::File).firstOrNull { it.isFile }
            ?: error("cannot find options_schema.json from ${System.getProperty("user.dir")}")
        return file.readText()
    }
}
