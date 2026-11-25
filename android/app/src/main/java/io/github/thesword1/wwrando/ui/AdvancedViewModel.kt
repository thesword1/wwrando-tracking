package io.github.thesword1.wwrando.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.thesword1.wwrando.data.Permalink
import io.github.thesword1.wwrando.data.PermalinkRunner
import io.github.thesword1.wwrando.data.RandoBridge
import io.github.thesword1.wwrando.data.RandoSetup
import kotlinx.coroutines.launch

data class AboutInfo(
    val versionName: String,
    val bundledCommit: String,
    val installedCommit: String?,
    val termuxVersion: String?,
)

/** Owns the Advanced screen state: permalink encode/decode jobs and the About card facts. */
class AdvancedViewModel(application: Application) : AndroidViewModel(application) {
    private val setup = RandoSetup(application, viewModelScope)

    var loading by mutableStateOf(false)
        private set
    var permalink by mutableStateOf<String?>(null)
        private set
    var generateError by mutableStateOf<String?>(null)
        private set
    var pasteError by mutableStateOf<String?>(null)
        private set
    var pasteText by mutableStateOf("")
        private set

    private var generatedSettings: Map<String, Any> = emptyMap()
    private var generatedSeed: String = ""

    fun setupReady(): Boolean = setup.isSetupCurrent()

    /** True once settings or the Home seed changed after the last generate (the link is stale). */
    fun isStale(settings: Map<String, Any>, seed: String): Boolean =
        permalink != null && (settings != generatedSettings || seed != generatedSeed)

    fun onPasteChanged(value: String) {
        pasteText = value
        pasteError = null
    }

    /** Returns true when the paste field holds a syntactically valid permalink. */
    fun validatePaste(): Boolean {
        val valid = Permalink.isValid(pasteText.trim())
        pasteError = if (valid) null else "Not a valid permalink"
        return valid
    }

    fun generate(seed: String, settings: Map<String, Any>, onSeed: (String) -> Unit) {
        if (loading) return
        if (!setup.isSetupCurrent()) {
            permalink = null
            generateError = "Run setup first"
            return
        }
        generateError = null
        viewModelScope.launch {
            loading = true
            val result = PermalinkRunner.encode(getApplication(), seed, settings)
            loading = false
            if (result.ok) {
                permalink = result.permalink
                generatedSettings = settings
                generatedSeed = seed
                // A blank Home seed gets the generated one so the next run reproduces the link.
                if (seed.isBlank() && result.seed.isNotBlank()) onSeed(result.seed)
            } else {
                permalink = null
                generateError = result.error ?: "Failed to generate permalink"
            }
        }
    }

    fun load(onSeed: (String) -> Unit, applySettings: (Map<String, Any>) -> Unit) {
        if (loading) return
        val permalink = pasteText.trim()
        if (!Permalink.isValid(permalink)) {
            pasteError = "Not a valid permalink"
            return
        }
        if (!setup.isSetupCurrent()) {
            pasteError = "Run setup first"
            return
        }
        pasteError = null
        viewModelScope.launch {
            loading = true
            val result = PermalinkRunner.decode(getApplication(), permalink)
            loading = false
            if (result.ok) {
                applySettings(result.settings)
                if (result.seed.isNotBlank()) onSeed(result.seed)
                pasteText = ""
            } else {
                pasteError = result.error ?: "Could not load permalink"
            }
        }
    }

    fun about(): AboutInfo = AboutInfo(
        versionName = appVersionName(),
        bundledCommit = setup.bundledCommit(),
        installedCommit = setup.installedCommit(),
        termuxVersion = RandoBridge.termuxVersion(getApplication()),
    )

    private fun appVersionName(): String = runCatching {
        val context = getApplication<Application>()
        context.packageManager.getPackageInfo(context.packageName, 0).versionName
    }.getOrNull() ?: ""
}
