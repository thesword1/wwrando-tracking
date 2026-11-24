import java.security.MessageDigest

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "io.github.thesword1.wwrando"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.thesword1.wwrando"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    // Stable debug signing so CI builds install over each other. The keystore is never in the repo:
    // CI decodes it from the CI_DEBUG_KEYSTORE_B64 secret into $RUNNER_TEMP and points GM_DEBUG_KEYSTORE
    // at it; locally it is read straight from the GM_DEBUG_KEYSTORE* env vars. When the secret is absent
    // (e.g. fork PRs), the default Android debug key is used instead.
    val stableKeystore = System.getenv("GM_DEBUG_KEYSTORE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (stableKeystore != null) {
            create("stableDebug") {
                storeFile = stableKeystore
                storePassword = System.getenv("GM_DEBUG_KEYSTORE_PASSWORD")
                keyAlias = "wwrdebug"
                keyPassword = System.getenv("GM_DEBUG_KEYSTORE_PASSWORD")
                storeType = "PKCS12"
            }
        }
    }

    buildTypes {
        debug {
            if (stableKeystore != null) signingConfig = signingConfigs.getByName("stableDebug")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
    }

    sourceSets {
        getByName("main") {
            assets.srcDir(project.layout.buildDirectory.dir("generated/assets"))
        }
    }
}

// This repo's own Python randomizer sources (plus the gclib submodule) are the single source of truth:
// they are copied into generated APK assets at build time, at the exact commit this build is on. No
// fetch-at-tag and no network fetch: the tree is read straight from the working directory. Qt/GUI-only
// code is not bundled, and assembleDebug still works without the surrounding checkout (the copy task
// just copies whatever is present).
val copyRandomizerPython by tasks.registering(Sync::class) {
    val repoRoot = rootProject.layout.projectDirectory.dir("..")
    into(project.layout.buildDirectory.dir("generated/wwrando-tree"))
    from(repoRoot) {
        include("**/*.py")
        include("data/**")
        include("logic/**")
        include("asm/**")
        include("assets/**")
        include("seedgen/**")
        include("version.txt")
        // Qt/GUI-only code and non-runtime directories are not bundled.
        exclude("wwr_ui/uic/**")
        exclude("wwr_ui/randomizer_window.py")
        exclude("wwr_ui/cosmetic_tab.py")
        exclude("wwr_ui/offline_options.py")
        exclude("wwr_ui/qt_init.py")
        exclude("wwr_ui/update_checker.py")
        exclude("wwr_ui/build_ui.py")
        exclude("test/**")
        exclude("android/**")
        exclude("**/__pycache__/**")
        exclude("build/**")
        exclude("dist/**")
        exclude("site/**")
        exclude(".venv/**")
        exclude(".git/**")
        exclude(".github/**")
    }
}

// First-run setup streams the tree to Termux over the app's loopback bridge, so the copied tree is
// packed into one gzip archive (.tgz: AAPT gunzips and renames *.gz assets) plus a SHA-256 of that archive (installed-version marker).
// The bundled tree has no .git, so version.py would report "_NOGIT" and seed hashes/permalinks would
// not match a desktop build of the same commit. Ship the commit in build_commit.txt instead.
val buildCommit = providers.exec {
    workingDir = rootProject.layout.projectDirectory.dir("..").asFile
    commandLine("git", "rev-parse", "HEAD")
}.standardOutput.asText.map { it.trim() }

val writeBuildCommit by tasks.registering {
    val commit = buildCommit
    val outFile = project.layout.buildDirectory.file("generated/build-commit/build_commit.txt")
    inputs.property("commit", commit)
    outputs.file(outFile)
    doLast { outFile.get().asFile.writeText(commit.get() + "\n") }
}

val bundleRandomizerTree by tasks.registering(org.gradle.api.tasks.bundling.Tar::class) {
    dependsOn(copyRandomizerPython, writeBuildCommit)
    from(project.layout.buildDirectory.dir("generated/wwrando-tree"))
    from(project.layout.buildDirectory.dir("generated/build-commit"))
    include("**")
    compression = org.gradle.api.tasks.bundling.Compression.GZIP
    archiveFileName.set("wwrando.tgz")
    destinationDirectory.set(project.layout.buildDirectory.dir("generated/assets"))
}

val writeTreeHash by tasks.registering {
    dependsOn(bundleRandomizerTree)
    val archive = bundleRandomizerTree.flatMap { it.archiveFile }
    val shaFile = project.layout.buildDirectory.file("generated/assets/wwrando.sha256")
    inputs.file(archive)
    outputs.file(shaFile)
    doLast {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(archive.get().asFile.readBytes())
        shaFile.get().asFile.writeText(
            digest.joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') },
        )
    }
}

tasks.named("preBuild") {
    dependsOn(copyRandomizerPython, writeTreeHash)
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.compose.ui.tooling)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
