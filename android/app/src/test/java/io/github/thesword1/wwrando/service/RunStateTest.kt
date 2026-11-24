package io.github.thesword1.wwrando.service

import org.junit.Assert.assertEquals
import org.junit.Test

class RunStateTest {
    @Test
    fun transitionsIdleToRunningToDone() {
        RunState.set(RunStateValue.Idle)
        assertEquals(RunStateValue.Idle, RunState.state.value)

        RunState.set(RunStateValue.Running(5, 10, "Randomizing"))
        val running = RunState.state.value as RunStateValue.Running
        assertEquals(5, running.progress)
        assertEquals(10, running.max)
        assertEquals("Randomizing", running.step)

        RunState.set(RunStateValue.Done("seed", "hash", "permalink", "folder"))
        val done = RunState.state.value as RunStateValue.Done
        assertEquals("hash", done.seedHash)
        assertEquals("folder", done.outputFolder)
    }

    @Test
    fun transitionsToFailedAndCancelled() {
        RunState.set(RunStateValue.Failed("boom"))
        assertEquals("boom", (RunState.state.value as RunStateValue.Failed).error)

        RunState.set(RunStateValue.Cancelled)
        assertEquals(RunStateValue.Cancelled, RunState.state.value)
    }
}
