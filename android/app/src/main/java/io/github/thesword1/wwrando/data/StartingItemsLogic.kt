package io.github.thesword1.wwrando.data

/** Pure rules for the Starting items screen. The allowed item list comes from the itemlist option. */
object StartingItemsLogic {
    const val HURRICANE_SPIN = "Hurricane Spin"
    const val PROGRESSIVE_SWORD = "Progressive Sword"

    /** Items the current sword mode removes from both the picker and the current list (desktop rule). */
    fun excludedItems(swordMode: String): Set<String> = when (swordMode) {
        OptionDependencies.SWORDLESS -> setOf(HURRICANE_SPIN, PROGRESSIVE_SWORD)
        OptionDependencies.NO_STARTING_SWORD, OptionDependencies.SWORDS_OPTIONAL -> setOf(PROGRESSIVE_SWORD)
        else -> emptySet()
    }

    /** The current starting list with any sword-mode-excluded items removed. */
    fun filteredStarting(startingGear: List<String>, swordMode: String): List<String> {
        val excluded = excludedItems(swordMode)
        if (excluded.isEmpty()) return startingGear
        return startingGear.filterNot { it in excluded }
    }

    /** Remaining pickable count per item after removing what is already in the starting list. */
    fun availableCounts(
        option: OptionDef.ItemList,
        startingGear: List<String>,
        swordMode: String,
    ): Map<String, Int> {
        val excluded = excludedItems(swordMode)
        val current = counts(filteredStarting(startingGear, swordMode))
        return option.choices
            .filterNot { it in excluded }
            .associateWith { item -> (option.maxCounts[item] ?: 0) - (current[item] ?: 0) }
            .filterValues { it > 0 }
    }

    fun counts(list: List<String>): Map<String, Int> = list.groupingBy { it }.eachCount()

    /** The desktop's starting-health label ("X hearts and Y piece(s)"). */
    fun healthLabel(startingPohs: Int, startingHcs: Int): String {
        val pieces = startingPohs + startingHcs * 4
        val full = pieces / 4
        val remainder = pieces % 4
        return buildString {
            append("Current Starting Health: $full ")
            append(if (full == 1) "heart" else "hearts")
            if (remainder > 0) append(if (remainder == 1) " and 1 piece" else " and $remainder pieces")
        }
    }
}
