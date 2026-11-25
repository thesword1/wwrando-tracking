package io.github.thesword1.wwrando.data

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OptionsSchemaTest {

    private val fixture = """
        {
          "options": [
            {"name": "progression_dungeons", "group": "Progress locations", "type": "bool",
             "default": true, "description": "d", "permalink": true},
            {"name": "sword_mode", "group": "Modes", "type": "enum",
             "default": "Start with Hero's Sword", "description": "d", "permalink": true,
             "choices": ["Start with Hero's Sword", "Swordless"],
             "choice_descriptions": ["A", "B"]},
            {"name": "num_item_hints", "group": "Hints", "type": "int",
             "default": 15, "description": "d", "minimum": 0, "maximum": 15, "permalink": true},
            {"name": "included_dungeons", "group": "Modes", "type": "multi",
             "default": [], "description": "d", "permalink": true,
             "choices": ["Earth Temple", "Wind Temple"]},
            {"name": "starting_gear", "group": "Starting items", "type": "itemlist",
             "default": [], "description": "d", "permalink": true,
             "choices": ["Bombs", "Progressive Bow"],
             "max_counts": {"Bombs": 1, "Progressive Bow": 3}}
          ],
          "skipped": ["custom_player_model"]
        }
    """.trimIndent()

    @Test
    fun `parses a small fixture into sealed option defs`() {
        val schema = OptionsSchema.parse(fixture)

        assertEquals(5, schema.size)
        val dungeons = schema[0] as OptionDef.Bool
        assertTrue(dungeons.default)
        val sword = schema[1] as OptionDef.Enum
        assertEquals(listOf("Start with Hero's Sword", "Swordless"), sword.choices)
        assertEquals(listOf("A", "B"), sword.choiceDescriptions)
        val hints = schema[2] as OptionDef.IntOption
        assertEquals(0, hints.minimum)
        assertEquals(15, hints.maximum)
        val included = schema[3] as OptionDef.Multi
        assertEquals(listOf("Earth Temple", "Wind Temple"), included.choices)
        assertEquals(emptyList<String>(), included.default)
        val gear = schema[4] as OptionDef.ItemList
        assertEquals(3, gear.maxCounts["Progressive Bow"])
        assertEquals(1, gear.maxCounts["Bombs"])
        assertEquals(emptyList<String>(), gear.default)
    }

    @Test
    fun `parses the real committed asset`() {
        val schema = OptionsSchema.parse(readRealAsset())

        assertTrue(schema.size >= 70)
        assertTrue(schema.all { it.name.isNotBlank() && it.group.isNotBlank() })
        assertTrue(schema.none { it.name == "custom_player_model" })
        schema.filterIsInstance<OptionDef.Enum>().forEach {
            assertEquals(it.name, it.choices.size, it.choiceDescriptions.size)
        }
        schema.filterIsInstance<OptionDef.IntOption>().forEach {
            assertTrue(it.name, it.minimum <= it.maximum)
        }
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
