package io.github.thesword1.wwrando.data

/** The fix action a Self-Check row needs. The UI maps each to a button/launcher. */
enum class SelfCheckFix { InstallTermux, UpdateTermux, GrantRunCommand, RunSetup, PickIso, PickOutputFolder }

data class SelfCheckIssue(val message: String, val fix: SelfCheckFix)

/** Facts the self-check aggregates. Kept plain so the rules are unit-testable without Android. */
data class SelfCheckInput(
    val termuxInstalled: Boolean = true,
    val termuxNewEnough: Boolean = true,
    val runCommandGranted: Boolean = true,
    val setupReady: Boolean = true,
    val setupRunning: Boolean = false,
    val setupError: String? = null,
    val isoPicked: Boolean = false,
    val isoVerified: Boolean = false,
    val outputPicked: Boolean = false,
)

/** Pure self-check aggregation: a list of failures, or an empty list when everything is OK. */
object SelfCheckLogic {
    fun issues(input: SelfCheckInput): List<SelfCheckIssue> = buildList {
        when {
            !input.termuxInstalled -> add(
                SelfCheckIssue("Termux is not installed (0.118+).", SelfCheckFix.InstallTermux),
            )
            !input.termuxNewEnough -> add(
                SelfCheckIssue("Termux is too old; update to 0.118 or newer.", SelfCheckFix.UpdateTermux),
            )
            !input.runCommandGranted -> add(
                SelfCheckIssue("Termux RUN_COMMAND permission is denied.", SelfCheckFix.GrantRunCommand),
            )
        }
        if (!input.setupRunning) {
            when {
                input.setupError != null -> add(
                    SelfCheckIssue("Setup failed: ${input.setupError}", SelfCheckFix.RunSetup),
                )
                !input.setupReady -> add(
                    SelfCheckIssue("Setup is not ready yet.", SelfCheckFix.RunSetup),
                )
            }
        }
        when {
            !input.isoPicked -> add(
                SelfCheckIssue("No clean ISO picked.", SelfCheckFix.PickIso),
            )
            !input.isoVerified -> add(
                SelfCheckIssue("ISO is not verified (not the clean Wind Waker ISO).", SelfCheckFix.PickIso),
            )
        }
        if (!input.outputPicked) {
            add(SelfCheckIssue("Output folder not picked.", SelfCheckFix.PickOutputFolder))
        }
    }
}
