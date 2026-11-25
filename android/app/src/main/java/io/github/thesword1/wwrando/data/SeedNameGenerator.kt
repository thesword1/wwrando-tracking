package io.github.thesword1.wwrando.data

import kotlin.random.Random

/** Pure mirror of `seedgen/seedgen.py make_random_seed_name` (two adjectives + one noun/name). */
object SeedNameGenerator {
    fun generate(
        adjectives: List<String>,
        nouns: List<String>,
        names: List<String>,
        random: Random = Random.Default,
    ): String {
        require(adjectives.size >= 2 && nouns.isNotEmpty() && names.isNotEmpty()) { "empty seed word list" }
        val chosenAdjectives = adjectives.shuffled(random).take(2)
        val nounList = if (random.nextBoolean()) nouns else names
        val noun = nounList[random.nextInt(nounList.size)]
        return (chosenAdjectives + noun).joinToString("") { capitalizeFirstLetter(it) }
    }

    /** Capitalizes only the first ASCII letter, leaving every other character untouched (as desktop). */
    fun capitalizeFirstLetter(word: String): String {
        val out = StringBuilder(word.length)
        var seenLetter = false
        for (char in word) {
            if (!seenLetter && (char in 'A'..'Z' || char in 'a'..'z')) {
                out.append(char.uppercaseChar())
                seenLetter = true
            } else {
                out.append(char)
            }
        }
        return out.toString()
    }
}
