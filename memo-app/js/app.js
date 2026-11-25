/**
 * 轻记 —— 一个纯前端的备忘录
 * 数据保存在浏览器 localStorage 里，刷新或关闭页面都不会丢。
 */

const STORAGE_KEY = 'memo.notes.v1';

// ---------- DOM 引用 ----------
const $ = (selector, root = document) => root.querySelector(selector);

const els = {
  search: $('#search'),
  searchClear: $('#search-clear'),
  tagFilters: $('#tag-filters'),
  stat: $('#stat'),
  notes: $('#notes'),
  empty: $('#empty'),
  emptyTitle: $('#empty-title'),
  emptyDesc: $('#empty-desc'),
  btnEmptyNew: $('#btn-empty-new'),
  editor: $('#editor'),
  form: $('#editor-form'),
  editorTitle: $('#editor-title'),
  inTitle: $('#in-title'),
  titleError: $('#title-error'),
  inContent: $('#in-content'),
  inTags: $('#in-tags'),
  toast: $('#toast'),
  template: $('#note-template'),
};

// ---------- 状态 ----------
let notes = loadNotes();
let editingId = null;          // 正在编辑的备忘 id，null 表示新建
let keyword = '';              // 搜索关键字
let activeTag = null;          // 当前筛选的标签

// ---------- 存储 ----------
function loadNotes() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const data = raw ? JSON.parse(raw) : [];
    return Array.isArray(data) ? data : [];
  } catch (err) {
    console.warn('读取本地数据失败，已使用空列表：', err);
    return [];
  }
}

function saveNotes() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
  } catch (err) {
    console.warn('保存失败：', err);
    toast('保存失败，浏览器可能禁用了本地存储');
  }
}

// ---------- 工具函数 ----------
function uid() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function parseTags(text) {
  // 支持用中英文逗号、顿号或空格分隔
  const list = text
    .split(/[,，、\s]+/)
    .map((t) => t.trim())
    .filter(Boolean);
  return [...new Set(list)].slice(0, 5);
}

function formatTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return `今天 ${time}`;

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`;

  if (d.getFullYear() === now.getFullYear()) {
    return `${d.getMonth() + 1}月${d.getDate()}日 ${time}`;
  }
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => els.toast.classList.remove('show'), 1800);
}

// ---------- 筛选与排序 ----------
function matchesKeyword(note, kw) {
  if (!kw) return true;
  const text = (note.title + ' ' + note.content + ' ' + note.tags.join(' ')).toLowerCase();
  return text.includes(kw);
}

function visibleNotes() {
  const kw = keyword.trim().toLowerCase();
  return notes
    .filter((n) => matchesKeyword(n, kw))
    .filter((n) => !activeTag || n.tags.includes(activeTag))
    .sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
      if (a.done !== b.done) return a.done ? 1 : -1;
      return b.updatedAt - a.updatedAt;
    });
}

// ---------- 渲染 ----------
function renderTagFilters() {
  // 标签统计基于「搜索结果」，但不受当前标签筛选影响
  const kw = keyword.trim().toLowerCase();
  const pool = notes.filter((n) => matchesKeyword(n, kw));

  const counts = new Map();
  pool.forEach((n) => n.tags.forEach((t) => counts.set(t, (counts.get(t) || 0) + 1)));

  if (activeTag && !counts.has(activeTag)) activeTag = null;

  els.tagFilters.textContent = '';

  const allChip = document.createElement('button');
  allChip.type = 'button';
  allChip.className = 'chip';
  allChip.setAttribute('role', 'tab');
  allChip.setAttribute('aria-selected', String(!activeTag));
  allChip.textContent = '全部';
  allChip.addEventListener('click', () => {
    activeTag = null;
    render();
  });
  els.tagFilters.appendChild(allChip);

  [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'))
    .forEach(([tag, count]) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.setAttribute('role', 'tab');
      chip.setAttribute('aria-selected', String(activeTag === tag));
      chip.innerHTML = '';
      chip.append(tag);
      const num = document.createElement('span');
      num.className = 'chip-count';
      num.textContent = count;
      chip.appendChild(num);
      chip.addEventListener('click', () => {
        activeTag = activeTag === tag ? null : tag;
        render();
      });
      els.tagFilters.appendChild(chip);
    });
}

function renderNotes(list) {
  els.notes.textContent = '';

  const fragment = document.createDocumentFragment();
  list.forEach((note) => {
    const node = els.template.content.firstElementChild.cloneNode(true);
    node.dataset.id = note.id;
    node.classList.toggle('pinned', !!note.pinned);
    node.classList.toggle('done', !!note.done);

    $('.note-title', node).textContent = note.title;
    $('.note-body', node).textContent = note.content;
    $('.note-time', node).textContent = formatTime(note.updatedAt);

    const tagsBox = $('.note-tags', node);
    note.tags.forEach((tag) => {
      const span = document.createElement('span');
      span.className = 'note-tag';
      span.textContent = '#' + tag;
      tagsBox.appendChild(span);
    });

    fragment.appendChild(node);
  });

  els.notes.appendChild(fragment);
}

function renderStat(list) {
  const total = notes.length;
  const done = notes.filter((n) => n.done).length;

  if (total === 0) {
    els.stat.textContent = '';
    return;
  }
  const showing = list.length !== total ? `正在显示 ${list.length} 条 · ` : '';
  els.stat.textContent = `${showing}共 ${total} 条，已完成 ${done} 条`;
}

function render() {
  const list = visibleNotes();

  renderTagFilters();
  renderNotes(list);
  renderStat(list);

  // 空状态：区分「一条都没有」和「筛选后没有结果」
  const isEmpty = list.length === 0;
  els.empty.hidden = !isEmpty;
  els.notes.hidden = isEmpty;

  if (isEmpty) {
    const hasFilter = keyword.trim() !== '' || activeTag !== null;
    if (hasFilter && notes.length > 0) {
      els.emptyTitle.textContent = '没有匹配的备忘录';
      els.emptyDesc.textContent = '换个关键词，或者点「全部」标签看看。';
      els.btnEmptyNew.hidden = true;
    } else {
      els.emptyTitle.textContent = '还没有备忘录';
      els.emptyDesc.textContent = '点「新建备忘」，记下第一件事吧。';
      els.btnEmptyNew.hidden = false;
    }
  }
}

// ---------- 编辑弹窗 ----------
function openEditor(id = null) {
  editingId = id;
  els.form.reset();
  els.inTitle.classList.remove('invalid');
  els.titleError.hidden = true;

  if (id) {
    const note = notes.find((n) => n.id === id);
    if (!note) return;
    els.editorTitle.textContent = '编辑备忘';
    els.inTitle.value = note.title;
    els.inContent.value = note.content;
    els.inTags.value = note.tags.join(', ');
  } else {
    els.editorTitle.textContent = '新建备忘';
  }

  els.editor.showModal();
  els.inTitle.focus();
}

function closeEditor() {
  els.editor.close();
  editingId = null;
}

function handleSubmit(event) {
  event.preventDefault();

  const title = els.inTitle.value.trim();
  if (!title) {
    els.inTitle.classList.add('invalid');
    els.titleError.hidden = false;
    els.inTitle.focus();
    return;
  }

  const content = els.inContent.value.trim();
  const tags = parseTags(els.inTags.value);
  const now = Date.now();

  if (editingId) {
    const note = notes.find((n) => n.id === editingId);
    if (note) {
      Object.assign(note, { title, content, tags, updatedAt: now });
    }
    toast('已保存修改');
  } else {
    notes.push({
      id: uid(),
      title,
      content,
      tags,
      pinned: false,
      done: false,
      createdAt: now,
      updatedAt: now,
    });
    toast('已新建备忘');
  }

  saveNotes();
  closeEditor();
  render();
}

// ---------- 卡片操作 ----------
function handleNoteClick(event) {
  const tagEl = event.target.closest('.note-tag');
  if (tagEl) {
    activeTag = tagEl.textContent.slice(1);
    render();
    return;
  }

  const actionEl = event.target.closest('[data-action]');
  if (!actionEl) return;

  const card = event.target.closest('.note');
  const note = notes.find((n) => n.id === card?.dataset.id);
  if (!note) return;

  switch (actionEl.dataset.action) {
    case 'edit':
      openEditor(note.id);
      break;

    case 'toggle-pin':
      note.pinned = !note.pinned;
      saveNotes();
      render();
      toast(note.pinned ? '已置顶' : '已取消置顶');
      break;

    case 'toggle-done':
      note.done = !note.done;
      note.updatedAt = Date.now();
      saveNotes();
      render();
      toast(note.done ? '太棒了，又完成一件' : '已恢复为待办');
      break;

    case 'delete': {
      const ok = window.confirm(`确定删除「${note.title}」吗？删除后无法恢复。`);
      if (!ok) return;
      notes = notes.filter((n) => n.id !== note.id);
      saveNotes();
      render();
      toast('已删除');
      break;
    }
  }
}

// ---------- 搜索 ----------
function handleSearch() {
  keyword = els.search.value;
  els.searchClear.hidden = keyword === '';
  render();
}

// ---------- 事件绑定 ----------
function bindEvents() {
  $('#btn-new').addEventListener('click', () => openEditor());
  els.btnEmptyNew.addEventListener('click', () => openEditor());

  els.search.addEventListener('input', handleSearch);
  els.searchClear.addEventListener('click', () => {
    els.search.value = '';
    els.search.focus();
    handleSearch();
  });

  els.notes.addEventListener('click', handleNoteClick);

  els.form.addEventListener('submit', handleSubmit);
  $('#btn-close').addEventListener('click', closeEditor);
  $('#btn-cancel').addEventListener('click', closeEditor);

  // 点击遮罩关闭
  els.editor.addEventListener('click', (event) => {
    if (event.target === els.editor) closeEditor();
  });

  // Esc 关闭弹窗时也要清掉编辑状态
  els.editor.addEventListener('close', () => { editingId = null; });

  // 标题输入后去掉红框
  els.inTitle.addEventListener('input', () => {
    els.inTitle.classList.remove('invalid');
    els.titleError.hidden = true;
  });

  // Ctrl / ⌘ + Enter 保存
  els.form.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });
}

// ---------- 启动 ----------
function seedIfFirstVisit() {
  const SEEDED_KEY = 'memo.seeded';
  try {
    if (localStorage.getItem(SEEDED_KEY) || notes.length > 0) return;

    // 首次打开时放一条示例，方便直接看到效果（删掉也可以）
    const now = Date.now();
    notes = [{
      id: uid(),
      title: '欢迎使用轻记',
      content: '试着点一下卡片标题可以编辑。\n右上角的小图钉能把备忘置顶，左边圆圈用来标记完成。\n这条示例看完可以直接删掉。',
      tags: ['示例'],
      pinned: true,
      done: false,
      createdAt: now,
      updatedAt: now,
    }];
    saveNotes();
    localStorage.setItem(SEEDED_KEY, '1');
  } catch (err) {
    console.warn('初始化示例数据失败：', err);
  }
}

bindEvents();
seedIfFirstVisit();
render();
