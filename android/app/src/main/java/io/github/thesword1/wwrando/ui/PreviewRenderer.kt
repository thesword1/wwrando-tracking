package io.github.thesword1.wwrando.ui

import android.graphics.Bitmap
import io.github.thesword1.wwrando.data.ColorLogic

/** Decodes and recolours the model preview using the pure [ColorLogic] port. Android-only. */
object PreviewRenderer {
    fun recolor(bitmap: Bitmap, mask: Bitmap, baseColor: IntArray, replacement: IntArray): Bitmap {
        val width = bitmap.width
        val height = bitmap.height
        if (mask.width != width || mask.height != height) return bitmap
        val pixels = IntArray(width * height)
        val maskPixels = IntArray(width * height)
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
        mask.getPixels(maskPixels, 0, width, 0, 0, width, height)
        val out = ColorLogic.exchangeImage(pixels, maskPixels, width, height, baseColor, replacement)
        return Bitmap.createBitmap(out, width, height, Bitmap.Config.ARGB_8888)
    }
}
