#!/bin/bash
# 一键发版：构建 APK → 同步数据/代码清单（stamp vcode）→ 仓库提交+tag → GitHub Release(挂 APK) → 站点清单推送
# 用法: ./release.sh <versionCode> ["发版说明"]
#   例: ./release.sh 9 "错题支持按小节筛选"
set -e
cd "$(dirname "$0")"
VC="${1:?用法: ./release.sh <versionCode> [说明]}"
VER="1.$VC"
NOTES="${2:-考研复习 v$VER}"
SITE_DIR="/d/university_learning/site"

echo "[1/6] 构建 APK（versionCode=$VC, versionName=$VER）"
(cd android && bash build.sh "$VC" > /dev/null)
echo "      $(ls -la dist/考研复习.apk | awk '{print $5}') bytes"

echo "[2/6] 同步数据与代码清单（app_index 盖 vcode 戳）"
python extractor/extract_data.py | tail -2

echo "[3/6] 写发布元数据 → site/appdata/app_release.json"
python - "$VC" "$VER" "$NOTES" <<'PYEOF'
import json, sys, time, io
vc, ver, notes = int(sys.argv[1]), sys.argv[2], sys.argv[3]
meta = {
    "version": ver, "vcode": vc, "t": int(time.time() * 1000),
    "apk": f"https://github.com/Oyama-Mahiro-F/kaoyan-review-app/releases/download/v{ver}/kaoyan-review.apk",
    "notes": notes,
}
p = r"D:\university_learning\site\appdata\app_release.json"
io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(meta, ensure_ascii=False, indent=1))
print("      app_release.json →", meta["version"])
PYEOF

echo "[4/6] 仓库提交 + tag v$VER"
git add -A
git commit -m "release v$VER" 2>/dev/null || echo "      （仓库无变更）"
git tag -f "v$VER" > /dev/null
git push 2>&1 | tail -1
git push origin "v$VER" -f 2>&1 | tail -1

echo "[5/6] GitHub Release v$VER（上传 APK）"
cp "dist/考研复习.apk" "dist/kaoyan-review.apk"
gh release delete "v$VER" --yes 2>/dev/null || true
gh release create "v$VER" "dist/kaoyan-review.apk" --title "考研复习 v$VER" --notes "$NOTES"

echo "[6/6] 推送站点（app_release / app_index / appdata 生效）"
cd "$SITE_DIR" && PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python push.py 2>&1 | grep -E "推送成功|失败" | head -2

echo ""
echo "==== v$VER 发布完成：GitHub Release + 手机「检查更新」可用 ===="
