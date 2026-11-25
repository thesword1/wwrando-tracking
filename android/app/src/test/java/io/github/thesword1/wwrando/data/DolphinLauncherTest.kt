package io.github.thesword1.wwrando.data

import android.content.Intent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DolphinLauncherTest {

    @Test
    fun `spec has the expected package component extra and flags`() {
        val spec = DolphinLauncher.buildSpec(
            "org.dolphinemu.dolphinemu",
            "content://com.android.externalstorage.documents/tree/primary%3AWWRando/document/primary%3AWWRando%2Fhash_20261124-100000%2FWW%20Random.iso",
        )

        assertEquals("org.dolphinemu.dolphinemu", spec.packageName)
        assertEquals("org.dolphinemu.dolphinemu.ui.main.MainActivity", spec.componentClass)
        assertEquals("content://com.android.externalstorage.documents/tree/primary%3AWWRando/document/primary%3AWWRando%2Fhash_20261124-100000%2FWW%20Random.iso", spec.autoStartFile)
        assertEquals(spec.autoStartFile, spec.dataUri)
        assertEquals(
            Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TASK,
            spec.flags,
        )
        assertTrue(spec.sendsRawUriClipData)
    }

    @Test
    fun `both dolphin packages are queried`() {
        assertEquals(
            listOf("org.dolphinemu.dolphinemu", "org.dolphinemu.mmjr"),
            DolphinLauncher.PACKAGES,
        )
    }
}
