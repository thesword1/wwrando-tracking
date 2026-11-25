package io.github.thesword1.wwrando.data

import kotlin.random.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SeedNameGeneratorTest {

    @Test
    fun `capitalizes only the first letter`() {
        assertEquals("Able", SeedNameGenerator.capitalizeFirstLetter("able"))
        assertEquals("Able9", SeedNameGenerator.capitalizeFirstLetter("able9"))
        assertEquals("123Abc", SeedNameGenerator.capitalizeFirstLetter("123abc"))
    }

    @Test
    fun `generates adjective adjective noun shape`() {
        val name = SeedNameGenerator.generate(
            adjectives = listOf("able", "bold"),
            nouns = listOf("boat"),
            names = listOf("link"),
            random = Random(1),
        )
        assertTrue(name.isNotBlank())
        assertEquals(3, name.count { it.isUpperCase() })
    }
}
