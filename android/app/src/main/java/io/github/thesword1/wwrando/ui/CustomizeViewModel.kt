package io.github.thesword1.wwrando.ui

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import io.github.thesword1.wwrando.data.CustomizeLogic
import io.github.thesword1.wwrando.data.CustomizeStore
import io.github.thesword1.wwrando.data.ColorPresetStore
import io.github.thesword1.wwrando.data.ModelMetadata
import io.github.thesword1.wwrando.data.ModelStore
import kotlin.random.Random
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Owns the Customize screen state, model imports and the debounced live preview. */
class CustomizeViewModel(application: Application) : AndroidViewModel(application) {
    private val store = CustomizeStore(application)
    private val models = ModelStore.from(application)
    private val colorPresets = ColorPresetStore(application)

    var state by mutableStateOf(store.state())
        private set
    var installed by mutableStateOf(models.list())
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var preview by mutableStateOf<ImageBitmap?>(null)
        private set
    var version by mutableIntStateOf(0)
        private set

    private var previewJob: Job? = null

    init {
        // A stored model that no longer exists falls back to Link (PLAN 6b).
        if (state.playerModel != CustomizeLogic.DEFAULT_MODEL &&
            state.playerModel != "Random" &&
            state.playerModel != "Random (exclude Link)" &&
            state.playerModel !in installed
        ) {
            commitState(state.copy(playerModel = CustomizeLogic.DEFAULT_MODEL))
        } else {
            schedulePreview()
        }
    }

    val metadata: ModelMetadata get() { version; return models.metadata(state.playerModel) }

    val defaultColors: Map<String, List<Int>> get() { version; return CustomizeLogic.defaultColors(state, metadata) }

    /** User presets stored for the current model + hero/casual prefix. */
    val userPresets: Map<String, Map<String, List<Int>>> get() {
        version
        return colorPresets.presets(state.playerModel, CustomizeLogic.isCasual(state, metadata))
    }

    val presetNames: List<String> get() {
        version
        return CustomizeLogic.presetNames(state, metadata, userPresets.keys)
    }

    val isUserPresetSelected: Boolean get() { version; return state.presetSelection in userPresets }

    val isRandomModel: Boolean get() = state.playerModel == "Random" || state.playerModel == "Random (exclude Link)"

    val voiceAvailable: Boolean get() { version; return models.hasCustomVoice(state.playerModel) }

    fun selectModel(name: String) {
        if (name == state.playerModel) return
        var next = state.copy(playerModel = name)
        val meta = models.metadata(name)
        if (meta.disableCasualClothes) next = next.copy(casualClothes = false)
        val preset = CustomizeLogic.presetAfterSwitch(next.colorPreset, CustomizeLogic.colorPresets(next, meta))
        next = next.copy(colorPreset = preset, presetSelection = preset)
        commitState(next)
    }

    fun toggleCasual(casual: Boolean) {
        var next = state.copy(casualClothes = casual)
        val meta = models.metadata(next.playerModel)
        val preset = CustomizeLogic.presetAfterSwitch(next.colorPreset, CustomizeLogic.colorPresets(next, meta))
        next = next.copy(colorPreset = preset, presetSelection = preset)
        commitState(next)
    }

    fun toggleVoice(enabled: Boolean) = commitState(state.copy(disableVoice = enabled))

    fun toggleItems(enabled: Boolean) = commitState(state.copy(disableItems = enabled))

    fun selectPreset(name: String) {
        commitState(CustomizeLogic.selectPreset(state, name, metadata, userPresets))
    }

    fun setColor(colorName: String, color: List<Int>) {
        val defaults = defaultColors
        commitState(CustomizeLogic.applyColorChange(state, metadata, defaults, colorName, color))
    }

    fun randomizeOne(colorName: String) {
        commitState(CustomizeLogic.randomizeOne(state, metadata, defaultColors, colorName, Random.Default))
    }

    fun randomizeAll(separate: Boolean) {
        val next = if (separate) {
            CustomizeLogic.randomizeAllSeparately(state, metadata, Random.Default)
        } else {
            CustomizeLogic.randomizeAllTogether(state, metadata, Random.Default)
        }
        commitState(next)
    }

