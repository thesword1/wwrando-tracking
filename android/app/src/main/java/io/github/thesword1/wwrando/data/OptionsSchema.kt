package io.github.thesword1.wwrando.data

import org.json.JSONArray
import org.json.JSONObject

/** One generated randomizer option, ready for the settings screen to render. */
sealed interface OptionDef {
    val name: String
    val group: String
    val description: String
    val permalink: Boolean

    data class Bool(
        override val name: String,
        override val group: String,
        override val description: String,
        override val permalink: Boolean,
        val default: Boolean,
    ) : OptionDef

    data class Enum(
        override val name: String,
        override val group: String,
        override val description: String,
        override val permalink: Boolean,
        val default: String,
        val choices: List<String>,
        val choiceDescriptions: List<String>,
    ) : OptionDef

    data class IntOption(
        override val name: String,
        override val group: String,
        override val description: String,
        override val permalink: Boolean,
        val default: Int,
        val minimum: Int,
        val maximum: Int,
    ) : OptionDef

    data class Multi(
        override val name: String,
        override val group: String,
        override val description: String,
        override val permalink: Boolean,
        val default: List<String>,
        val choices: List<String>,
    ) : OptionDef

    /** A list option whose values are items with per-item max counts (progressive items). */
    data class ItemList(
        override val name: String,
        override val group: String,
        override val description: String,
        override val permalink: Boolean,
        val default: List<String>,
        val choices: List<String>,
        val maxCounts: Map<String, Int>,
    ) : OptionDef
}

/** Parses the committed `options_schema.json` asset (org.json) into [OptionDef]s. Pure: no Android types. */
object OptionsSchema {
    fun parse(json: String): List<OptionDef> {
        val root = JSONObject(json)
        val entries = root.getJSONArray("options")
        val options = ArrayList<OptionDef>(entries.length())
        for (i in 0 until entries.length()) {
            val obj = entries.getJSONObject(i)
            val name = obj.getString("name")
            val group = obj.getString("group")
            val description = obj.optString("description", "")
            val permalink = obj.optBoolean("permalink", true)
            options += when (obj.getString("type")) {
                "bool" -> OptionDef.Bool(name, group, description, permalink, obj.getBoolean("default"))
                "enum" -> OptionDef.Enum(
                    name, group, description, permalink,
                    obj.getString("default"),
                    toStringList(obj.getJSONArray("choices")),
                    toStringList(obj.getJSONArray("choice_descriptions")),
                )
                "int" -> OptionDef.IntOption(
                    name, group, description, permalink,
                    obj.getInt("default"),
                    obj.getInt("minimum"),
                    obj.getInt("maximum"),
                )
                "multi" -> OptionDef.Multi(
                    name, group, description, permalink,
                    toStringList(obj.optJSONArray("default") ?: JSONArray()),
                    toStringList(obj.getJSONArray("choices")),
                )
                "itemlist" -> OptionDef.ItemList(
                    name, group, description, permalink,
                    toStringList(obj.optJSONArray("default") ?: JSONArray()),
                    toStringList(obj.getJSONArray("choices")),
                    toCountMap(obj.getJSONObject("max_counts")),
                )
                else -> throw IllegalArgumentException("unknown option type for $name")
            }
        }
        return options
    }

    private fun toStringList(array: JSONArray): List<String> =
        (0 until array.length()).map { array.getString(it) }

    private fun toCountMap(obj: JSONObject): Map<String, Int> {
        val out = LinkedHashMap<String, Int>()
        obj.keys().forEach { key -> out[key] = obj.getInt(key) }
        return out
    }
}
