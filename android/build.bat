@echo off
rem ============================================================
rem 考研复习 APK 一键构建脚本
rem 用法: build.bat [versionCode]   默认 1
rem 产物: ..\dist\考研复习.apk
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set SDK=C:\Users\61468\AppData\Local\Android\Sdk
set BT=%SDK%\build-tools\34.0.0
set PLATFORM=%SDK%\platforms\android-34\android.jar
set JBR=D:\IntelliJ IDEA\jbr
set JAVA_HOME=%JBR%
set PATH=%JBR%\bin;%PATH%
set VC=%1
if "%VC%"=="" set VC=1

set ROOT=%cd%\..
set ASSETS=assets
set BUILD=build

echo [0/7] 准备 assets（www + data）
if exist %ASSETS% rmdir /s /q %ASSETS%
mkdir %ASSETS%
xcopy /e /i /q "%ROOT%\www" "%ASSETS%\www" >nul
xcopy /e /i /q "%ROOT%\data" "%ASSETS%\data" >nul
del /q "%ASSETS%\data\_report.txt" 2>nul

if exist %BUILD% rmdir /s /q %BUILD%
mkdir %BUILD%

echo [1/7] aapt2 compile
"%BT%\aapt2.exe" compile --dir res -o %BUILD%\res.zip || goto :fail

echo [2/7] aapt2 link
"%BT%\aapt2.exe" link -o %BUILD%\base.apk -I "%PLATFORM%" --manifest AndroidManifest.xml -A %ASSETS% --min-sdk-version 24 --target-sdk-version 34 --version-code %VC% --version-name 1.%VC% %BUILD%\res.zip --auto-add-overlay || goto :fail

echo [3/7] javac
mkdir %BUILD%\classes
javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "%PLATFORM%" -d %BUILD%\classes java\com\kaoyan\review\MainActivity.java || goto :fail

echo [4/7] d8 dex
"%BT%\d8.bat" --release --lib "%PLATFORM%" --output %BUILD% %BUILD%\classes\com\kaoyan\review\*.class || goto :fail

echo [5/7] 打包 classes.dex
python -c "import zipfile; z=zipfile.ZipFile(r'%BUILD%\base.apk','a',zipfile.ZIP_STORED); z.write(r'%BUILD%\classes.dex','classes.dex'); z.close()" || goto :fail

echo [6/7] zipalign
"%BT%\zipalign.exe" -f 4 %BUILD%\base.apk %BUILD%\aligned.apk || goto :fail

echo [7/7] 签名
if not exist ..\keystore\kaoyan.jks (
  echo   首次构建，生成签名密钥...
  mkdir ..\keystore 2>nul
  keytool -genkeypair -v -keystore ..\keystore\kaoyan.jks -alias kaoyan -keyalg RSA -keysize 2048 -validity 10000 -storepass kaoyan2026 -keypass kaoyan2026 -dname "CN=Kaoyan Review, O=Personal" || goto :fail
)
"%BT%\apksigner.bat" sign --ks ..\keystore\kaoyan.jks --ks-pass pass:kaoyan2026 --key-pass pass:kaoyan2026 --out "%ROOT%\dist\考研复习.apk" %BUILD%\aligned.apk || goto :fail

"%BT%\apksigner.bat" verify --print-certs "%ROOT%\dist\考研复习.apk" | findstr /c:"Signer" >nul && (
  echo.
  echo ==== 构建成功: %ROOT%\dist\考研复习.apk ====
  for %%A in ("%ROOT%\dist\考研复习.apk") do echo 大小: %%~zA 字节
) || goto :fail
goto :eof

:fail
echo.
echo ==== 构建失败 ====
exit /b 1
