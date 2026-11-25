package io.github.thesword1.wwrando.data

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ModelStoreTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun zipOf(entries: Map<String, String>): File {
        val file = File(tmp.root, "model-${System.nanoTime()}.zip")
        ZipOutputStream(FileOutputStream(file)).use { out ->
            for ((name, data) in entries) {
                out.putNextEntry(ZipEntry(name))
                out.write(data.toByteArray(Charsets.UTF_8))
                out.closeEntry()
            }
        }
        return file
    }

    private fun store(): ModelStore = ModelStore(File(tmp.root, "models"))

    private fun import(store: ModelStore, zip: File): ModelStore.ImportResult =
        store.importZip(FileInputStream(zip))

    @Test
    fun `single model zip is imported`() {
        val zip = zipOf(
            mapOf(
                "MyModel/Link.arc" to "ARC",
                "MyModel/metadata.txt" to "hero_custom_colors: {}\n",
                "MyModel/preview/preview_hero.png" to "PNG",
            ),
        )
        val result = import(store(), zip)
        assertTrue(result is ModelStore.ImportResult.Ok)
        assertEquals(listOf("MyModel"), store().list())
        assertNotNull(store().readEntry("MyModel", "metadata.txt"))
        assertNotNull(store().readEntry("MyModel", "preview/preview_hero.png"))
    }

    @Test
    fun `model pack is split into one zip per model`() {
        val zip = zipOf(
            mapOf(
                "Pack/models/A/Link.arc" to "A",
                "Pack/models/A/metadata.txt" to "",
                "Pack/models/B/Link.arc" to "B",
                "Pack/models/B/metadata.txt" to "",
            ),
        )
        val result = import(store(), zip)
        assertTrue(result is ModelStore.ImportResult.Ok)
        assertEquals(2, (result as ModelStore.ImportResult.Ok).installed)
        assertEquals(listOf("A", "B"), store().list())
    }

    @Test
    fun `missing required file is rejected`() {
        val zip = zipOf(mapOf("M/Link.arc" to "ARC"))
        val result = import(store(), zip)
        assertTrue(result is ModelStore.ImportResult.Error)
        assertTrue((result as ModelStore.ImportResult.Error).message.contains("Missing file"))
    }

    @Test
    fun `zip slip entry is rejected`() {
        val zip = zipOf(
            mapOf(
                "M/Link.arc" to "ARC",
                "M/metadata.txt" to "",
                "../evil.txt" to "x",
            ),
        )
        val result = import(store(), zip)
        assertTrue(result is ModelStore.ImportResult.Error)
    }

    @Test
    fun `reserved model name is rejected`() {
        val zip = zipOf(
            mapOf(
                "Link/Link.arc" to "ARC",
                "Link/metadata.txt" to "",
            ),
        )
        val result = import(store(), zip)
        assertTrue(result is ModelStore.ImportResult.Error)
        assertTrue((result as ModelStore.ImportResult.Error).message.contains("Invalid model name"))
    }

    @Test
    fun `reimport replaces the model`() {
        val store = store()
        import(store, zipOf(mapOf("M/Link.arc" to "OLD", "M/metadata.txt" to "")))
        import(store, zipOf(mapOf("M/Link.arc" to "NEW", "M/metadata.txt" to "")))
        assertEquals(listOf("M"), store.list())
        assertEquals("NEW", store.readEntry("M", "Link.arc")?.toString(Charsets.UTF_8))
    }

    @Test
    fun `delete removes the model`() {
        val store = store()
        import(store, zipOf(mapOf("M/Link.arc" to "ARC", "M/metadata.txt" to "")))
        store.delete("M")
        assertEquals(emptyList<String>(), store.list())
        assertNull(store.readEntry("M", "Link.arc"))
    }
}
