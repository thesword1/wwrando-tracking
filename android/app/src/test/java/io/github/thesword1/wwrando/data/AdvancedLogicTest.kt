package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AdvancedLogicTest {

    private val schema = listOf<OptionDef>(
        OptionDef.Bool("a", "g", "d", true, true),
        OptionDef.Enum("b", "g", "d", true, "x", listOf("x", "y"), listOf("X", "Y")),
        OptionDef.IntOption("c", "g", "d", true, 5, 0, 10),
        OptionDef.ItemList(
            "gear",
            "g",
            "d",
            true,
            emptyList(),
            listOf("Bombs", "Progressive Bow"),
            mapOf("Bombs" to 1, "Progressive Bow" to 3),
        ),
        OptionDef.Bool("player_in_casual_clothes", "g", "d", true, false),
    )
    private val schemaByName = schema.associateBy { it.name }
    private val defaults = SettingsLogic.defaults(schema)

    @Test
    fun `decoded settings become the stored diff dropping defaults and non-scoped names`() {
        val decoded = mapOf(
            "a" to false,
            "b" to "x",
            "c" to 5,
            "gear" to listOf("Bombs"),
            "player_in_casual_clothes" to true,
            "unknown_option" to 123,
        )
        assertEquals(
            mapOf("a" to false, "gear" to listOf("Bombs")),
            AdvancedLogic.decodedDiff(decoded, schemaByName, defaults),
        )
    }

    @Test
    fun `decoded settings drop invalid values`() {
        val decoded = mapOf(
            "a" to "not-a-bool",
            "b" to "z",
            "c" to 99,
            "gear" to listOf("Bombs", "Bombs"),
        )
        assertEquals(emptyMap<String, Any>(), AdvancedLogic.decodedDiff(decoded, schemaByName, defaults))
    }

    @Test
    fun `parses the last JSON line ignoring noise before it`() {
        val result = AdvancedLogic.parseResult(
            "startup warning\n{\"ok\":true,\"seed\":\"s\",\"permalink\":\"p\",\"settings\":{\"a\":true,\"b\":[\"x\",\"y\"]}}\n",
        )!!
        assertTrue(result.ok)
        assertEquals("s", result.seed)
        assertEquals("p", result.permalink)
        assertEquals(mapOf("a" to true, "b" to listOf("x", "y")), result.settings)
    }

    @Test
    fun `parses an ok false error line`() {
        val result = AdvancedLogic.parseResult(
            """{"ok":false,"step":"permalink","error":"different version/commit"}""",
        )!!
        assertFalse(result.ok)
        assertEquals("different version/commit", result.error)
    }

    @Test
    fun `returns null for blank or non-json stdout`() {
        assertNull(AdvancedLogic.parseResult(""))
        assertNull(AdvancedLogic.parseResult("   \n  "))
        assertNull(AdvancedLogic.parseResult("no json here"))
    }
}
