package io.github.thesword1.wwrando.data

/**
 * Pure rules for pasted/shared permalinks. A permalink is the randomizer's base64-encoded settings
 * string (standard base64 alphabet, so it may contain `+`, `/` and trailing `=`), with the same
 * length bound enforced in run.sh before the value is handed to the randomizer.
 */
object Permalink {
    private val PATTERN = Regex("^[A-Za-z0-9+/=]{4,2000}$")

    fun isValid(value: String): Boolean = PATTERN.matches(value)
}
