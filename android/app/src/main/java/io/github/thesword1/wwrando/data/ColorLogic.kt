package io.github.thesword1.wwrando.data

import kotlin.math.max
import kotlin.math.min

/**
 * Pure Kotlin port of the desktop recoloring math in `gclib/gclib/texture_utils.py`
 * (`color_exchange` pure-Python path and `hsv_shift_color`). Every truncation matches Python's
 * `colorsys` + `int()` exactly, so the Android preview and the desktop GUI produce identical
 * colors. `ColorLogicTest` asserts this against fixtures generated from the Python code.
 */
object ColorLogic {
    /** ARGB of the mask's opaque pure-red pixel (FF0000FF): the only pixel color_exchange changes. */
    const val MASK_RED: Int = 0xFFFF0000.toInt()

    data class Hsv(val h: Int, val s: Int, val v: Int)

    private fun mod1(x: Double): Double = x - Math.floor(x)

    private fun modInt(a: Int, b: Int): Int = ((a % b) + b) % b

    /** int(h*360), int(s*100), int(v*100) of colorsys.rgb_to_hsv(r/255, g/255, b/255). */
    fun rgbToHsv(rgb: IntArray): Hsv {
        val r = rgb[0] / 255.0
        val g = rgb[1] / 255.0
        val b = rgb[2] / 255.0
        val maxc = max(r, max(g, b))
        val minc = min(r, min(g, b))
        val v = maxc
        if (minc == maxc) return Hsv(0, 0, (v * 100).toInt())
        val rangec = maxc - minc
        val s = rangec / maxc
        val rc = (maxc - r) / rangec
        val gc = (maxc - g) / rangec
        val bc = (maxc - b) / rangec
        val rawH = when {
            r == maxc -> bc - gc
            g == maxc -> 2.0 + rc - bc
            else -> 4.0 + gc - rc
        }
        val h = mod1(rawH / 6.0)
        return Hsv((h * 360).toInt(), (s * 100).toInt(), (v * 100).toInt())
    }

    /** int(r*255), int(g*255), int(b*255) of colorsys.hsv_to_rgb(h/360, s/100, v/100). */
    fun hsvToRgb(hsv: Hsv): IntArray {
        val h = hsv.h / 360.0
        val s = hsv.s / 100.0
        val v = hsv.v / 100.0
        if (s == 0.0) {
            val c = (v * 255).toInt()
            return intArrayOf(c, c, c)
        }
        val i = (h * 6.0).toInt()
        val f = (h * 6.0) - i
        val p = v * (1.0 - s)
        val q = v * (1.0 - s * f)
        val t = v * (1.0 - s * (1.0 - f))
        val r: Double
        val g: Double
        val b: Double
        when (modInt(i, 6)) {
            0 -> { r = v; g = t; b = p }
            1 -> { r = q; g = v; b = p }
            2 -> { r = p; g = v; b = t }
            3 -> { r = p; g = q; b = v }
            4 -> { r = t; g = p; b = v }
            else -> { r = v; g = p; b = q }
        }
        return intArrayOf((r * 255).toInt(), (g * 255).toInt(), (b * 255).toInt())
    }

    /** Mirror of texture_utils.hsv_shift_color for a 3- or 4-channel color (alpha preserved). */
    fun hsvShiftColor(color: IntArray, hShift: Int, vShift: Int): IntArray {
        val hasAlpha = color.size == 4
        val hsv = rgbToHsv(intArrayOf(color[0], color[1], color[2]))
        var h = modInt(hsv.h + hShift, 360)
        val origV = hsv.v
        var v = hsv.v + vShift
        if (v < 0) v = 0
        if (v > 100) v = 100
        if (v < 30 && origV >= 30) v = 30
        if (v > 90 && origV <= 90) v = 90
        val vDiff = v - origV

        val origS = hsv.s
        var s = hsv.s
        if (origS < 15 && vShift > 0) {
            s += if (origV < 30) vShift * 2 else vShift
        } else {
            s -= vDiff
        }
        if (s < 0) s = 0
        if (s > 100) s = 100
        if (s < 5 && origS >= 5) s = 5
        if (s > 80 && origS <= 80) s = 80

        val out = hsvToRgb(Hsv(h, s, v))
        return if (hasAlpha) intArrayOf(out[0], out[1], out[2], color[3]) else out
    }

    /** Per-pixel transform of the pure-Python color_exchange (no mask; alpha preserved). */
    fun exchangePixel(base: IntArray, replacement: IntArray, pixel: IntArray): IntArray {
        val hasAlpha = pixel.size == 4
        val baseHsv = rgbToHsv(base)
        val replacementHsv = rgbToHsv(replacement)
        val sChange = replacementHsv.s - baseHsv.s
        val vChange = replacementHsv.v - baseHsv.v

        val px = rgbToHsv(intArrayOf(pixel[0], pixel[1], pixel[2]))
        var s = px.s
        if (s == 0) s = baseHsv.s
        val newH = modInt(replacementHsv.h, 360)
        val newS = max(0, min(100, s + sChange))
        val newV = max(0, min(100, px.v + vChange))

        val out = hsvToRgb(Hsv(newH, newS, newV))
        return if (hasAlpha) intArrayOf(out[0], out[1], out[2], pixel[3]) else out
    }

    fun argbToRgba(argb: Int): IntArray = intArrayOf(
        (argb ushr 16) and 0xFF,
        (argb ushr 8) and 0xFF,
        argb and 0xFF,
        (argb ushr 24) and 0xFF,
    )

    fun rgbaToArgb(rgba: IntArray): Int =
        ((rgba[3] and 0xFF) shl 24) or ((rgba[0] and 0xFF) shl 16) or
            ((rgba[1] and 0xFF) shl 8) or (rgba[2] and 0xFF)

    /**
     * Applies the desktop color_exchange over a flat ARGB image: only pixels whose mask is
     * [MASK_RED] are recoloured; white, transparent and every other mask colour are left alone.
     */
    fun exchangeImage(
        image: IntArray,
        mask: IntArray,
        width: Int,
        height: Int,
        base: IntArray,
        replacement: IntArray,
    ): IntArray {
        require(image.size == width * height && mask.size == width * height)
        val out = image.copyOf()
        for (i in out.indices) {
            if (mask[i] != MASK_RED) continue
            out[i] = rgbaToArgb(exchangePixel(base, replacement, argbToRgba(out[i])))
        }
        return out
    }
}
