/* 应用代码加载器（稳定引导层）：
   - store/render/app 三个业务文件与 app.css 支持「检查更新」在线覆盖；
   - 覆盖存 localStorage kaoyan_code_v1（{t, version, files:{path:text}}）；
   - 新装/重打包的 APK 自带更新代码：内置时间戳 >= 覆盖时间戳时自动丢弃覆盖；
   - index.html / boot.js / vendor 不参与在线更新（改了这些才需要重打 APK）。 */
(function () {
  'use strict';
  var JS_FILES = ['js/store.js', 'js/render.js', 'js/app.js'];
  var CSS_FILE = 'css/app.css';
  var LS_KEY = 'kaoyan_code_v1';
  window.__codeSrc = {};

  var ov = null;
  try { ov = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (e) { ov = null; }
  // 新装/重打包的 APK 自带更新代码：内置版本号 >= 覆盖版本号时丢弃覆盖（按 versionCode 比对）
  if (ov && window.BUILD) {
    var bv = parseInt(window.BUILD.v) || 0;
    var stale = (ov.vcode && bv >= ov.vcode) || (!ov.vcode && ov.t && window.BUILD.t >= ov.t);
    if (stale) {
      localStorage.removeItem(LS_KEY);
      ov = null;
    }
  }

  function loadBundled(src, cb) {
    window.__codeSrc[src] = 'bundled';
    var s = document.createElement('script');
    // APK 内按构建时间戳稳定缓存；浏览器开发时（无 BUILD）每次取最新，避免启发式缓存吃掉新代码
    s.src = '/www/' + src + '?v=' + ((window.BUILD && window.BUILD.t) || Date.now());
    s.onload = cb;
    s.onerror = function () { console.error('加载失败:', src); cb(); };
    document.head.appendChild(s);
  }
  function runOverride(code, src, cb) {
    try {
      window.__codeSrc[src] = 'override';
      (0, eval)(code);
      cb();
    } catch (e) {
      console.error('覆盖代码执行失败，回退内置:', src, e);
      delete window.__codeSrc[src];
      loadBundled(src, cb);
    }
  }

  if (ov && ov.files && ov.files[CSS_FILE]) {
    var st = document.createElement('style');
    st.textContent = ov.files[CSS_FILE];
    document.head.appendChild(st);
    window.__codeSrc[CSS_FILE] = 'override';
  }

  var i = 0;
  (function next() {
    if (i >= JS_FILES.length) return;
    var f = JS_FILES[i++];
    var code = ov && ov.files && ov.files[f];
    if (code) runOverride(code, f, next);
    else loadBundled(f, next);
  })();
})();
