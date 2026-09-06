/* 问枢 Pivot · S3 完整原型 · 公共脚本 */
var toastTimer = null;
function toast(msg) {
  var t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div'); t.id = 'toast'; t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { t.classList.remove('show'); }, 1900);
}
/* 用户菜单 */
function toggleUserMenu(e) {
  e.stopPropagation();
  var u = e.currentTarget;
  u.classList.toggle('open');
  var close = function () { u.classList.remove('open'); document.removeEventListener('click', close); };
  document.addEventListener('click', close);
}
function initUserMenu(adminUrl) {
  document.addEventListener('click', function (e) {
    var u = document.getElementById('userbox');
    if (u && !u.contains(e.target)) u.classList.remove('open');
  });
}
/* Ctrl+K 聚焦全局搜索 */
document.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    var g = document.getElementById('gq');
    if (g) { e.preventDefault(); g.focus(); }
  }
});
/* 全局搜索提交：搜文档→search.html；问AI→chat.html */
function gsearch(e) {
  if (e) e.preventDefault();
  var i = document.getElementById('gq');
  var v = (i ? i.value : '').trim();
  if (!v) { toast('请输入搜索内容'); return; }
  if (window.location.pathname.indexOf('search.html') !== -1) {
    var m = document.getElementById('sqi');
    if (m) { m.value = v; runSearch(); return; }
  }
  toast('🔍 已携带关键词跳转搜索结果页');
  setTimeout(function(){ window.location.href = 'search.html?q=' + encodeURIComponent(v); }, 350);
}
/* 通用打开 Modal */
function openModal(id) { document.getElementById(id).classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.mask.show').forEach(function (m) { m.classList.remove('show'); });
    var d = document.getElementById('drawer');
    if (d) d.classList.remove('show');
    var o = document.getElementById('overlay');
    if (o) o.classList.remove('show');
  }
});
/* 证据抽屉 */
function openDrawer(i) {
  var tag = document.getElementById('dtag');
  if (tag) tag.textContent = ' · 引用 [' + i + ']';
  document.getElementById('overlay').classList.add('show');
  document.getElementById('drawer').classList.add('show');
}
function closeDrawer() {
  document.getElementById('overlay').classList.remove('show');
  document.getElementById('drawer').classList.remove('show');
}
/* 反馈投票 */
function vote(btn, type) {
  var box = btn.parentNode;
  box.querySelectorAll('.vote').forEach(function (b) { b.classList.remove('on'); });
  btn.classList.add('on');
  var n = btn.querySelector('.n'); var c = parseInt(n.textContent || '0');
  n.textContent = c + 1;
  toast(btn.classList.contains('on') ? (type === 'ok' ? '👍 感谢反馈，将用于优化回答' : '👎 已记录，将改进该回答') : '已取消');
}
/* 导出浮层 */
function togglePop(e) {
  e.stopPropagation();
  var pop = e.currentTarget.parentNode.querySelector('.pop');
  if (pop) {
    document.querySelectorAll('.pop.show').forEach(function (p) { if (p !== pop) p.classList.remove('show'); });
    pop.classList.toggle('show');
  }
}
document.addEventListener('click', function () {
  document.querySelectorAll('.pop.show').forEach(function (p) { p.classList.remove('show'); });
});
