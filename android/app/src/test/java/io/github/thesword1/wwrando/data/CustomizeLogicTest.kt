package io.github.thesword1.wwrando.data

import kotlin.random.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CustomizeLogicTest {

    private val metadata = ModelMetadata.parse(
        "hero_custom_colors:\n  Hair: 0xFFEF10\n  Tunic: 0x5AB24A\n" +
            "casual_custom_colors:\n  Shirt: 0x4A75AD\n" +
            "hero_color_presets:\n  Dark Link:\n    Hair: 0x000000\n",
    )

    private fun defaults() = CustomizeLogic.defaultColors(CustomizeLogic.State(), metadata)

    @Test
    fun `default preset returns model base color`() {
        val state = CustomizeLogic.State()
        assertEquals(listOf(255, 239, 16), CustomizeLogic.getColor(state, metadata, defaults(), "Hair"))
    }

    @Test
    fun `custom preset returns stored custom color`() {
        val state = CustomizeLogic.State(colorPreset = CustomizeLogic.CUSTOM_PRESET, customColors = mapOf("Hair" to listOf(1, 2, 3)))
        assertEquals(listOf(1, 2, 3), CustomizeLogic.getColor(state, metadata, defaults(), "Hair"))
        assertEquals(listOf(90, 178, 74), CustomizeLogic.getColor(state, metadata, defaults(), "Tunic"))
    }

    @Test
    fun `named preset returns preset color`() {
        val state = CustomizeLogic.State(colorPreset = "Dark Link")
        assertEquals(listOf(0, 0, 0), CustomizeLogic.getColor(state, metadata, defaults(), "Hair"))
        assertEquals(listOf(90, 178, 74), CustomizeLogic.getColor(state, metadata, defaults(), "Tunic"))
    }

    @Test
    fun `changing a color from a preset switches to Custom and copies the others`() {
        val state = CustomizeLogic.State(colorPreset = "Dark Link")
        val next = CustomizeLogic.applyColorChange(state, metadata, defaults(), "Hair", listOf(9, 9, 9))
        assertEquals(CustomizeLogic.CUSTOM_PRESET, next.colorPreset)
        assertEquals(listOf(9, 9, 9), next.customColors["Hair"])
        // The other colour was copied from the "Dark Link" preset's effective colour (Tunic has no
        // preset entry, so it keeps the model base).
        assertEquals(listOf(90, 178, 74), next.customColors["Tunic"])
    }

    @Test
    fun `casual clothes selects the casual color set`() {
        val state = CustomizeLogic.State(casualClothes = true)
        val casualDefaults = CustomizeLogic.defaultColors(state, metadata)
        assertEquals(listOf(74, 117, 173), CustomizeLogic.getColor(state, metadata, casualDefaults, "Shirt"))
    }

    @Test
    fun `preset after switch keeps a shared preset name`() {
        val presets = CustomizeLogic.colorPresets(CustomizeLogic.State(), metadata)
        assertEquals("Dark Link", CustomizeLogic.presetAfterSwitch("Dark Link", presets))
        assertEquals(CustomizeLogic.DEFAULT_PRESET, CustomizeLogic.presetAfterSwitch("Missing", presets))
    }

    @Test
    fun `randomize all together switches to Custom and recolors every color`() {
        val state = CustomizeLogic.State()
        val next = CustomizeLogic.randomizeAllTogether(state, metadata, Random(42))
        assertEquals(CustomizeLogic.CUSTOM_PRESET, next.colorPreset)
        assertEquals(setOf("Hair", "Tunic"), next.customColors.keys)
        assertTrue(next.customColors["Hair"] != listOf(255, 239, 16))
    }

    @Test
    fun `reset one on default is a no-op`() {
        val state = CustomizeLogic.State()
        assertEquals(state, CustomizeLogic.resetOne(state, metadata, defaults(), "Hair"))
    }

    @Test
    fun `reset all colors clears custom colors and selects default`() {
        val state = CustomizeLogic.State(
            colorPreset = CustomizeLogic.CUSTOM_PRESET,
            customColors = mapOf("Hair" to listOf(1, 2, 3)),
            presetSelection = "My preset",
        )
        val next = CustomizeLogic.resetAllColors(state)
        assertEquals(CustomizeLogic.DEFAULT_PRESET, next.colorPreset)
        assertEquals(CustomizeLogic.DEFAULT_PRESET, next.presetSelection)
        assertTrue(next.customColors.isEmpty())
    }

    @Test
    fun `selecting a user preset becomes Custom with the selection keeping its name`() {
        val state = CustomizeLogic.State()
        val userPresets = mapOf("My look" to mapOf("Hair" to listOf(9, 9, 9), "Tunic" to listOf(8, 8, 8)))
        val next = CustomizeLogic.selectPreset(state, "My look", metadata, userPresets)
        assertEquals(CustomizeLogic.CUSTOM_PRESET, next.colorPreset)
        assertEquals("My look", next.presetSelection)
        assertEquals(listOf(9, 9, 9), next.customColors["Hair"])
    }

    @Test
    fun `selecting a model preset keeps the name in both fields`() {
        val state = CustomizeLogic.State()
        val next = CustomizeLogic.selectPreset(state, "Dark Link", metadata, emptyMap())
        assertEquals("Dark Link", next.colorPreset)
        assertEquals("Dark Link", next.presetSelection)
    }

    @Test
    fun `user preset names refuse reserved and model preset names`() {
        assertTrue(CustomizeLogic.validateUserPresetName("Default", metadata, false) != null)
        assertTrue(CustomizeLogic.validateUserPresetName("Dark Link", metadata, false) != null)
        assertTrue(CustomizeLogic.validateUserPresetName("   ", metadata, false) != null)
        assertEquals(null, CustomizeLogic.validateUserPresetName("My look", metadata, false))
    }

    @Test
    fun `preset names append user presets after model presets`() {
        val meta = ModelMetadata.parse(
            "hero_custom_colors:\n  Hair: 0xFF0000\n" +
                "hero_color_presets:\n  Good: {Hair: 0x0000FF}\n",
        )
        val names = CustomizeLogic.presetNames(
            CustomizeLogic.State(),
            meta,
            setOf("Zebra", "Apple"),
        )
        assertEquals(listOf("Default", "Custom", "Good", "Apple", "Zebra"), names)
    }

    @Test
    fun `reserved preset names are filtered out`() {
        val meta = ModelMetadata.parse(
            "hero_custom_colors:\n  Hair: 0xFF0000\n" +
                "hero_color_presets:\n  Default: {Hair: 0x000000}\n  Custom: {Hair: 0x000000}\n  Good: {Hair: 0x0000FF}\n",
        )
        val names = CustomizeLogic.presetNames(CustomizeLogic.State(), meta)
        assertEquals(listOf("Default", "Custom", "Good"), names)
    }
}
