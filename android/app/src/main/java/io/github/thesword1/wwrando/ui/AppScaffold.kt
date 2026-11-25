package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.SelfCheckIssue

enum class Section(val label: String, val icon: ImageVector) {
    Home("Home", Icons.Filled.Home),
    Logic("Logic", Icons.Filled.Tune),
    Tweaks("Tweaks", Icons.Filled.Settings),
    StartingItems("Starting items", Icons.Filled.Inventory2),
    Customize("Customize", Icons.Filled.Palette),
    Advanced("Advanced", Icons.Filled.Info),
}

/** Left navigation rail shell modeled on GameHub Manager's AppScaffold. */
@Composable
fun AppScaffold(
    selfCheck: List<SelfCheckIssue>,
    permissionDenials: Int,
    viewModel: RandoViewModel,
    outputsViewModel: OutputsViewModel,
    settingsViewModel: SettingsViewModel,
    customizeViewModel: CustomizeViewModel,
    onRequestPermission: () -> Unit,
    onInstallTermux: () -> Unit,
    onOpenAppSettings: () -> Unit,
    onOpenHistory: () -> Unit,
) {
    var current by rememberSaveable { mutableStateOf(Section.Home) }

    Scaffold { padding ->
        Row(Modifier.fillMaxSize().padding(padding)) {
            NavigationRail {
                Section.entries.forEach { section ->
                    NavigationRailItem(
                        selected = section == current,
                        onClick = { current = section },
                        icon = { Icon(section.icon, contentDescription = section.label) },
                        label = { Text(section.label) },
                    )
                }
            }
            Box(Modifier.fillMaxSize()) {
                when (current) {
                    Section.Home -> HomeScreen(
                        selfCheck = selfCheck,
                        permissionDenials = permissionDenials,
                        viewModel = viewModel,
                        outputsViewModel = outputsViewModel,
                        settingsViewModel = settingsViewModel,
                        onRequestPermission = onRequestPermission,
                        onInstallTermux = onInstallTermux,
                        onOpenAppSettings = onOpenAppSettings,
                        onOpenHistory = onOpenHistory,
                    )
                    Section.Logic -> LogicScreen(viewModel = settingsViewModel)
                    Section.Tweaks -> TweaksScreen(viewModel = settingsViewModel)
                    Section.StartingItems -> StartingItemsScreen(viewModel = settingsViewModel)
                    Section.Customize -> CustomizeScreen(viewModel = customizeViewModel)
                    Section.Advanced -> PlaceholderScreen("Advanced", "About and permalink arrive in 6c.")
                }
            }
        }
    }
}

@Composable
private fun PlaceholderScreen(title: String, message: String) {
    Column(
        Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineSmall)
        Text(message, style = MaterialTheme.typography.bodyMedium)
    }
}
