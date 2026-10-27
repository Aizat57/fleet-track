/* FleetTrack UI behaviour: navigation drawer, popovers, toasts, tabs, modals, filters,
   uploads, the Add Vehicle wizard and conditional fields. Progressive enhancement only —
   every form still submits normally without JavaScript. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  /* ---------- sidebar drawer (tablet / mobile) */
  function initDrawer() {
    const sidebar = $('#sidebar'), toggle = $('#menu-toggle');
    if (!sidebar || !toggle) return;
    let scrim;
    const close = () => {
      sidebar.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false');
      scrim && scrim.remove(); scrim = null;
    };
    toggle.addEventListener('click', () => {
      if (sidebar.classList.contains('open')) return close();
      sidebar.classList.add('open'); toggle.setAttribute('aria-expanded', 'true');
      scrim = document.createElement('div'); scrim.className = 'scrim'; scrim.addEventListener('click', close);
      document.body.appendChild(scrim);
      const first = $('a', sidebar); first && first.focus();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && sidebar.classList.contains('open')) { close(); toggle.focus(); } });
  }

  /* ---------- popovers: [data-pop] wrapper with a [data-pop-trigger] button */
  function initPopovers() {
    const closeAll = except => $$('.pop.open').forEach(p => {
      if (p === except) return;
      p.classList.remove('open');
      const t = $('[data-pop-trigger]', p); t && t.setAttribute('aria-expanded', 'false');
    });
    document.addEventListener('click', e => {
      const trigger = e.target.closest('[data-pop-trigger]');
      if (trigger) {
        const pop = trigger.closest('.pop');
        const open = !pop.classList.contains('open');
        closeAll(pop);
        pop.classList.toggle('open', open);
        trigger.setAttribute('aria-expanded', String(open));
        if (open) { const f = $('.pop-panel a, .pop-panel button', pop); f && setTimeout(() => f.focus(), 30); }
        return;
      }
      if (!e.target.closest('.pop-panel')) closeAll();
    });
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      const open = $('.pop.open');
      if (open) { closeAll(); const t = $('[data-pop-trigger]', open); t && t.focus(); }
    });
  }

  /* ---------- toasts */
  function initToasts() {
    $$('.toast').forEach((t, i) => {
      const dismiss = () => { t.classList.add('leaving'); setTimeout(() => t.remove(), 240); };
      $('button', t) && $('button', t).addEventListener('click', dismiss);
      if (!t.classList.contains('error')) setTimeout(dismiss, 5200 + i * 600);
    });
  }
  window.ftToast = function (msg, kind = 'success') {
    let box = $('.toasts');
    if (!box) { box = document.createElement('div'); box.className = 'toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    const t = document.createElement('div');
    t.className = 'toast ' + kind; t.setAttribute('role', 'status');
    t.innerHTML = '<span class="t-msg"></span>';
    $('.t-msg', t).textContent = msg;
    box.appendChild(t);
    setTimeout(() => { t.classList.add('leaving'); setTimeout(() => t.remove(), 240); }, 4500);
  };

  /* ---------- tabs (ARIA tabs pattern; ?tab= kept in the URL) */
  function initTabs() {
    $$('[role="tablist"]').forEach(list => {
      const tabs = $$('[role="tab"]', list);
      const select = (tab, focus) => {
        tabs.forEach(t => {
          const on = t === tab;
          t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
          const panel = document.getElementById(t.getAttribute('aria-controls'));
          if (panel) panel.hidden = !on;
        });
        if (focus) tab.focus();
        if (list.dataset.urlParam) {
          const u = new URL(location.href); u.searchParams.set(list.dataset.urlParam, tab.dataset.key);
          history.replaceState(null, '', u);
        }
      };
      tabs.forEach((t, i) => {
        t.addEventListener('click', () => select(t));
        t.addEventListener('keydown', e => {
          let j = null;
          if (e.key === 'ArrowRight') j = (i + 1) % tabs.length;
          if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length;
          if (e.key === 'Home') j = 0;
          if (e.key === 'End') j = tabs.length - 1;
          if (j !== null) { e.preventDefault(); select(tabs[j], true); }
        });
      });
      $$('[data-goto-tab]').forEach(a => a.addEventListener('click', e => {
        const t = tabs.find(t => t.dataset.key === a.dataset.gotoTab);
        if (t) { e.preventDefault(); select(t); t.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
      }));
    });
  }

  /* ---------- modals: <dialog class="modal"> opened by [data-open="id"] */
  function initModals() {
    document.addEventListener('click', e => {
      const opener = e.target.closest('[data-open]');
      if (opener) {
        const d = document.getElementById(opener.dataset.open);
        if (d && d.showModal) { e.preventDefault(); d.showModal(); d.dispatchEvent(new CustomEvent('ft:open', { detail: opener })); }
      }
      const closer = e.target.closest('[data-close]');
      if (closer) { const d = closer.closest('dialog'); d && d.close(); }
    });
    $$('dialog.modal').forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));
  }

  /* ---------- confirmation for destructive forms */
  function initConfirm() {
    const dlg = $('#confirm-dialog');
    let pending = null;
    document.addEventListener('submit', e => {
      const form = e.target;
      if (!form.dataset.confirm || form.dataset.confirmed) return;
      e.preventDefault();
      if (!dlg) { if (confirm(form.dataset.confirm)) { form.dataset.confirmed = '1'; form.submit(); } return; }
      pending = form;
      $('#confirm-message', dlg).textContent = form.dataset.confirm;
      $('#confirm-ok', dlg).textContent = form.dataset.confirmLabel || 'Delete';
      dlg.showModal();
      $('#confirm-cancel', dlg).focus();
    });
    dlg && $('#confirm-ok', dlg).addEventListener('click', () => {
      if (pending) { pending.dataset.confirmed = '1'; dlg.close(); pending.submit(); }
    });
  }

  /* ---------- filter forms auto-submit; period selector reveals custom range */
  function initFilters() {
    $$('form[data-autosubmit]').forEach(form => {
      $$('select, input[type=date]', form).forEach(c => c.addEventListener('change', () => {
        if (c.name === 'period' && c.value === 'custom') {
          const box = $('[data-custom-range]', form); if (box) { box.hidden = false; $('input', box).focus(); }
          return;
        }
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }));
    });
    $$('[data-toggle]').forEach(btn => btn.addEventListener('click', () => {
      const t = document.getElementById(btn.dataset.toggle);
      if (!t) return;
      t.hidden = !t.hidden;
      btn.setAttribute('aria-expanded', String(!t.hidden));
    }));
    $$('[data-href]').forEach(row => row.addEventListener('click', e => {
      if (e.target.closest('a, button, input, select, label, form')) return;
      location.href = row.dataset.href;
    }));
  }

  /* ---------- global search: "/" focuses, mobile toggle */
  function initSearch() {
    const box = $('#global-search'), input = box && $('input', box);
    if (!input) return;
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !e.target.closest('input, textarea, select, [contenteditable]')) { e.preventDefault(); box.classList.add('mobile-open'); input.focus(); }
    });
    const mob = $('#search-toggle');
    mob && mob.addEventListener('click', () => { box.classList.toggle('mobile-open'); if (box.classList.contains('mobile-open')) input.focus(); });
    input.addEventListener('blur', () => setTimeout(() => box.classList.remove('mobile-open'), 150));
  }

  /* ---------- drop zones */
  function fileIcon(name) {
    const ext = (name.split('.').pop() || '').toLowerCase();
    if (ext === 'pdf') return '<span class="file-ico pdf">PDF</span>';
    if (['jpg', 'jpeg', 'png', 'webp', 'heic'].includes(ext)) return '<span class="file-ico img">IMG</span>';
    if (['xls', 'xlsx', 'csv'].includes(ext)) return '<span class="file-ico xls">XLS</span>';
    return '<span class="file-ico">' + ext.toUpperCase().slice(0, 4) + '</span>';
  }
  function fmtSize(n) { return n < 1024 * 1024 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB'; }
  function initDropzones() {
    $$('.dropzone').forEach(zone => {
      const input = $('input[type=file]', zone), list = zone.nextElementSibling && zone.nextElementSibling.matches('.dz-list') ? zone.nextElementSibling : null;
      const max = (+zone.dataset.maxMb || 20) * 1048576;
      const render = () => {
        if (!list) return;
        list.innerHTML = '';
        Array.from(input.files).forEach(f => {
          const row = document.createElement('div'); row.className = 'dz-file';
          row.innerHTML = fileIcon(f.name) + '<span class="fn"></span><span class="small muted">' + fmtSize(f.size) + '</span>';
          $('.fn', row).textContent = f.name;
          if (f.size > max) row.insertAdjacentHTML('beforeend', '<span class="badge badge-danger">Too large</span>');
          list.appendChild(row);
        });
        const nameInput = zone.form && zone.form.querySelector('[name="name"]');
        if (nameInput && !nameInput.value && input.files[0]) nameInput.value = input.files[0].name.replace(/\.[^.]+$/, '');
      };
      ['dragenter', 'dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('over'); }));
      ['dragleave', 'drop'].forEach(ev => zone.addEventListener(ev, () => zone.classList.remove('over')));
      zone.addEventListener('drop', e => {
        e.preventDefault();
        if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; render(); }
      });
      input.addEventListener('change', render);
    });
  }

  /* ---------- XHR upload with progress (document modal) */
  function initAjaxUpload() {
    $$('form[data-ajax-upload]').forEach(form => {
      form.addEventListener('submit', e => {
        e.preventDefault();
        const bar = $('.upload-progress', form), fill = bar && $('i', bar), btn = $('[type=submit]', form);
        $$('.error-text[data-js]', form).forEach(n => n.remove());
        $$('[aria-invalid]', form).forEach(n => n.removeAttribute('aria-invalid'));
        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.upload.addEventListener('progress', ev => { if (ev.lengthComputable && fill) fill.style.width = (ev.loaded / ev.total * 100) + '%'; });
        xhr.onload = () => {
          btn && btn.classList.remove('is-loading');
          let res = {};
          try { res = JSON.parse(xhr.responseText); } catch (_) { /* not JSON */ }
          if (xhr.status === 200 && res.ok) { location.href = res.redirect || location.href; return; }
          if (bar) bar.hidden = true;
          if (xhr.status === 403) { ftToast('You do not have permission to upload documents.', 'error'); return; }
          const errors = res.errors || { __all__: ['Upload failed. Please try again.'] };
          Object.entries(errors).forEach(([name, msgs]) => {
            const input = form.querySelector(`[name="${name}"]`);
            const p = document.createElement('p'); p.className = 'error-text'; p.dataset.js = '1'; p.textContent = msgs.join(' ');
            if (input) { input.setAttribute('aria-invalid', 'true'); (input.closest('.field, .dropzone') || input).after(p); }
            else form.querySelector('.modal-body').prepend(p);
          });
        };
        xhr.onerror = () => { btn && btn.classList.remove('is-loading'); if (bar) bar.hidden = true; ftToast('Network error — the file was not uploaded.', 'error'); };
        if (bar) { bar.hidden = false; fill.style.width = '0'; }
        btn && btn.classList.add('is-loading');
        xhr.send(new FormData(form));
      });
    });
  }

  /* ---------- document preview modal */
  function initPreview() {
    const dlg = $('#preview-dialog');
    if (!dlg) return;
    const body = $('.modal-body', dlg), title = $('#preview-title', dlg), dl = $('#preview-download', dlg);
    document.addEventListener('click', e => {
      const a = e.target.closest('[data-preview]');
      if (!a) return;
      e.preventDefault();
      title.textContent = a.dataset.name || 'Preview';
      dl.href = a.dataset.download || a.href;
      body.innerHTML = '<div class="skeleton" style="height:60vh"></div>';
      const src = a.dataset.preview;
      if (a.dataset.kind === 'image') {
        const img = new Image(); img.className = 'preview-img'; img.alt = a.dataset.name || '';
        img.onload = () => { body.innerHTML = ''; body.appendChild(img); };
        img.onerror = () => { body.innerHTML = '<p class="muted">Preview unavailable. Download the file instead.</p>'; };
        img.src = src;
      } else {
        const f = document.createElement('iframe'); f.className = 'preview-frame'; f.title = a.dataset.name || 'Document preview';
        f.onload = () => { const sk = $('.skeleton', body); sk && sk.remove(); f.hidden = false; };
        f.hidden = true; f.src = src; body.appendChild(f);
      }
      dlg.showModal();
    });
    dlg.addEventListener('close', () => { body.innerHTML = ''; });
  }

  /* ---------- conditional fields (vehicle type / ownership type) */
  function initConditional() {
    const form = $('form[data-vehicle-form]');
    if (!form) return;
    const type = form.querySelector('[name="vehicle_type"]'), own = form.querySelector('[name="ownership_type"]');
    const apply = () => {
      $$('[data-show-types], [data-show-ownership]', form).forEach(f => {
        const types = f.dataset.showTypes ? f.dataset.showTypes.split(',') : null;
        const owns = f.dataset.showOwnership ? f.dataset.showOwnership.split(',') : null;
        if (f.hasAttribute('data-needs-type') && !type.value) { f.hidden = true; return; }
        const show = (!types || !type.value || types.includes(type.value)) && (!owns || !own.value || owns.includes(own.value));
        f.hidden = !show;
      });
      $$('[data-only-motorised]', form).forEach(n => { n.hidden = type.value === 'trailer'; });
      $$('[data-only-trailer]', form).forEach(n => { n.hidden = type.value !== 'trailer'; });
      $$('[data-type-pick]', form).forEach(card => card.setAttribute('aria-checked', String(card.dataset.typePick === type.value)));
    };
    type && type.addEventListener('change', apply);
    own && own.addEventListener('change', apply);
    $$('[data-type-pick]', form).forEach(card => card.addEventListener('click', () => {
      type.value = card.dataset.typePick; type.dispatchEvent(new Event('change'));
    }));
    apply();
  }

  /* ---------- Add Vehicle wizard */
  function initWizard() {
    const form = $('form[data-wizard]');
    if (!form) return;
    const panels = $$('[data-step-panel]', form), buttons = $$('[data-step-btn]');
    const stepInput = form.querySelector('[name="step"]'), bar = $('.progress-line i');
    let current = +form.dataset.start || 1;
    const errorStep = panels.findIndex(p => p.querySelector('.error-text'));
    if (errorStep >= 0) current = errorStep + 1;

    function validate(panel) {
      let ok = true;
      $$('input, select, textarea', panel).forEach(c => {
        if (c.closest('[hidden]')) return;
        if (!c.checkValidity()) { ok = false; c.setAttribute('aria-invalid', 'true'); }
        else if (!c.closest('.field')?.querySelector('.error-text')) c.removeAttribute('aria-invalid');
      });
      if (!ok) { const bad = panel.querySelector('[aria-invalid="true"]'); bad && bad.focus(); bad && bad.reportValidity(); }
      return ok;
    }
    function go(n, opts = {}) {
      if (n > current && !opts.skipCheck) {
        for (let i = current; i < n; i++) if (!validate(panels[i - 1])) { show(i); return; }
      }
      show(n);
    }
    function show(n) {
      current = Math.max(1, Math.min(panels.length, n));
      panels.forEach((p, i) => { p.hidden = i + 1 !== current; });
      buttons.forEach((b, i) => {
        b.toggleAttribute('aria-current', i + 1 === current);
        if (i + 1 === current) b.setAttribute('aria-current', 'step');
        b.classList.toggle('done', i + 1 < current && !b.classList.contains('has-error'));
      });
      if (stepInput) stepInput.value = current;
      if (bar) bar.style.width = ((current - 1) / (panels.length - 1) * 100) + '%';
      $$('[data-prev]', form).forEach(b => { b.hidden = current === 1; });
      $$('[data-next]', form).forEach(b => { b.hidden = current === panels.length; });
      $$('[data-finish]', form).forEach(b => { b.hidden = current !== panels.length; });
      if (current === panels.length) buildReview();
      const h = panels[current - 1].querySelector('h2'); h && h.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
    function buildReview() {
      $$('[data-review]', form).forEach(block => {
        const dl = $('dl', block); dl.innerHTML = '';
        const panel = panels[+block.dataset.review - 1];
        let any = false;
        // The step panels themselves are hidden here, so only look for hidden ancestors inside the panel.
        const hiddenInPanel = el => { for (let n = el; n && n !== panel; n = n.parentElement) if (n.hidden) return true; return false; };
        $$('.field', panel).forEach(f => {
          if (hiddenInPanel(f)) return;
          const c = f.querySelector('input:not([type=hidden]), select, textarea'); if (!c || c.type === 'file') return;
          let v = c.tagName === 'SELECT' ? (c.value ? c.options[c.selectedIndex].text : '') : (c.type === 'checkbox' ? (c.checked ? 'Yes' : '') : c.value);
          if (!v) return;
          any = true;
          const labelEl = f.querySelector('label, .field-label');
          let label = c.name;
          if (labelEl) { const copy = labelEl.cloneNode(true); copy.querySelectorAll('.sr-only, .req, input, select').forEach(n => n.remove()); label = copy.textContent; }
          dl.insertAdjacentHTML('beforeend', '<dt></dt><dd></dd>');
          dl.lastElementChild.previousElementSibling.textContent = label.replace('*', '').trim();
          dl.lastElementChild.textContent = v;
        });
        if (!any) dl.innerHTML = '<dt class="not-recorded">Nothing entered</dt><dd></dd>';
      });
    }
    buttons.forEach((b, i) => b.addEventListener('click', () => go(i + 1)));
    $$('[data-next]', form).forEach(b => b.addEventListener('click', () => go(current + 1)));
    $$('[data-prev]', form).forEach(b => b.addEventListener('click', () => go(current - 1, { skipCheck: true })));
    $$('[data-edit-step]', form).forEach(b => b.addEventListener('click', () => go(+b.dataset.editStep, { skipCheck: true })));
    // Drafts skip browser validation entirely.
    $$('button[value="draft"]', form).forEach(b => b.addEventListener('click', () => { form.noValidate = true; }));
    form.addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target.tagName === 'INPUT' && current < panels.length) { e.preventDefault(); go(current + 1); }
    });
    show(current);
  }

  /* ---------- header: stronger surface once the page has scrolled under it */
  function initStickyHeader() {
    const bar = $('.topbar');
    if (!bar) return;
    const update = () => bar.classList.toggle('is-stuck', window.scrollY > 8);
    window.addEventListener('scroll', update, { passive: true });
    update();
  }

  /* ---------- prevent double submits */
  function initSubmitGuard() {
    document.addEventListener('submit', e => {
      const f = e.target;
      if (e.defaultPrevented || f.dataset.ajaxUpload !== undefined || f.method.toLowerCase() !== 'post') return;
      const b = e.submitter;
      if (b) setTimeout(() => b.classList.add('is-loading'), 0);
    });
    window.addEventListener('pageshow', () => $$('.is-loading').forEach(b => b.classList.remove('is-loading')));
  }

  document.addEventListener('DOMContentLoaded', () => {
    initDrawer(); initStickyHeader(); initPopovers(); initToasts(); initTabs(); initModals(); initConfirm(); initFilters();
    initSearch(); initDropzones(); initAjaxUpload(); initPreview(); initConditional(); initWizard(); initSubmitGuard();
  });
})();
