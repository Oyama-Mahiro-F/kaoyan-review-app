#!/bin/bash
# 考研复习 APK 一键构建（Git Bash 版，各步骤已验证）
# 用法: ./build.sh [versionCode]   产物: ../dist/考研复习.apk
set -e
cd "$(dirname "$0")"
VC="${1:-1}"

export JAVA_HOME="D:/IntelliJ IDEA/jbr"
export PATH="$JAVA_HOME/bin:$PATH"
SDK="C:/Users/61468/AppData/Local/Android/Sdk"
BT="$SDK/build-tools/34.0.0"
PLATFORM="$SDK/platforms/android-34/android.jar"
ROOT="$(cd .. && pwd)"

echo "[0/7] 准备 assets（www + data）"
rm -rf assets build
mkdir -p assets build
cp -r "$ROOT/www" assets/www
cp -r "$ROOT/data" assets/data
rm -f assets/data/_report.txt
printf 'window.BUILD={v:"%s",vs:"1.%s",t:%s000};' "$VC" "$VC" "$(date +%s)" > assets/www/build_info.js
printf '{"vcode":%s,"version":"1.%s","t":%s000}' "$VC" "$VC" "$(date +%s)" > "$ROOT/app_build.json"

echo "[1/7] aapt2 compile"
"$BT/aapt2.exe" compile --dir res -o build/res.zip

echo "[2/7] aapt2 link"
"$BT/aapt2.exe" link -o build/base.apk -I "$PLATFORM" --manifest AndroidManifest.xml \
  -A assets --min-sdk-version 24 --target-sdk-version 34 \
  --version-code "$VC" --version-name "1.$VC" build/res.zip --auto-add-overlay

echo "[3/7] javac"
mkdir -p build/classes
javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "$PLATFORM" \
  -d build/classes java/com/kaoyan/review/MainActivity.java 2>/dev/null || true
[ -f build/classes/com/kaoyan/review/MainActivity.class ] || { echo "javac 失败"; exit 1; }

echo "[4/7] d8 dex"
"$BT/d8.bat" --release --lib "$PLATFORM" --output build build/classes/com/kaoyan/review/*.class

echo "[5/7] 打包 classes.dex"
python -c "import zipfile; z=zipfile.ZipFile(r'build/base.apk','a',zipfile.ZIP_STORED); z.write(r'build/classes.dex','classes.dex'); z.close()"

echo "[6/7] zipalign"
"$BT/zipalign.exe" -f 4 build/base.apk build/aligned.apk 2>/dev/null || "$BT/zipalign.exe" -f 4 build/base.apk build/aligned.apk

echo "[7/7] 签名"
mkdir -p "$ROOT/keystore" "$ROOT/dist"
if [ ! -f "$ROOT/keystore/kaoyan.jks" ]; then
  keytool -genkeypair -keystore "$ROOT/keystore/kaoyan.jks" -alias kaoyan -keyalg RSA \
    -keysize 2048 -validity 10000 -storepass kaoyan2026 -keypass kaoyan2026 \
    -dname "CN=Kaoyan Review, O=Personal" 2>/dev/null
fi
"$BT/apksigner.bat" sign --ks "$ROOT/keystore/kaoyan.jks" --ks-pass pass:kaoyan2026 \
  --key-pass pass:kaoyan2026 --out "$ROOT/dist/考研复习.apk" build/aligned.apk 2>/dev/null
"$BT/apksigner.bat" verify "$ROOT/dist/考研复习.apk" 2>/dev/null
cp "$ROOT/dist/考研复习.apk" "$ROOT/dist/kaoyan-review.apk"   # ASCII 名副本供 GitHub Release 上传
echo ""
echo "==== 构建成功: $ROOT/dist/考研复习.apk ($(du -h "$ROOT/dist/考研复习.apk" | cut -f1)) ===="
