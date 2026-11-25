package io.github.thesword1.wwrando.data

/**
 * Pure setup decision for the Android app. A successful first-run setup records the APK's build
 * commit, so a missing record (nothing installed yet) or a differing commit means setup must run
 * again. No Android types, so it is unit-testable on the JVM.
 */
object SetupLogic {
    /** True when nothing is recorded, or the recorded commit differs from the APK's commit. */
    fun setupNeeded(installedCommit: String?, bundledCommit: String): Boolean =
        installedCommit.isNullOrBlank() || installedCommit != bundledCommit
}
