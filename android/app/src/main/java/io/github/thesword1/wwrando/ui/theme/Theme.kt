package io.github.thesword1.wwrando.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/** Mirrors GameHub Manager's dark-only palette (read-only reference). */
private val DarkColors = darkColorScheme(
    primary = Color(0xFF4FA3FF),
    onPrimary = Color(0xFF001A33),
    secondary = Color(0xFF9CC7FF),
    tertiary = Color(0xFF7BD88F),
    error = Color(0xFFFF6B6B),
    background = Color(0xFF101216),
    onBackground = Color(0xFFE6E8EE),
    surface = Color(0xFF161A21),
    onSurface = Color(0xFFE6E8EE),
    surfaceVariant = Color(0xFF1F2530),
    onSurfaceVariant = Color(0xFFB4BAC6),
    surfaceContainer = Color(0xFF1B2029),
    outline = Color(0xFF3A4250),
)

@Composable
fun WwRandoTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = DarkColors, content = content)
}
