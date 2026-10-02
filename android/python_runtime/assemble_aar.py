#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把 p4a 预处理产物组装成 runtime AAR（与 Gradle 产物结构一致，可离线复现）。

输入（由 p4a 的 build.py 预处理生成，见 p4a_package_aar.sh）：
  dist_aar/AndroidManifest.xml          —— 已含 ServiceZhixue 声明
  dist_aar/src/main/java/**             —— ServiceZhixue + org.kivy/org.renpy 运行时类
  dist_aar/src/main/assets/private.tar  —— 本载荷（web/ learning/ structured/ service/）
  dist_aar/libs/arm64-v8a/*.so          —— CPython 3.14 + libpybundle（载荷编译产物）
  dist_aar/templates/*                  —— p4a 模板资源（图标/启动图）

输出：
  app/libs/zhixueenglish_backend_runtime.aar

为什么不用 Gradle 打包：p4a dist 的 wrapper 固定 gradle-8.14.3，需要联网下载发行包；
本工程要求离线可复现，因此这里用等价的 zip 组装（manifest + classes.jar + jni + assets + res），
内容与《智学小四门》已验证 AAR 完全同构。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist_aar"
OUT_AAR = HERE.parent / "app" / "libs" / "zhixueenglish_backend_runtime.aar"
RUNTIME_PACKAGE = "com.zhixueenglish.app.dev.runtime"
SERVICE_CLASS = RUNTIME_PACKAGE + ".ServiceZhixue"


def find_javac() -> str:
    candidates = [
        Path(r"D:\Program Files\Android\Android Studio\jbr\bin\javac.exe"),
        Path(os.environ.get("JAVA_HOME", "")) / "bin" / "javac.exe",
    ]
    for path in candidates:
        if path and path.exists():
            return str(path)
    found = shutil.which("javac")
    if found:
        return found
    raise SystemExit("找不到 javac（需要 JDK；Android Studio 自带 JBR 亦可）")


def find_android_jar() -> str:
    sdk = Path(os.environ.get("ANDROID_HOME") or r"G:\AndroidSDK")
    for api in ("android-33", "android-36", "android-35", "android-34"):
        jar = sdk / "platforms" / api / "android.jar"
        if jar.exists():
            return str(jar)
    raise SystemExit("找不到 android.jar（需要 Android SDK platform）")


def build_classes_jar(work: Path) -> Path:
    src_root = DIST / "src" / "main" / "java"
    sources = [p for p in src_root.rglob("*.java") if "com\\zhixueai" not in str(p)
               and "com/zhixueai" not in str(p)]
    if not sources:
        raise SystemExit("没有可编译的 Java 源（p4a 预处理未完成？）")
    classes_dir = work / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    android_jar = find_android_jar()
    cmd = [find_javac(), "-nowarn", "-source", "8", "-target", "8",
           "-bootclasspath", android_jar, "-classpath", android_jar,
           "-d", str(classes_dir)] + [str(p) for p in sources]
    subprocess.run(cmd, check=True)
    jar_path = work / "classes.jar"
    with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as jar:
        for path in sorted(classes_dir.rglob("*")):
            if path.is_file():
                jar.write(path, path.relative_to(classes_dir).as_posix())
    return jar_path


def private_version(private_tar: Path) -> str:
    """与 p4a 同口径的载荷版本串（PythonUtil 用它判断是否需要重新解包）。"""
    digest = hashlib.sha1(private_tar.read_bytes()).hexdigest()
    return digest


def main() -> int:
    if not DIST.exists():
        raise SystemExit("缺少 p4a 预处理目录：%s（先运行 p4a_package_aar.sh）" % DIST)
    private_tar = DIST / "src" / "main" / "assets" / "private.tar"
    if not private_tar.exists():
        raise SystemExit("缺少 private.tar（p4a 预处理未完成）")
    libs_dir = DIST / "libs" / "arm64-v8a"
    if not libs_dir.exists():
        raise SystemExit("缺少 arm64-v8a 运行库")

    work = HERE / ".aar_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    classes_jar = build_classes_jar(work)

    manifest = (DIST / "AndroidManifest.xml").read_text(encoding="utf-8")
    if "package=" not in manifest:
        manifest = manifest.replace(
            "<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\"",
            "<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\"\n"
            "      package=\"%s\"" % RUNTIME_PACKAGE, 1)
    if SERVICE_CLASS not in manifest:
        raise SystemExit("manifest 里缺少服务声明：" + SERVICE_CLASS)

    version = private_version(private_tar)
    values_xml = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<resources>\n"
        "    <string name=\"app_name\">ZhixueEnglishRuntime</string>\n"
        "    <string name=\"private_version\">%s</string>\n</resources>\n" % version
    )
    meta_props = (
        "aarFormatVersion=1.0\n"
        "aarMetadataVersion=1.0\n"
        "minCompileSdk=1\n"
        "minCompileSdkExtension=0\n"
        "minAndroidGradlePluginVersion=1.0.0\n"
        "coreLibraryDesugaringEnabled=false\n"
    )
    r_txt = ("int drawable presplash 0x0\nint mipmap icon 0x0\n"
             "int string app_name 0x0\nint string private_version 0x0\n")

    OUT_AAR.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_AAR, "w", zipfile.ZIP_DEFLATED) as aar:
        aar.writestr("AndroidManifest.xml", manifest)
        aar.writestr("R.txt", r_txt)
        aar.writestr("res/values/values.xml", values_xml)
        aar.writestr("META-INF/com/android/build/gradle/aar-metadata.properties", meta_props)
        for name, src in (("res/mipmap/icon.png", DIST / "templates" / "kivy-icon.png"),
                          ("res/drawable/presplash.jpg", DIST / "templates" / "kivy-presplash.jpg")):
            if src.exists():
                aar.write(src, name)
        aar.write(classes_jar, "classes.jar")
        aar.write(private_tar, "assets/private.tar")
        for so in sorted(libs_dir.glob("*.so")):
            aar.write(so, "jni/arm64-v8a/" + so.name)

    size = OUT_AAR.stat().st_size
    print("AAR:", OUT_AAR)
    print("  size: %.1f MB" % (size / 1024 / 1024))
    print("  private_version:", version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
