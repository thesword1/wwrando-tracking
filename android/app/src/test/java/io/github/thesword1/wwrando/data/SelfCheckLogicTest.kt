package io.github.thesword1.wwrando.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SelfCheckLogicTest {

    @Test
    fun `everything ok yields no issues`() {
        assertTrue(
            SelfCheckLogic.issues(
                SelfCheckInput(
                    setupReady = true,
                    isoPicked = true,
                    isoVerified = true,
                    outputPicked = true,
                ),
            ).isEmpty(),
        )
    }

    @Test
    fun `termux missing is reported first`() {
        val issues = SelfCheckLogic.issues(
            SelfCheckInput(
                termuxInstalled = false,
                setupReady = false,
                isoPicked = false,
                outputPicked = false,
            ),
        )
        assertEquals(SelfCheckFix.InstallTermux, issues.first().fix)
        assertTrue(issues.any { it.fix == SelfCheckFix.PickIso })
        assertTrue(issues.any { it.fix == SelfCheckFix.PickOutputFolder })
    }

    @Test
    fun `run command denial and setup error are reported`() {
        val issues = SelfCheckLogic.issues(
            SelfCheckInput(
                runCommandGranted = false,
                setupReady = false,
                setupError = "boom",
                isoPicked = true,
                isoVerified = true,
                outputPicked = true,
            ),
        )
        assertTrue(issues.any { it.fix == SelfCheckFix.GrantRunCommand })
        assertTrue(issues.any { it.fix == SelfCheckFix.RunSetup && it.message.contains("boom") })
    }

    @Test
    fun `unverified iso is reported as pick iso`() {
        val issues = SelfCheckLogic.issues(
            SelfCheckInput(
                setupReady = true,
                isoPicked = true,
                isoVerified = false,
                outputPicked = true,
            ),
        )
        assertEquals(listOf(SelfCheckFix.PickIso), issues.map { it.fix })
    }
}
