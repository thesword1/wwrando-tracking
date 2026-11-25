package io.github.thesword1.wwrando.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.thesword1.wwrando.data.SelfCheckFix
import io.github.thesword1.wwrando.data.SelfCheckIssue

/** Home's Self-Check card: a list of failures each with a fix action, or "Everything is OK". */
@Composable
fun SelfCheckCard(
    issues: List<SelfCheckIssue>,
    permissionDenials: Int,
    onFix: (SelfCheckFix) -> Unit,
    onOpenAppSettings: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Self-Check", style = MaterialTheme.typography.titleMedium)
            if (issues.isEmpty()) {
                Text(
                    "Everything is OK",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyLarge,
                )
            } else {
                issues.forEach { issue ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            issue.message,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f),
                        )
                        TextButton(onClick = { onFix(issue.fix) }) { Text(fixLabel(issue.fix)) }
                    }
                    if (issue.fix == SelfCheckFix.GrantRunCommand && permissionDenials >= 2) {
                        TextButton(onClick = onOpenAppSettings) { Text("Open app settings") }
                    }
                }
            }
        }
    }
}

private fun fixLabel(fix: SelfCheckFix): String = when (fix) {
    SelfCheckFix.InstallTermux -> "Install"
    SelfCheckFix.UpdateTermux -> "Update"
    SelfCheckFix.GrantRunCommand -> "Grant permission"
    SelfCheckFix.RunSetup -> "Retry setup"
    SelfCheckFix.PickIso -> "Pick ISO"
    SelfCheckFix.PickOutputFolder -> "Pick folder"
}
