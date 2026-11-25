package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StartingItemsLogicTest {

    private val option = OptionDef.ItemList(
        name = "starting_gear",
        group = "Starting items",
        description = "d",
        permalink = true,
        default = emptyList(),
        choices = listOf("Bombs", "Hurricane Spin", "Progressive Bow", "Progressive Sword"),
        maxCounts = mapOf("Bombs" to 1, "Hurricane Spin" to 1, "Progressive Bow" to 3, "Progressive Sword" to 3),
    )

    @Test
    fun `swordless removes hurricane spin and progressive sword`() {
        assertEquals(
            setOf("Hurricane Spin", "Progressive Sword"),
            StartingItemsLogic.excludedItems(OptionDependencies.SWORDLESS),
        )
        val filtered = StartingItemsLogic.filteredStarting(
            listOf("Bombs", "Hurricane Spin", "Progressive Sword"),
            OptionDependencies.SWORDLESS,
        )
        assertEquals(listOf("Bombs"), filtered)
    }

    @Test
    fun `no starting sword and swords optional remove progressive sword only`() {
        listOf(OptionDependencies.NO_STARTING_SWORD, OptionDependencies.SWORDS_OPTIONAL).forEach { mode ->
            assertEquals(
                setOf("Progressive Sword"),
                StartingItemsLogic.excludedItems(mode),
            )
        }
        assertEquals(
            emptySet<String>(),
            StartingItemsLogic.excludedItems("Start with Hero's Sword"),
        )
    }

    @Test
    fun `available counts respect max counts and current list`() {
        val available = StartingItemsLogic.availableCounts(
            option,
            startingGear = listOf("Progressive Bow", "Progressive Bow"),
            swordMode = "Start with Hero's Sword",
        )
        assertEquals(1, available["Progressive Bow"])
        assertEquals(1, available["Bombs"])
        assertEquals(3, available["Progressive Sword"])
        assertEquals(1, available["Hurricane Spin"])
    }

    @Test
    fun `available counts exclude sword mode filtered items`() {
        val available = StartingItemsLogic.availableCounts(
            option,
            startingGear = emptyList(),
            swordMode = OptionDependencies.SWORDLESS,
        )
        assertFalse(available.containsKey("Hurricane Spin"))
        assertFalse(available.containsKey("Progressive Sword"))
    }

    @Test
    fun `health label matches desktop`() {
        assertEquals("Current Starting Health: 3 hearts", StartingItemsLogic.healthLabel(0, 3))
        assertEquals("Current Starting Health: 3 hearts and 1 piece", StartingItemsLogic.healthLabel(1, 3))
        assertEquals("Current Starting Health: 4 hearts and 2 pieces", StartingItemsLogic.healthLabel(2, 4))
    }
}
