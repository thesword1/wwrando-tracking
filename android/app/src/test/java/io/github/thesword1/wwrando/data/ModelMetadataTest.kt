package io.github.thesword1.wwrando.data

import java.io.File
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelMetadataTest {

    private fun readAsset(name: String): String {
        val candidates = listOf(
            "assets/$name",
            "../assets/$name",
            "../../assets/$name",
        )
        val file = candidates.map(::File).firstOrNull { it.isFile }
            ?: error("cannot find $name from ${System.getProperty("user.dir")}")
        return file.readText()
    }

    @Test
    fun `link metadata parses colors and presets`() {
        val meta = ModelMetadata.parse(readAsset("link_metadata.txt"))
        assertNull(meta.errorMessage)
        assertArrayEquals(intArrayOf(255, 239, 16), meta.heroCustomColors["Hair"])
        assertArrayEquals(intArrayOf(74, 117, 173), meta.casualCustomColors["Shirt"])
        assertTrue(meta.heroColorPresets.containsKey("Dark Link"))
        assertArrayEquals(intArrayOf(0, 0, 0), meta.heroColorPresets.getValue("Dark Link").getValue("Hair"))
        assertTrue(meta.heroColorPresets.containsKey("Green Link"))
        assertEquals(false, meta.disableCasualClothes)
    }

    @Test
    fun `old format colors get the 0x prefix and tabs are accepted`() {
        val meta = ModelMetadata.parse(
            "hero_custom_colors:\n" +
                "\tHair: FFEF10\n" +
                "\tSkin: \"F7DB9C\"\n" +
                "casual_custom_colors:\n" +
                "\tShirt: 4A75AD\n",
        )
        assertNull(meta.errorMessage)
        assertArrayEquals(intArrayOf(255, 239, 16), meta.heroCustomColors["Hair"])
        assertArrayEquals(intArrayOf(247, 219, 156), meta.heroCustomColors["Skin"])
        assertArrayEquals(intArrayOf(74, 117, 173), meta.casualCustomColors["Shirt"])
    }

    @Test
    fun `parse error becomes errorMessage`() {
        val meta = ModelMetadata.parse("hero_custom_colors: [unclosed")
        assertNotNull(meta.errorMessage)
        assertTrue(meta.heroCustomColors.isEmpty())
    }

    @Test
    fun `invalid base color becomes errorMessage`() {
        val meta = ModelMetadata.parse("hero_custom_colors:\n  Hair: notacolor\n")
        assertNotNull(meta.errorMessage)
    }

    @Test
    fun `parse hex color accepts string and int`() {
        assertArrayEquals(intArrayOf(255, 239, 16), ModelMetadata.parseHexColor("0xFFEF10"))
        assertArrayEquals(intArrayOf(255, 239, 16), ModelMetadata.parseHexColor(0xFFEF10))
    }
}
