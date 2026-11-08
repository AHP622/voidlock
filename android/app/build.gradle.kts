plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// The release workflow passes the version (same number as the Windows app) and the signing key through environment variables.
val vName = System.getenv("VOIDLOCK_VERSION_NAME") ?: "0.0.0"
val vCode = (System.getenv("VOIDLOCK_VERSION_CODE") ?: "1").toInt()
val keystorePath: String? = System.getenv("VOIDLOCK_KEYSTORE")

android {
    namespace = "app.voidlock"
    compileSdk = 34

    defaultConfig {
        applicationId = "app.voidlock"
        minSdk = 26
        targetSdk = 34
        versionCode = vCode
        versionName = vName
    }

    signingConfigs {
        create("release") {
            if (keystorePath != null && File(keystorePath).exists()) {
                storeFile = File(keystorePath)
                storePassword = System.getenv("VOIDLOCK_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("VOIDLOCK_KEY_ALIAS")
                keyPassword = System.getenv("VOIDLOCK_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (keystorePath != null && File(keystorePath).exists()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.webkit:webkit:1.11.0")
    implementation("androidx.work:work-runtime:2.9.1")
}
