plugins {
    kotlin("jvm") version "2.2.10"
    kotlin("plugin.serialization") version "2.2.10"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
    // 6단계(pipeline.py 이식) parity 테스트가 examples/*.json 을 읽고 쓰는 데 필요하다.
    // 도메인 모델(Models.kt)에는 애노테이션을 붙이지 않고, Json.kt 에서 JsonElement 로
    // 수동 변환한다 — null/필드 부재 구분과 snake_case 매핑을 직접 통제하기 위해서다.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
}

kotlin {
    jvmToolchain(17)
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "failed", "skipped")
        showStandardStreams = true
    }
}
