package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.RailSections
import io.github.thesword1.wwrando.service.RunState
import io.github.thesword1.wwrando.service.RunStateValue

/** Tweaks rail section: Meta, In-Game Tracker, Convenience Tweaks, Hints. */
@Composable
fun TweaksScreen(viewModel: SettingsViewModel) {
    val runState by RunState.state.collectAsState()
    val runActive = runState is RunStateValue.Running
    viewModel.version

    Column(
        Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Tweaks", style = MaterialTheme.typography.headlineSmall)

        RailSections.tweaksGroups.forEach { group ->
            val options = group.options.mapNotNull { viewModel.schemaByName[it] }
            SectionCard(
                title = group.title,
                options = options,
                viewModel = viewModel,
                runActive = runActive,
                visible = viewModel::isVisible,
            )
        }
    }
}
