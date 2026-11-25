package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ColorPresetStoreTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun store(): ColorPresetStore = ColorPresetStore(tmp.root)

    @Test
    fun `user preset saves and reads back per model and casual prefix`() {
        val store = store()
        store.save("Link", casual = false, "Red Link", mapOf("Hair" to listOf(255, 0, 0)))
        store.save("Link", casual = true, "Blue Shirt", mapOf("Shirt" to listOf(0, 0, 255)))

        assertEquals(mapOf("Red Link" to mapOf("Hair" to listOf(255, 0, 0))), store.presets("Link", false))
        assertEquals(mapOf("Blue Shirt" to mapOf("Shirt" to listOf(0, 0, 255))), store.presets("Link", true))
        assertTrue(store.presets("Other", false).isEmpty())
    }

    @Test
    fun `saving an existing user preset name overwrites it`() {
        val store = store()
        store.save("Link", false, "Mine", mapOf("Hair" to listOf(1, 2, 3)))
        store.save("Link", false, "Mine", mapOf("Hair" to listOf(9, 9, 9)))

        assertEquals(mapOf("Mine" to mapOf("Hair" to listOf(9, 9, 9))), store.presets("Link", false))
    }

    @Test
    fun `deleting a user preset removes only that name`() {
        val store = store()
        store.save("Link", false, "Keep", mapOf("Hair" to listOf(1, 1, 1)))
        store.save("Link", false, "Drop", mapOf("Hair" to listOf(2, 2, 2)))
        store.delete("Link", false, "Drop")

        assertEquals(setOf("Keep"), store.presets("Link", false).keys)
        assertEquals(mapOf("Keep" to mapOf("Hair" to listOf(1, 1, 1))), store.presets("Link", false))
    }

    @Test
    fun `deleting a missing user preset is a no-op`() {
        val store = store()
        store.save("Link", false, "Keep", mapOf("Hair" to listOf(1, 1, 1)))
        store.delete("Link", false, "Missing")

        assertEquals(setOf("Keep"), store.presets("Link", false).keys)
    }
}
