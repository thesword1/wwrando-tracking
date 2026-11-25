package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsLogicTest {

    private val schema = listOf<OptionDef>(
        OptionDef.Bool("a", "g", "d", true, true),
        OptionDef.Enum("b", "g", "d", true, "x", listOf("x", "y"), listOf("X", "Y")),
        OptionDef.IntOption("c", "g", "d", true, 5, 0, 10),
        OptionDef.Multi("m", "g", "d", true, emptyList(), listOf("p", "q")),
        OptionDef.ItemList("gear", "g", "d", true, emptyList(), listOf("Bombs", "Progressive Bow"), mapOf("Bombs" to 1, "Progressive Bow" to 3)),
    )
    private val defaults = SettingsLogic.defaults(schema)

    @Test
    fun `diff keeps only non-default values and drops stale keys`() {
        val diff = SettingsLogic.diffAgainstDefaults(
            defaults,
            mapOf("a" to false, "b" to "x", "c" to 5, "m" to listOf("p"), "stale" to 1),
        )
        assertEquals(mapOf("a" to false, "m" to listOf("p")), diff)
    }

    @Test
    fun `effective values merge defaults with the diff`() {
        val effective = SettingsLogic.effectiveValues(defaults, mapOf("a" to false, "stale" to 1))
        assertEquals(false, effective["a"])
        assertEquals("x", effective["b"])
        assertEquals(5, effective["c"])
        assertEquals(false, effective.containsKey("stale"))
    }

    @Test
    fun `preset name validation`() {
        assertTrue(SettingsLogic.isValidPresetName("My Preset-1"))
        assertTrue(SettingsLogic.isValidPresetName("  padded  "))
        assertFalse(SettingsLogic.isValidPresetName(""))
        assertFalse(SettingsLogic.isValidPresetName("a!b"))
        assertFalse(SettingsLogic.isValidPresetName("a".repeat(41)))
    }

    @Test
    fun `modified flag compares current against the loaded preset`() {
        assertFalse(SettingsLogic.isModified(emptyMap(), emptyMap()))
        assertTrue(SettingsLogic.isModified(mapOf("a" to false), emptyMap()))
        assertFalse(SettingsLogic.isModified(mapOf("a" to false), mapOf("a" to false)))
        assertTrue(SettingsLogic.isModified(mapOf("a" to false), mapOf("a" to true)))
    }

    @Test
    fun `dropUnknown removes stale keys`() {
        assertEquals(
            mapOf("a" to true),
            SettingsLogic.dropUnknown(setOf("a"), mapOf("a" to true, "z" to 1)),
        )
    }

    @Test
    fun `value validation per type`() {
        assertTrue(SettingsLogic.isValidValue(schema[0], false))
        assertFalse(SettingsLogic.isValidValue(schema[0], 0))
        assertTrue(SettingsLogic.isValidValue(schema[1], "y"))
        assertFalse(SettingsLogic.isValidValue(schema[1], "z"))
        assertTrue(SettingsLogic.isValidValue(schema[2], 10))
        assertFalse(SettingsLogic.isValidValue(schema[2], 11))
        assertTrue(SettingsLogic.isValidValue(schema[3], listOf("p")))
        assertFalse(SettingsLogic.isValidValue(schema[3], listOf("p", "r")))
        assertTrue(SettingsLogic.isValidValue(schema[4], listOf("Bombs", "Progressive Bow", "Progressive Bow")))
        assertFalse(SettingsLogic.isValidValue(schema[4], listOf("Bombs", "Bombs")))
        assertFalse(SettingsLogic.isValidValue(schema[4], listOf("Progressive Bow", "Progressive Bow", "Progressive Bow", "Progressive Bow")))
    }
}
