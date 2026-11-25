package io.github.thesword1.wwrando.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import io.github.thesword1.wwrando.data.OptionDef
import io.github.thesword1.wwrando.data.OptionDependencies
import io.github.thesword1.wwrando.data.SettingsLogic
import io.github.thesword1.wwrando.data.SettingsStore

/** Owns the generated options schema and the current/preset settings diff for Logic/Tweaks/Starting items. */
class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    private val store = SettingsStore(application)
    private val defaults = SettingsLogic.defaults(store.schema)

    val schema: List<OptionDef> = store.schema
    val schemaByName: Map<String, OptionDef> = store.schema.associateBy { it.name }

    /** Bumped on every mutation so composables re-read the store's plain getters. */
    var version by mutableIntStateOf(0)
        private set

    fun effective(name: String): Any { version; return store.effective(name) }

    fun effectiveAll(): Map<String, Any> {
        version
        return defaults + store.current()
    }

    fun set(name: String, value: Any) {
        store.set(name, value)
        version++
    }

    fun resetToDefaults() {
        store.resetToDefaults()
        version++
    }

    /** The stored preset-scoped diff (what --settings-json takes); non-default values only. */
    fun currentDiff(): Map<String, Any> {
        version
        return store.current()
    }

    /** Replaces the current diff with decoded permalink settings (see SettingsStore.applyDecoded). */
    fun applyDecoded(decoded: Map<String, Any>) {
        store.applyDecoded(decoded)
        version++
    }

    fun listPresets(): List<String> { version; return listOf(SettingsLogic.DEFAULT_PRESET_NAME) + store.listPresets() }

    fun savePreset(name: String): String? {
        val saved = store.savePreset(name)
        if (saved != null) version++
        return saved
    }

    fun loadPreset(name: String) {
        store.loadPreset(name)
        version++
    }

    fun deletePreset(name: String) {
        store.deletePreset(name)
        version++
    }

    fun isVisible(name: String): Boolean {
        version
        return OptionDependencies.isVisible(name, effectiveAll())
    }

    val activePresetName: String get() { version; return store.activePresetName() }
    val isModified: Boolean get() { version; return store.isModified() }
    val changesCount: Int get() { version; return store.changesCount() }
}
