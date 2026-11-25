package io.github.thesword1.wwrando.data

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Parity against the repo's Python gclib color code. The JSON fixture is generated once by
 * `android/tools/gen_color_fixtures.py` and committed; this test only reads it.
 */
class ColorLogicTest {

    private fun fixture(): JSONObject {
        val stream = checkNotNull(javaClass.getResourceAsStream("/color_fixtures.json")) {
            "color_fixtures.json missing from test resources"
        }
        return JSONObject(stream.bufferedReader(Charsets.UTF_8).use { it.readText() })
    }

    private fun ints(array: JSONArray): IntArray = IntArray(array.length()) { array.getInt(it) }

    @Test
    fun `hsv shift matches python hsv_shift_color`() {
        val cases = fixture().getJSONArray("hsv_shift")
        assert(cases.length() > 0)
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val actual = ColorLogic.hsvShiftColor(ints(c.getJSONArray("color")), c.getInt("h"), c.getInt("v"))
            assertArrayEquals("case $i: $c", ints(c.getJSONArray("expect")), actual)
        }
    }

    @Test
    fun `color exchange pixel transform matches python color_exchange`() {
        val cases = fixture().getJSONArray("color_exchange")
        assert(cases.length() > 0)
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val actual = ColorLogic.exchangePixel(
                ints(c.getJSONArray("base")),
                ints(c.getJSONArray("replacement")),
                ints(c.getJSONArray("pixel")),
            )
            assertArrayEquals("case $i: $c", ints(c.getJSONArray("expect")), actual)
        }
    }

    @Test
    fun `exchange image only changes opaque red mask pixels`() {
        // ARGB pixels: opaque blue, semi-transparent green, grey under transparent mask, grey under red mask.
        val image = intArrayOf(
            0xFFFF0000.toInt(), // opaque blue
            0x8000FF00.toInt(), // semi-transparent green
            0xFFCCCCCC.toInt(), // grey
            0xFFCCCCCC.toInt(), // grey
        )
        val mask = intArrayOf(
            0xFFFFFFFF.toInt(), // white -> skip
            0xFFFF0000.toInt(), // red -> change
            0x00000000.toInt(), // transparent -> skip
            0xFFFF0000.toInt(), // red -> change
        )
        val out = ColorLogic.exchangeImage(image, mask, 4, 1, intArrayOf(255, 0, 0), intArrayOf(0, 0, 255))
        assertEquals(image[0], out[0]) // white mask: unchanged
        assertEquals(true, out[1] != image[1]) // red mask: recoloured
        assertEquals(0x80, ColorLogic.argbToRgba(out[1])[3]) // alpha preserved
        assertEquals(image[2], out[2]) // transparent mask: unchanged
        assertEquals(true, out[3] != image[3]) // red mask: recoloured
        assertEquals(255, ColorLogic.argbToRgba(out[3])[3]) // alpha preserved
    }
}