    fun resetOne(colorName: String) {
        commitState(CustomizeLogic.resetOne(state, metadata, defaultColors, colorName))
    }

    fun resetAllColors() {
        commitState(CustomizeLogic.resetAllColors(state))
    }

    fun importModel(uri: Uri) {
        error = null
        val input = getApplication<Application>().contentResolver.openInputStream(uri)
            ?: run { error = "Cannot open the selected file."; return }
        val result = input.use { models.importZip(it) }
        when (result) {
            is ModelStore.ImportResult.Error -> error = result.message
            is ModelStore.ImportResult.Ok -> {
                installed = models.list()
                version++
            }
        }
    }

    fun deleteModel(name: String) {
        models.delete(name)
        installed = models.list()
        version++
        if (state.playerModel == name) {
            var next = state.copy(playerModel = CustomizeLogic.DEFAULT_MODEL)
            val meta = models.metadata(CustomizeLogic.DEFAULT_MODEL)
            val preset = CustomizeLogic.presetAfterSwitch(next.colorPreset, CustomizeLogic.colorPresets(next, meta))
            next = next.copy(colorPreset = preset, presetSelection = preset)
            commitState(next)
        }
    }

    /** Save the current colours as a user preset; returns an error message, or null when saved. */
    fun saveUserPreset(name: String): String? {
        val casual = CustomizeLogic.isCasual(state, metadata)
        val validation = CustomizeLogic.validateUserPresetName(name, metadata, casual)
        if (validation != null) return validation
        val trimmed = name.trim()
        val defaults = defaultColors
        val colors = defaults.keys.associateWith { CustomizeLogic.getColor(state, metadata, defaults, it) }
        colorPresets.save(state.playerModel, casual, trimmed, colors)
        val next = CustomizeLogic.selectPreset(state, trimmed, metadata, colorPresets.presets(state.playerModel, casual))
        commitState(next)
        return null
    }

    fun deleteUserPreset(name: String) {
        val casual = CustomizeLogic.isCasual(state, metadata)
        colorPresets.delete(state.playerModel, casual, name)
        if (state.presetSelection == name) {
            commitState(state.copy(colorPreset = CustomizeLogic.DEFAULT_PRESET, presetSelection = CustomizeLogic.DEFAULT_PRESET))
        } else {
            version++
            schedulePreview()
        }
    }

    fun clearError() {
        error = null
    }

    private fun commitState(next: CustomizeLogic.State) {
        state = next
        store.save(next)
        version++
        schedulePreview()
    }

    private fun schedulePreview() {
        previewJob?.cancel()
        previewJob = viewModelScope.launch {
            delay(150)
            preview = renderPreview(state)
        }
    }

    private suspend fun renderPreview(s: CustomizeLogic.State): ImageBitmap? = withContext(Dispatchers.IO) {
        if (s.playerModel == "Random" || s.playerModel == "Random (exclude Link)") return@withContext null
        val meta = models.metadata(s.playerModel)
        if (meta.errorMessage != null) return@withContext null
        val casual = CustomizeLogic.isCasual(s, meta)
        val prefix = if (casual) "casual" else "hero"
        val baseBytes = models.previewBase(s.playerModel, prefix) ?: return@withContext null
        var bitmap = BitmapFactory.decodeByteArray(baseBytes, 0, baseBytes.size) ?: return@withContext null
        val defaults = meta.customColors(casual)
        for ((colorName, baseColor) in defaults) {
            val current = CustomizeLogic.getColor(s, meta, defaults.mapValues { it.value.toList() }, colorName)
            if (current == baseColor.toList()) continue
            val maskBytes = models.previewMask(s.playerModel, prefix, colorName) ?: continue
            val mask = BitmapFactory.decodeByteArray(maskBytes, 0, maskBytes.size) ?: continue
            bitmap = PreviewRenderer.recolor(bitmap, mask, baseColor, current.toIntArray())
        }
        bitmap.asImageBitmap()
    }
}
