package io.github.thesword1.wwrando.data

import android.content.Context
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * User colour presets (PLAN 6b device-test decisions): `filesDir/color_presets.json`, keyed by
 * model name -> hero|casual -> preset name -> {color: [r,g,b]}. Unlike `customize.json`, these are
 * only a UI convenience and are never part of the run diff or Home presets.
 */
class ColorPresetStore(
    private val dir: File,
) {
    private val file: File get() = File(dir, "color_presets.json")

    constructor(context: Context) : this(context.filesDir)

    fun presets(model: String, casual: Boolean): Map<String, Map<String, List<Int>>> =
        readAll()[model]?.get(prefix(casual)) ?: emptyMap()

    fun save(model: String, casual: Boolean, name: String, colors: Map<String, List<Int>>) {
        val root = readAll().toMutableMap()
        val modelMap = root.getOrPut(model) { mutableMapOf() }
        val prefixMap = modelMap.getOrPut(prefix(casual)) { mutableMapOf() }
        prefixMap[name] = colors
        write(root)
    }

    fun delete(model: String, casual: Boolean, name: String) {
        val root = readAll().toMutableMap()
        root[model]?.get(prefix(casual))?.remove(name)
        write(root)
    }

    private fun prefix(casual: Boolean): String = if (casual) "casual" else "hero"

    private fun readAll(): MutableMap<String, MutableMap<String, MutableMap<String, Map<String, List<Int>>>>> {
        if (!file.isFile) return mutableMapOf()
        val json = runCatching { JSONObject(file.readText(Charsets.UTF_8)) }.getOrNull()
            ?: return mutableMapOf()
        val root = mutableMapOf<String, MutableMap<String, MutableMap<String, Map<String, List<Int>>>>>()
        json.keys().forEach { model ->
            val modelObj = json.optJSONObject(model) ?: return@forEach
            val modelMap = mutableMapOf<String, MutableMap<String, Map<String, List<Int>>>>()
            modelObj.keys().forEach { prefix ->
                val prefixObj = modelObj.optJSONObject(prefix) ?: return@forEach
                val prefixMap = mutableMapOf<String, Map<String, List<Int>>>()
                prefixObj.keys().forEach { name ->
                    val colors = readColors(prefixObj.optJSONObject(name))
                    if (colors.isNotEmpty()) prefixMap[name] = colors
                }
                modelMap[prefix] = prefixMap
            }
            root[model] = modelMap
        }
        return root
    }

    private fun write(root: Map<String, Map<String, Map<String, Map<String, List<Int>>>>>) {
        val out = JSONObject()
        root.forEach { (model, modelMap) ->
            val modelObj = JSONObject()
            modelMap.forEach { (prefix, prefixMap) ->
                val prefixObj = JSONObject()
                prefixMap.forEach { (name, colors) ->
                    prefixObj.put(name, colorsJson(colors))
                }
                modelObj.put(prefix, prefixObj)
            }
            out.put(model, modelObj)
        }
        file.parentFile?.mkdirs()
        file.writeText(out.toString(), Charsets.UTF_8)
    }

    private fun readColors(obj: JSONObject?): Map<String, List<Int>> {
        if (obj == null) return emptyMap()
        val out = LinkedHashMap<String, List<Int>>()
        obj.keys().forEach { key ->
            val array = obj.optJSONArray(key) ?: return@forEach
            if (array.length() != 3) return@forEach
            val color = (0 until 3).map { array.getInt(it) }
            if (color.all { it in 0..255 }) out[key] = color
        }
        return out
    }

    private fun colorsJson(colors: Map<String, List<Int>>): JSONObject {
        val obj = JSONObject()
        colors.forEach { (name, color) -> obj.put(name, JSONArray(color)) }
        return obj
    }
}
