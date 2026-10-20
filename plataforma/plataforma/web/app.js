// Plataforma de prospecção — interface de página única (sem build, sem dependências).
// Todo valor interpolado em html`` é escapado; só raw() injeta marcação (usado para ícones e trechos já montados).

const RAW = Symbol('raw');
const raw = (s) => ({ [RAW]: String(s ?? '') });
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const R = (v) => (v == null || v === false ? '' : Array.isArray(v) ? v.map(R).join('') : typeof v === 'object' && RAW in v ? v[RAW] : esc(v));
const html = (s, ...v) => raw(s.reduce((o, str, i) => o + str + (i < v.length ? R(v[i]) : ''), ''));
const put = (el, h) => { if (el) el.innerHTML = R(h); };
const $ = (sel, base = document) => base.querySelector(sel);
const $$ = (sel, base = document) => [...base.querySelectorAll(sel)];

// ------------------------------------------------------------------------------------------- ícones
const P = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/>',
  predio: '<path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/><path d="M16 9h2a2 2 0 0 1 2 2v10"/><path d="M2 21h20M8 7h4M8 11h4M8 15h4"/>',
  pessoas: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>',
  historico: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 3"/>',
  revisao: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
  ajustes: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  busca: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  baixar: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  atualizar: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  pausa: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
  arquivo: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>',
  externo: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  copiar: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  claude: '<path d="M12 3l1.9 5.6 5.6 1.9-5.6 1.9L12 18l-1.9-5.6-5.6-1.9 5.6-1.9z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  alerta: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17.5v.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.5"/>',
  relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  meia: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
  circulo: '<circle cx="12" cy="12" r="8"/>',
  tel: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  whats: '<path d="M3 21l1.6-4.8A8.5 8.5 0 1 1 7.8 19.4z"/><path d="M9 10c.5 2 2.5 4 4.5 4.5"/>',
  email: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  site: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  voltar: '<path d="M15 18l-6-6 6-6"/>',
  seta: '<path d="M9 18l6-6-6-6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  tema: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  mais: '<path d="M12 5v14M5 12h14"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  mapa: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  filtro: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
  fila: '<path d="M4 6h10M4 12h10M4 18h6"/><path d="M17 15l3 3-3 3"/><path d="M20 18h-6"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
};
const ic = (n) => raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ''}</svg>`);

// ------------------------------------------------------------------------------------------- formatação
const nf = new Intl.NumberFormat('pt-BR');
const num = (n) => (n == null || n === '' ? '—' : nf.format(n));
const pad = (n) => String(n).padStart(2, '0');
function data(iso, hora = true) {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? iso + 'T00:00:00' : iso);
  if (isNaN(d)) return iso;
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}` + (hora && iso.length > 10 ? ` ${pad(d.getHours())}:${pad(d.getMinutes())}` : '');
}
function rel(iso) {
  if (!iso) return '—';
  const s = (Date.now() - new Date(iso)) / 1000;
  if (isNaN(s)) return iso;
  if (s < 60) return 'agora';
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  if (s < 86400 * 30) return `há ${Math.floor(s / 86400)} d`;
  return data(iso, false);
}
function duracao(s) {
  s = Math.round(s || 0);
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h ${pad(Math.floor((s % 3600) / 60))} min`;
}
const plural = (n, um, varios) => `${num(n)} ${n === 1 ? um : varios}`;
const handle = (url) => { const m = String(url || '').match(/instagram\.com\/([A-Za-z0-9._]+)/); return m ? m[1].toLowerCase() : ''; };

// ------------------------------------------------------------------------------------------- vocabulário de estados
const EST_EXEC = {
  criada: ['', 'Criada', 'circulo'], em_andamento: ['info', 'Em andamento', 'play'], aguardando: ['atencao', 'Aguardando o Instagram', 'relogio'],
  concluida: ['bom', 'Concluída', 'check'], concluida_parcial: ['atencao', 'Concluída parcialmente', 'meia'],
  concluida_com_falhas: ['serio', 'Concluída com falhas', 'alerta'], interrompida: ['serio', 'Interrompida', 'pausa'],
  pausada: ['atencao', 'Pausada', 'pausa'], parada: ['serio', 'Parada sem finalizar', 'alerta'],
  precisa_acao: ['critico', 'Precisa de você', 'alerta'], falhou: ['critico', 'Falhou', 'x'],
};
const ST_EMP = {
  identificada: ['bom', 'CNPJ confirmado', 'check'], provavel: ['nc', 'CNPJ provável', 'meia'], parcial: ['atencao', 'Sem CNPJ', 'meia'],
  ambigua: ['serio', 'Ambígua', 'alerta'], nao_encontrada: ['', 'Não encontrada', 'circulo'], erro: ['critico', 'Erro técnico', 'x'],
};
const EST_CAMPO = {
  confirmado: ['bom', 'Confirmado', 'check'], parcial: ['atencao', 'Parcialmente confirmado', 'meia'],
  nao_confirmado: ['nc', 'Não confirmado', 'alerta'], nao_encontrado: ['', 'Não encontrado', 'circulo'], vazio: ['', 'Vazio', 'circulo'],
};
const SIT_PERFIL = {
  identificado: ['bom', 'Identificado', 'check'], revisar: ['atencao', 'Revisar', 'meia'],
  sem_correspondencia: ['', 'Sem correspondência', 'circulo'], descartado: ['', 'Descartado', 'x'],
};
const EST_VINC = { confirmado: ['bom', 'Confirmado', 'check'], sugerido: ['nc', 'Sugerido', 'meia'], rejeitado: ['', 'Rejeitado', 'x'] };
const TIPO = { instagram: ['instagram', 'Análise do Instagram'], empresas: ['predio', 'Pesquisa de empresas'], revisao_claude: ['claude', 'Revisão pelo Claude'] };
const ORIGEM = { entrada: 'informado na lista', cadastro: 'cadastro da Receita', site: 'site oficial', instagram: 'perfil do Instagram',
  busca: 'resultado de busca', cep: 'consulta de CEP', gerado: 'gerado pela ferramenta', revisao: 'revisão', dominio: 'link da bio', manual: 'manual' };
const badge = (mapa, v, texto) => { const [c, r, i] = mapa[v] || ['', v || '—', 'circulo']; return html`<span class="badge ${c}">${ic(i)}${texto || r}</span>`; };
const conf = (c) => (c ? html`<span class="chip" title="Confiança">${{ alta: 'conf. alta', media: 'conf. média', baixa: 'conf. baixa' }[c] || c}</span>` : '');

let SEGS = [];
const segNome = (c) => (SEGS.find((s) => s.codigo === c) || {}).nome || c;
const segChips = (perfil = [], inferido = []) => html`<span class="chips">${perfil.map((s) => html`<span class="chip seg" title="${segNome(s)} (perfil do Instagram identificado)">${s}</span>`)}${inferido.map((s) => html`<span class="chip seg inferido" title="${segNome(s)} (inferido pelo nome/categoria; não confirmado)">${s}</span>`)}</span>`;

// ------------------------------------------------------------------------------------------- API
async function api(url, { global = false } = {}) {
  // requisições da página são canceladas ao navegar: nada da página anterior é desenhado na seguinte
  const r = await fetch(url, { headers: { Accept: 'application/json' }, signal: global ? undefined : app.controle.signal });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erro || `Erro ${r.status}`);
  return d;
}
async function post(url, dados = {}) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erro || `Erro ${r.status}`);
  return d;
}
const semErro = (promessa, padrao) => promessa.catch((e) => { if (e.name === 'AbortError') throw e; return padrao; });
const urlSegura = (u) => (/^https?:\/\//i.test(String(u || '')) ? String(u) : '');
function depois(fn, ms) { const t = setTimeout(() => { app.timers.delete(t); fn(); }, ms); app.timers.add(t); return t; }
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v != null && !(Array.isArray(v) && !v.length)).map(([k, v]) => [k, Array.isArray(v) ? v.join(',') : v])).toString();

// ------------------------------------------------------------------------------------------- avisos, diálogos
function toast(msg, erro = false) {
  const t = document.createElement('div');
  t.className = 'toast' + (erro ? ' erro' : '');
  put(t, html`${ic(erro ? 'alerta' : 'check')}<span>${msg}</span>`);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), erro ? 8000 : 4500);
}
function dialogo(titulo, corpo, botoes) {
  // botoes: [{rotulo, classe, valor}] — devolve a Promise com o valor do botão (ou null ao fechar)
  const d = $('#dialogo');
  put(d, html`<form method="dialog"><div class="dlg-cab"><h2>${titulo}</h2><button class="icone-btn" value="" aria-label="Fechar">${ic('x')}</button></div>
    <div class="dlg-corpo">${corpo}</div>
    <div class="dlg-rodape">${botoes.map((b) => html`<button class="btn ${b.classe || ''}" value="${b.valor}">${b.rotulo}</button>`)}</div></form>`);
  d.returnValue = '';
  d.showModal();
  return new Promise((ok) => d.addEventListener('close', () => ok(d.returnValue || null), { once: true }));
}
async function copiar(texto) {
  try { await navigator.clipboard.writeText(texto); toast('Pedido copiado. Cole no chat do Claude Code.'); }
  catch { await dialogo('Copie o pedido', html`<textarea readonly>${texto}</textarea>`, [{ rotulo: 'Fechar', valor: 'ok' }]); }
}
async function executar(fn, ok) {
  try { const r = await fn(); if (ok) toast(typeof ok === 'function' ? ok(r) : ok); return r; }
  catch (e) { if (e.name !== 'AbortError') toast(e.message, true); return null; }
}

// ------------------------------------------------------------------------------------------- componentes
function multi(nome, rotulo, opcoes, sel) {
  const s = new Set(sel);
  return html`<details class="multi" data-multi="${nome}"><summary>${rotulo}${s.size ? html` <span class="qt">${s.size}</span>` : ''}</summary>
    <div class="painel">${opcoes.length ? opcoes.map((o) => o.grupo ? html`<div class="grupo">${o.grupo}</div>` :
      html`<label><input type="checkbox" value="${o.valor}" ${s.has(String(o.valor)) ? 'checked' : ''}> <span>${o.rotulo ?? o.valor}</span>${o.n != null ? html`<span class="n">${num(o.n)}</span>` : ''}</label>`) : html`<div class="mut pequeno-txt" style="padding:8px">Sem opções.</div>`}</div></details>`;
}
function selecao(nome, rotulo, opcoes, atual) {
  return html`<select data-sel="${nome}" aria-label="${rotulo}"><option value="">${rotulo}</option>${opcoes.map(([v, r]) => html`<option value="${v}" ${String(atual ?? '') === String(v) ? 'selected' : ''}>${r}</option>`)}</select>`;
}
function paginacao(d, acao = 'pagina') {
  if (d.paginas <= 1) return '';
  return html`<div class="paginacao"><span>Página ${d.pagina} de ${d.paginas}</span>
    <button class="btn pequeno" data-acao="${acao}" data-pagina="${d.pagina - 1}" ${d.pagina <= 1 ? 'disabled' : ''}>Anterior</button>
    <button class="btn pequeno" data-acao="${acao}" data-pagina="${d.pagina + 1}" ${d.pagina >= d.paginas ? 'disabled' : ''}>Próxima</button></div>`;
}
function barra(pct, indef = false) {
  return html`<div class="barra ${indef ? 'indef' : ''}" role="progressbar" aria-valuemin="0" aria-valuemax="100" ${pct != null ? raw(`aria-valuenow="${Math.round(pct)}"`) : ''}><i style="width:${Math.max(0, Math.min(100, pct || 0)).toFixed(1)}%"></i></div>`;
}
function hbarras(itens, max) {
  max = max || Math.max(1, ...itens.map((i) => i.n));
  return html`<div class="hbarras">${itens.map((i) => {
    const corpo = html`<span class="rot" title="${i.titulo || i.rotulo}">${i.rotulo}</span><span class="trilho"><i style="width:${(100 * i.n / max).toFixed(1)}%"></i></span><span class="v">${num(i.n)}</span>`;
    return i.href ? html`<a class="hbarra" href="${i.href}">${corpo}</a>` : html`<div class="hbarra">${corpo}</div>`;
  })}</div>`;
}
function vazio(titulo, texto = '') { return html`<div class="vazio"><strong>${titulo}</strong>${texto}</div>`; }
function progressoExec(x) {
  if (x.tipo === 'revisao_claude') return `${plural(x.processados || 0, 'ação', 'ações')}`;
  const verbo = x.tipo === 'instagram' ? 'analisados' : 'pesquisadas';
  return `${num(x.processados || 0)} de ${num(x.total || 0)} ${verbo}` + (x.falhas ? ` · ${plural(x.falhas, 'falha', 'falhas')}` : '');
}
function itemExec(x) {
  const [i] = TIPO[x.tipo] || ['circulo'];
  return html`<a class="item-exec" href="#/execucoes/${encodeURIComponent(x.id)}"><span class="tipo-ico">${ic(i)}</span>
    <span style="min-width:0"><span class="t">${x.referencia || x.nome}</span><span class="s">${[progressoExec(x), x.tipo === 'empresas' && !x.em_andamento ? '' : x.ultima_etapa, rel(x.atualizado || x.criado)].filter(Boolean).join(' · ')}</span></span>
    ${badge(EST_EXEC, x.estado)}</a>`;
}

// ------------------------------------------------------------------------------------------- roteamento
const app = { token: 0, timer: null, acoes: {}, mudar: null, enviar: {}, pagina: {}, controle: new AbortController(), timers: new Set(), navegacoes: 0 };
const ROTAS = [];
const NAO_ENCONTRADA = { titulo: 'Página não encontrada', menu: '', fn: (el) => put(el, html`<div class="card">${vazio('Página não encontrada.', html`<br><a href="#/">Ir para a visão geral</a>`)}</div>`) };
const rota = (re, titulo, menu, fn) => ROTAS.push({ re, titulo, menu, fn });

function hashAtual() {
  const h = location.hash.slice(1) || '/';
  const [caminho, query] = h.split('?');
  return { caminho, q: Object.fromEntries(new URLSearchParams(query || '')) };
}
function trocarQuery(q) {
  const { caminho } = hashAtual();
  const s = qs(q);
  history.replaceState(null, '', '#' + caminho + (s ? '?' + s : ''));
}
async function navegar() {
  const token = ++app.token;
  app.navegacoes++;
  clearTimeout(app.timer);
  app.controle.abort();
  app.controle = new AbortController();
  app.timers.forEach(clearTimeout); app.timers.clear();
  app.acoes = {}; app.mudar = null; app.enviar = {}; app.pagina = {};
  $('#lateral').classList.remove('aberta');
  const { caminho, q } = hashAtual();
  let alvo = NAO_ENCONTRADA, m = null;
  for (const r of ROTAS) { const x = caminho.match(r.re); if (x) { alvo = r; m = x; break; } }
  $('#titulo').textContent = alvo.titulo;
  document.title = `${alvo.titulo} · Prospecção`;
  $$('#menu a').forEach((a) => { if (a.dataset.menu === alvo.menu) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  const main = $('#conteudo');
  put(main, html`<div class="carregando">Carregando…</div>`);
  try {
    const p = (await alvo.fn(main, (m || []).slice(1).map(decodeURIComponent), q)) || {};
    if (token !== app.token) return;
    app.pagina = p;
    agendar(token);
  } catch (e) {
    if (token === app.token && e.name !== 'AbortError') put(main, html`<div class="card">${vazio('Não foi possível carregar esta página.', e.message)}</div>`);
  }
  window.scrollTo(0, 0);
}
function agendar(token) {
  const p = app.pagina;
  if (!p.atualizar) return;
  app.timer = setTimeout(async () => {
    if (token !== app.token) return;
    if (!document.hidden) { try { await p.atualizar(); } catch { /* tenta de novo no próximo ciclo */ } }
    if (token === app.token) agendar(token);
  }, typeof p.intervalo === 'function' ? p.intervalo() : p.intervalo || 6000);
}

// eventos delegados
document.addEventListener('click', (e) => {
  const linha = e.target.closest('tr[data-href]');
  if (linha && !e.target.closest('a,button,input,label,select')) { location.hash = linha.dataset.href; return; }
  const el = e.target.closest('[data-acao]');
  if (el && !el.disabled) { const fn = app.acoes[el.dataset.acao] || GLOBAIS[el.dataset.acao]; if (fn) { if (!el.matches('input')) e.preventDefault(); fn(el, e); } }
  $$('details.multi[open]').forEach((d) => { if (!d.contains(e.target)) d.open = false; });
});
document.addEventListener('change', (e) => app.mudar && app.mudar(e.target, e));
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const aberto = e.target.closest?.('details.multi[open]') || $('details.multi[open]');
  if (aberto) { aberto.open = false; $('summary', aberto).focus(); }
});
document.addEventListener('focusin', (e) => $$('details.multi[open]').forEach((d) => { if (!d.contains(e.target)) d.open = false; }));
// painel do filtro nunca sai da tela (filtros à direita ou em tela estreita)
document.addEventListener('toggle', (e) => {
  const d = e.target;
  if (!d.matches?.('details.multi') || !d.open) return;
  const p = $('.painel', d);
  p.style.left = '0px';
  const r = p.getBoundingClientRect(), vw = document.documentElement.clientWidth;
  if (r.right > vw - 8) p.style.left = `${Math.min(0, vw - 8 - r.right)}px`;
}, true);
document.addEventListener('input', (e) => app.mudar && e.target.matches('input[type=search],[data-digitar]') && app.mudar(e.target, e));
document.addEventListener('submit', (e) => {
  const f = e.target.closest('form[data-form]');
  if (f && app.enviar[f.dataset.form]) { e.preventDefault(); app.enviar[f.dataset.form](f, e); }
});
const GLOBAIS = {
  voltar: (el) => { if (app.navegacoes > 1) history.back(); else location.hash = el.getAttribute('href'); },
  filtros_painel: (b) => { const p = $('#filtros-painel'); if (!p) return; p.hidden = !p.hidden; b.setAttribute('aria-expanded', String(!p.hidden)); },
  aba_exec: (b) => {
    $$('[data-acao=aba_exec]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    $$('[data-painel]').forEach((p) => { p.hidden = p.dataset.painel !== b.dataset.aba; });
  },
  copiar_pedido: async (el) => {
    const max = document.getElementById('claude-max-' + el.dataset.id.replace(/[^a-z0-9]/gi, ''))?.value || el.dataset.max || '';
    const d = await executar(() => api(`/api/execucoes/${encodeURIComponent(el.dataset.id)}/pedido-claude?max=${max}`)); if (d) copiar(d.texto);
  },
  claude_fundo: async (el) => {
    const max = document.getElementById('claude-max-' + el.dataset.id.replace(/[^a-z0-9]/gi, ''))?.value || '';
    const tipo = el.dataset.id.startsWith('emp:') ? 'empresas' : 'instagram';
    const ok = await dialogo('Revisar em segundo plano com o Claude Code', html`
      <p>O Claude Code vai revisar ${max ? html`até <b>${max}</b>` : 'os'} itens incertos <b>sem interação</b>, usando a sua assinatura (consome a cota de uso).</p>
      <p>Ele só pode executar ${tipo === 'empresas' ? html`a ferramenta <code>empresas</code> e fazer buscas e leituras na web` : html`a ferramenta <code>prospeccao</code>, decidindo só com o que está no pacote de revisão`}.
      Cada decisão fica registrada e nada é apagado.</p>
      <p class="mut">Acompanhe em Execuções; você pode parar a qualquer momento.</p>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Iniciar revisão', classe: 'primario', valor: 'ok' }]);
    if (ok !== 'ok') return;
    const r = await executar(() => post(`/api/execucoes/${encodeURIComponent(el.dataset.id)}/claude`, { max_itens: max || null }), 'Revisão iniciada.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  },
};

// ------------------------------------------------------------------------------------------- casca
const MENU = [
  ['visao', '#/', 'home', 'Visão geral'], ['instagram', '#/instagram', 'instagram', 'Instagram'],
  ['fila', '#/fila', 'fila', 'Fila de pesquisa'],
  ['empresas', '#/empresas', 'predio', 'Empresas'], ['perfis', '#/perfis', 'pessoas', 'Perfis'],
  ['execucoes', '#/execucoes', 'historico', 'Execuções'], ['revisao', '#/revisao', 'revisao', 'Revisão'],
  ['sistema', '#/sistema', 'ajustes', 'Sistema'],
];
function montarCasca() {
  put($('#menu'), MENU.map(([k, href, i, r]) => html`<a href="${href}" data-menu="${k}">${ic(i)}<span>${r}</span>${['execucoes', 'revisao', 'fila'].includes(k) ? html`<span class="contador" id="cont-${k}" hidden></span>` : ''}</a>`));
  put($('#menu-btn'), ic('menu'));
  put($('#tema-btn'), ic('tema'));
  $('#menu-btn').addEventListener('click', () => { const a = $('#lateral').classList.toggle('aberta'); $('#menu-btn').setAttribute('aria-expanded', a); });
  const tema = localGet('tema');
  if (tema) document.documentElement.dataset.theme = tema;
  $('#tema-btn').addEventListener('click', () => {
    const escuro = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = escuro ? 'light' : 'dark';
    localSet('tema', document.documentElement.dataset.theme);
  });
  $('#busca-global').addEventListener('submit', (e) => { e.preventDefault(); const q = $('#busca-global-q').value.trim(); const alvo = '#/empresas' + (q ? '?q=' + encodeURIComponent(q) : ''); if (location.hash === alvo) navegar(); else location.hash = alvo; });
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !e.target.closest('input,textarea,select')) { e.preventDefault(); $('#busca-global-q').focus(); }
  });
}
function localGet(k) { try { return localStorage.getItem('prospeccao.' + k); } catch { return null; } }
function localSet(k, v) { try { localStorage.setItem('prospeccao.' + k, v); } catch { /* sem armazenamento */ } }
async function statusGlobal() {
  try {
    const s = await api('/api/status', { global: true });
    const ce = $('#cont-execucoes'), cr = $('#cont-revisao');
    ce.hidden = !s.em_andamento; ce.textContent = s.em_andamento; ce.classList.toggle('ativo', !!s.em_andamento);
    const pend = s.pendencias.duplicidades + s.pendencias.vinculos_sugeridos;
    cr.hidden = !pend; cr.textContent = pend;
    const cfila = $('#cont-fila'), nfila = s.pendencias.fila_pendentes || 0;
    cfila.hidden = !nfila; cfila.textContent = nfila;
    put($('#lateral-rodape'), html`<span class="pulso ${s.em_andamento ? 'rodando' : ''}"></span>${s.em_andamento ? plural(s.em_andamento, 'execução em andamento', 'execuções em andamento') : 'Nenhuma execução em andamento'}<br><span>Base lida às ${s.agora.slice(11, 16)}</span>`);
  } catch {
    put($('#lateral-rodape'), html`<span class="pulso" style="background:var(--critical)"></span>Sem conexão com a plataforma`);
  }
}

// ======================================================================================= VISÃO GERAL
rota(/^\/?$/, 'Visão geral', 'visao', async (el) => {
  let ultimo = '';
  const render = async () => {
    const d = await api('/api/visao-geral');
    const assinatura = JSON.stringify(d);
    if (assinatura === ultimo) return;
    ultimo = assinatura;
    const e = d.empresas, p = d.perfis, x = d.execucoes, pend = d.pendencias;
    const st = e.por_status;
    const passos = [];
    if (pend.fila_pendentes) passos.push([pend.fila_pendentes, 'perfis na fila esperando os dados da empresa', '#/fila']);
    if (pend.empresas_revisar) passos.push([pend.empresas_revisar, 'empresas com dados incertos para revisar', '#/empresas?pendencia=revisar']);
    if (pend.duplicidades) passos.push([pend.duplicidades, 'possíveis duplicidades para decidir', '#/revisao']);
    if (pend.vinculos_sugeridos) passos.push([pend.vinculos_sugeridos, 'vínculos perfil ↔ empresa sugeridos', '#/revisao?aba=vinculos']);
    if (pend.perfis_revisar) passos.push([pend.perfis_revisar, 'perfis duvidosos no pacote de revisão', '#/revisao?aba=claude']);
    const segs = p.por_segmento.filter((s) => s.n).sort((a, b) => b.n - a.n);
    put(el, html`
      <div class="tiles">
        <a class="tile" href="#/empresas"><span class="rotulo">Empresas na base</span><span class="valor">${num(e.total)}</span>
          <span class="detalhe">${num(st.identificada || 0)} com CNPJ confirmado · ${num(st.provavel || 0)} prováveis</span></a>
        <a class="tile" href="#/perfis?situacao=identificado"><span class="rotulo">Perfis identificados</span><span class="valor">${num(p.identificados)}</span>
          <span class="detalhe">de ${num(p.total)} perfis analisados · ${num(p.revisar)} para revisar</span></a>
        <a class="tile" href="#/fila"><span class="rotulo">Na fila de pesquisa</span><span class="valor">${num(pend.fila_pendentes || 0)}</span>
          <span class="detalhe">perfis identificados esperando os dados da empresa</span></a>
      </div>
      <div class="grade g-lado" style="margin-top:16px">
        <div>
          ${x.em_andamento.length ? html`<section class="card"><div class="card-cab"><h2>Em andamento</h2></div>
            <div class="lista-exec">${x.em_andamento.map(itemExec)}</div></section>` : ''}
          ${x.atencao.length ? html`<section class="card"><div class="card-cab"><h2>Precisa de atenção</h2></div>
            <div class="lista-exec">${x.atencao.map(itemExec)}</div></section>` : ''}
          <section class="card"><div class="card-cab"><h2>Atividade recente</h2><a class="btn fantasma pequeno" href="#/execucoes">Ver todas ${ic('seta')}</a></div>
            ${x.recentes.length ? html`<div class="lista-exec">${x.recentes.map(itemExec)}</div>` : vazio('Nenhuma execução ainda.', 'Comece por uma análise do Instagram ou uma pesquisa de empresas.')}</section>
        </div>
        <div>
          <section class="card"><div class="card-cab"><h2>Próximos passos</h2></div>
            ${passos.length ? html`<div class="passos">${passos.map(([n, t, h]) => html`<a class="passo" href="${h}"><span class="n">${num(n)}</span><span>${t}</span>${ic('seta')}</a>`)}</div>` : vazio('Tudo em dia.')}
            <div class="acoes" style="margin-top:14px"><a class="btn primario" href="#/instagram">${ic('instagram')}Nova análise</a><a class="btn" href="#/empresas?nova=1">${ic('predio')}Pesquisar empresas</a></div>
          </section>
          <section class="card"><div class="card-cab"><h2>Perfis identificados por segmento</h2></div>
            ${segs.length ? hbarras(segs.map((s) => ({ rotulo: `${s.codigo} · ${s.nome}`, titulo: s.descricao, n: s.n, href: `#/perfis?situacao=identificado&segmento=${s.codigo}` }))) : vazio('Nenhum perfil identificado ainda.')}
          </section>
          <section class="card"><div class="card-cab"><h2>Qualidade da base de empresas</h2></div>
            <dl class="dl">
              <dt>Com dados não confirmados</dt><dd><a href="#/empresas?pendencia=nao_confirmados">${num(e.com_nao_confirmados)}</a></dd>
              <dt>Para revisar</dt><dd><a href="#/empresas?pendencia=revisar">${num(e.precisa_revisao)}</a></dd>
              <dt>Sem telefone, WhatsApp ou e-mail</dt><dd><a href="#/empresas?contato=sem">${num(e.sem_contato)}</a></dd>
              <dt>Desatualizadas (pesquisa antiga)</dt><dd><a href="#/empresas?pendencia=desatualizada">${num(e.desatualizadas)}</a></dd>
              <dt>Com perfil do Instagram confirmado</dt><dd><a href="#/empresas?instagram=vinculado">${num(e.com_perfil)}</a></dd>
            </dl></section>
        </div>
      </div>`);
  };
  await render();
  return { atualizar: render, intervalo: 8000 };
});

// ======================================================================================= INSTAGRAM
rota(/^\/instagram$/, 'Pesquisa no Instagram', 'instagram', async (el) => {
  const [sis] = await Promise.all([semErro(api('/api/sistema'), {}), carregarSegmentos()]);
  const sessao = sis.sessao_instagram || {};
  put(el, html`
    <div class="grade g-lado">
      <section class="card"><div class="card-cab"><h2>Nova análise de seguidores</h2></div>
        <form data-form="analisar" class="grade" style="gap:14px">
          <div class="linha-form">
            <label class="campo">@ do perfil de origem<input type="text" name="origem" placeholder="@feirafunerariabrasil" required autocomplete="off"></label>
            <label class="campo">Limite de seguidores<input type="number" name="limite" min="1" placeholder="sem limite"></label>
            <label class="campo">Leitura de bio/categoria<select name="detalhes"><option value="candidatos">candidatos</option><option value="todos">todos (mais lento)</option><option value="nenhum">nenhum (só @ e nome)</option></select></label>
            <label class="campo">Publicações<select name="publicacoes"><option value="duvidosos">dos duvidosos</option><option value="nenhuma">não ler</option></select></label>
          </div>
          <fieldset style="border:0;padding:0;margin:0"><legend class="campo" style="font-size:12.5px;font-weight:600;color:var(--text-2)">Segmentos a encontrar
            <label class="marcar" style="margin-left:10px;font-weight:400"><input type="checkbox" data-acao="todas" checked> todos</label></legend>
            <div class="segmentos-grade">${SEGS.map((s) => html`<label class="marcar" title="${s.descricao}"><input type="checkbox" name="cat" value="${s.codigo}" checked> <b>${s.codigo}</b> ${s.nome}</label>`)}</div>
          </fieldset>
          <label class="marcar"><input type="checkbox" name="noite"> <span><b>Modo noite</b> <span class="mut">— continua sozinho se o Instagram pedir para esperar ou a conexão cair</span></span></label>
          <div class="acoes"><button class="btn primario" ${sessao.configurada ? '' : 'disabled'}>${ic('play')}Iniciar análise</button>
            ${sessao.configurada ? '' : html`<span class="mut pequeno-txt">Configure a sessão do Instagram em <a href="#/sistema">Sistema</a> para coletar.</span>`}</div>
        </form></section>
      <section class="card"><div class="card-cab"><h2>Sessão do Instagram</h2></div>
        ${sessao.configurada ? html`<p>${badge({ ok: ['bom', 'Configurada', 'check'] }, 'ok')} <span class="mut pequeno-txt">${sessao.origem || ''} ${sessao.salvo_em ? '· ' + data(sessao.salvo_em) : ''}</span></p>`
          : html`<p>${badge({ n: ['critico', 'Não configurada', 'alerta'] }, 'n')}</p>`}
        <a class="btn" href="#/sistema">${ic('ajustes')}Gerenciar sessão</a>
        
      </section>
    </div>
    <section class="card"><div class="card-cab"><h2>Análises</h2></div><div id="lista-ig"></div></section>`);

  app.acoes.todas = (cb) => $$('input[name=cat]', el).forEach((x) => (x.checked = cb.checked));
  app.mudar = (t) => {
    if (t.name !== 'cat') return;
    const todas = $('[data-acao=todas]', el), cs = $$('input[name=cat]', el);
    todas.checked = cs.every((x) => x.checked);
    todas.indeterminate = !todas.checked && cs.some((x) => x.checked);
  };
  app.enviar.analisar = async (f) => {
    const fd = new FormData(f);
    const cats = fd.getAll('cat');
    if (!cats.length) return toast('Escolha ao menos um segmento.', true);
    const botao = $('button.primario', f); botao.disabled = true;
    const r = await executar(() => post('/api/instagram/analisar', { origem: fd.get('origem'), limite: fd.get('limite') || null, detalhes: fd.get('detalhes'),
      publicacoes: fd.get('publicacoes'), noite: fd.get('noite') === 'on', categorias: cats.length === SEGS.length ? null : cats }), 'Análise iniciada.');
    botao.disabled = false;
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  };
  let ativo = false;
  const lista = async () => {
    const d = await api('/api/execucoes?tipo=instagram&por_pagina=100&arquivadas=0');
    ativo = d.itens.some((x) => x.em_andamento);
    put($('#lista-ig'), d.itens.length ? html`<div class="tabela-wrap"><table><thead><tr><th>Origem</th><th>Estado</th><th class="num">Obtidos</th><th class="num">Analisados</th>
      <th class="num">Identificados</th><th class="num">Para revisar</th><th class="num">Sem pesquisa de empresa</th><th>Atualizada</th></tr></thead><tbody>
      ${d.itens.map((x) => { const dd = x.resumo.dados || {}; const s = dd.situacoes || {}; return html`<tr class="clicavel" data-href="#/execucoes/${encodeURIComponent(x.id)}">
        <td class="nome"><a href="#/execucoes/${encodeURIComponent(x.id)}"><strong>${x.referencia}</strong></a><span class="sub">${x.nome}</span></td><td>${badge(EST_EXEC, x.estado)}</td>
        <td class="num">${num(x.total)}</td><td class="num">${num(x.processados)}</td><td class="num">${num(s.identificado || 0)}</td>
        <td class="num">${num(dd.pendentes_revisao ?? 0)}</td><td class="num">${num(dd.sem_empresa ?? 0)}</td>
        <td>${rel(x.atualizado)}<span class="sub">criada ${data(x.criado, false)}</span></td></tr>`; })}</tbody></table></div>`
      : vazio('Nenhuma análise ainda.', 'Informe um @ acima para começar.'));
  };
  await lista();
  return { atualizar: lista, intervalo: () => (ativo ? 5000 : 20000) };
});

// ======================================================================================= FILA DE PESQUISA
const EST_FILA = {
  pendente: ['atencao', 'Pendente', 'relogio'], pesquisando: ['info', 'Pesquisando', 'play'],
  concluido: ['bom', 'Concluído', 'check'], dispensado: ['', 'Dispensado', 'x'],
};
const COMANDO_CLAUDE = '/executar-tarefa';

rota(/^\/fila$/, 'Fila de pesquisa', 'fila', async (el, _, q0) => {
  await carregarSegmentos();
  const f = { estado: q0.estado || 'pendente', segmentos: q0.segmentos ? q0.segmentos.split(',') : [] };
  const sel = new Set();
  put(el, html`
    <div class="aviso info" style="margin-bottom:14px">${ic('terminal')}<div>
      <b>O que é esta fila.</b> A análise do Instagram descobre <i>quem</i> é parceiro em potencial (o @, o nome e o
      segmento). Os dados da empresa — CNPJ, telefone, endereço, site — vêm depois. Quem está esperando esse segundo
      passo fica aqui.<br>
      Você pode resolver de duas formas: pelo botão <b>Pesquisar pendentes</b> abaixo, ou no VS Code, escrevendo
      <code>${COMANDO_CLAUDE}</code> no Claude Code — ele lê esta mesma fila, pesquisa, revisa os casos incertos com
      fonte e grava tudo aqui. <button class="btn pequeno fantasma" data-acao="copiar_cmd">${ic('copiar')}Copiar comando</button>
    </div></div>
    <div class="tiles" id="tiles"></div>
    <div class="filtros" style="margin-top:16px">
      <span id="f-estado"></span><span id="f-segs"></span>
      <button class="btn fantasma" data-acao="limpar">Limpar filtros</button>
    </div>
    <div class="resultado-cab"><span class="total" id="total"></span><span id="sel-acoes"></span>
      <button class="btn primario pequeno" data-acao="pesquisar_fila">${ic('busca')}Pesquisar pendentes</button></div>
    <div id="itens"></div>`);

  const ESTADOS = [['pendente', 'Pendentes'], ['pesquisando', 'Sendo pesquisados'], ['concluido', 'Concluídos'],
    ['dispensado', 'Dispensados'], ['todos', 'Todos']];
  let dados = { itens: [], resumo: { por_estado: {}, por_segmento: {} } };

  const tiles = () => {
    const pe = dados.resumo.por_estado || {};
    put($('#tiles'), html`
      <a class="tile" href="#/fila?estado=pendente"><span class="rotulo">Pendentes</span><span class="valor">${num(pe.pendente || 0)}</span>
        <span class="detalhe">perfis identificados esperando os dados da empresa</span></a>
      <a class="tile" href="#/fila?estado=pesquisando"><span class="rotulo">Sendo pesquisados</span><span class="valor">${num(pe.pesquisando || 0)}</span>
        <span class="detalhe">numa pesquisa de empresas em andamento</span></a>
      <a class="tile" href="#/fila?estado=concluido"><span class="rotulo">Concluídos</span><span class="valor">${num(pe.concluido || 0)}</span>
        <span class="detalhe">já viraram empresa na base</span></a>`);
  };
  const filtros = () => {
    put($('#f-estado'), selecao('estado', 'Estado', ESTADOS, f.estado));
    const cont = dados.resumo.por_segmento || {};
    put($('#f-segs'), multi('segmentos', 'Segmento', SEGS.map((s) => ({ valor: s.codigo, rotulo: `${s.codigo} · ${s.nome}`, n: cont[s.codigo] })), f.segmentos));
  };
  const selAcoes = () => put($('#sel-acoes'), sel.size
    ? html`<span class="pequeno-txt"><b>${sel.size}</b> selecionado(s)</span>
        ${f.estado === 'dispensado' ? html`<button class="btn pequeno" data-acao="reabrir">${ic('atualizar')}Devolver à fila</button>`
          : html`<button class="btn pequeno" data-acao="dispensar">${ic('x')}Dispensar</button>`}
        <button class="btn pequeno fantasma" data-acao="limpar_sel">limpar</button>` : '');

  const carregar = async () => {
    trocarQuery({ estado: f.estado === 'pendente' ? '' : f.estado, segmentos: f.segmentos });
    dados = await api('/api/fila?' + qs({ estado: f.estado, segmentos: f.segmentos }));
    tiles(); filtros(); selAcoes();
    const d = dados.itens;
    $('#total').textContent = plural(d.length, 'perfil', 'perfis');
    put($('#itens'), d.length ? html`<div class="tabela-wrap"><table><thead><tr>
      <th><input type="checkbox" data-acao="sel_todos" aria-label="Selecionar todos"></th>
      <th>Perfil</th><th>Segmentos</th><th>Cidade</th><th>Estado</th><th>Análise de origem</th><th>Na fila desde</th></tr></thead><tbody>
      ${d.map((i) => html`<tr class="${sel.has(i.usuario) ? 'sel' : ''}">
        <td><input type="checkbox" data-acao="sel" data-u="${i.usuario}" ${sel.has(i.usuario) ? 'checked' : ''} aria-label="Selecionar @${i.usuario}"></td>
        <td class="nome"><a href="#/perfis/${encodeURIComponent(i.usuario)}"><strong>@${i.usuario}</strong></a>
          <a href="https://www.instagram.com/${i.usuario}/" target="_blank" rel="noopener" aria-label="Abrir @${i.usuario} no Instagram">${ic('externo')}</a>
          <span class="sub">${i.nome || ''}</span></td>
        <td>${segChips(i.segmentos)}</td><td>${i.cidade || html`<span class="mut">—</span>`}</td>
        <td>${badge(EST_FILA, i.estado)}${i.empresa_id ? html`<span class="sub"><a href="#/empresas/${i.empresa_id}">ver empresa</a></span>` : ''}${i.motivo ? html`<span class="sub">${i.motivo}</span>` : ''}</td>
        <td>${i.analise ? html`<a href="#/execucoes/${encodeURIComponent(i.execucao_id)}">${i.analise}</a>` : html`<span class="mut">—</span>`}</td>
        <td>${rel(i.criado)}</td></tr>`)}
      </tbody></table></div>`
      : vazio(f.estado === 'pendente' ? 'Nada pendente na fila.' : 'Nenhum perfil com esse filtro.',
              f.estado === 'pendente' ? 'Assim que uma análise do Instagram identificar perfis, eles aparecem aqui.' : ''));
  };

  app.acoes.copiar_cmd = () => copiar(COMANDO_CLAUDE);
  app.acoes.sel = (b) => { b.checked ? sel.add(b.dataset.u) : sel.delete(b.dataset.u); b.closest('tr').classList.toggle('sel', b.checked); selAcoes(); };
  app.acoes.sel_todos = (b) => { dados.itens.forEach((i) => (b.checked ? sel.add(i.usuario) : sel.delete(i.usuario))); carregar(); };
  app.acoes.limpar_sel = () => { sel.clear(); carregar(); };
  app.acoes.limpar = () => { f.estado = 'pendente'; f.segmentos = []; sel.clear(); carregar(); };
  app.acoes.dispensar = async () => {
    const r = await dialogo('Dispensar da fila', html`
      <p><b>${sel.size}</b> perfil(is) sairão da fila e não voltam sozinhos. Use para quem não é empresa ou não interessa.</p>
      <label class="campo">Motivo (opcional)<input type="text" id="fila-motivo" placeholder="ex.: perfil pessoal, não é empresa"></label>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Dispensar', classe: 'primario', valor: 'ok' }]);
    if (r !== 'ok') return;
    const motivo = $('#fila-motivo')?.value || '';
    if (await executar(() => post('/api/fila/dispensar', { usuarios: [...sel], motivo }), (d) => `${d.n} dispensado(s).`)) { sel.clear(); carregar(); }
  };
  app.acoes.reabrir = async () => {
    if (await executar(() => post('/api/fila/reabrir', { usuarios: [...sel] }), (d) => `${d.n} devolvido(s) à fila.`)) { sel.clear(); carregar(); }
  };
  app.acoes.pesquisar_fila = async (b) => {
    const pendentes = (dados.resumo.por_estado || {}).pendente || 0;
    if (!pendentes) return toast('Não há nada pendente na fila.', true);
    const r = await dialogo('Pesquisar os pendentes da fila', html`
      <p>Vai pesquisar os dados de empresa (CNPJ, telefone, endereço, site) dos perfis pendentes${f.segmentos.length ? html` dos segmentos <b>${f.segmentos.join(', ')}</b>` : ''}.</p>
      <label class="campo">Quantos no máximo<input type="number" id="fila-limite" min="1" max="1000" value="${Math.min(pendentes, 100)}"><span class="ajuda">Cerca de 5–15 s por empresa. Dá para parar e retomar.</span></label>
      <label class="marcar"><input type="checkbox" id="fila-incluir"> incluir quem já foi pesquisado há pouco</label>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Pesquisar', classe: 'primario', valor: 'ok' }]);
    if (r !== 'ok') return;
    b.disabled = true;
    const d = await executar(() => post('/api/fila/pesquisar', { limite: +$('#fila-limite').value || null, segmentos: f.segmentos.length ? f.segmentos : null, incluir_pesquisadas: $('#fila-incluir').checked }), 'Pesquisa iniciada.');
    b.disabled = false;
    if (d) location.hash = `#/execucoes/${encodeURIComponent(d.id)}`;
  };
  app.mudar = (t) => {
    const m = t.closest('details.multi');
    if (m?.dataset.multi === 'segmentos') { f.segmentos = $$('input:checked', m).map((i) => i.value); return carregar(); }
    if (t.dataset.sel === 'estado') { f.estado = t.value || 'pendente'; sel.clear(); return carregar(); }
  };
  await carregar();
  return { atualizar: carregar, intervalo: 10000 };
});

async function carregarSegmentos() { if (!SEGS.length) SEGS = await api('/api/segmentos'); return SEGS; }
function abasExec(abas) {
  return html`<div class="abas">${abas.map(([k, r], i) => html`<button aria-pressed="${i === 0}" data-acao="aba_exec" data-aba="${k}">${r}</button>`)}</div>`;
}

// ======================================================================================= EXECUÇÃO (detalhe)
rota(/^\/execucoes\/(.+)$/, 'Execução', 'execucoes', async (el, [id]) => {
  await carregarSegmentos();
  let x = await api(`/api/execucoes/${encodeURIComponent(id)}`);
  const [ico, tipoRot] = TIPO[x.tipo];
  $('#titulo').textContent = tipoRot;
  put(el, html`
    <a class="voltar" href="#/execucoes">${ic('voltar')}Execuções</a>
    <div class="cab-entidade"><div class="avatar">${ic(ico)}</div><div class="info"><h2>${x.referencia || x.nome}</h2>
      <div class="meta"><span id="badge-estado">${badge(EST_EXEC, x.estado)}</span><span class="mut">${tipoRot} · ${x.nome}</span>${x.arquivada ? html`<span class="chip">arquivada</span>` : ''}</div></div>
      <div class="acoes" id="acoes-exec"></div></div>
    <div id="painel-estado"></div>
    <div id="secoes"></div>`);

  const acoesExec = () => {
    const btns = [];
    if (x.em_andamento) btns.push(html`<button class="btn perigo" data-acao="parar">${ic('pausa')}Parar com segurança</button>`);
    else if (x.pode_retomar) btns.push(html`<button class="btn primario" data-acao="retomar">${ic('play')}${x.estado === 'criada' ? 'Iniciar' : x.estado === 'concluida_com_falhas' ? 'Refazer falhas' : 'Retomar'}</button>`);
    btns.push(html`<button class="btn" data-acao="arquivar">${ic('arquivo')}${x.arquivada ? 'Restaurar' : 'Arquivar'}</button>`);
    put($('#acoes-exec'), btns);
    put($('#badge-estado'), badge(EST_EXEC, x.estado));
  };
  app.acoes.parar = async () => { if (await executar(() => post(`/api/execucoes/${encodeURIComponent(id)}/parar`), 'Parada pedida: termina o item atual e para.')) atualizar(); };
  app.acoes.retomar = async () => {
    let dados = {};
    if (x.tipo === 'instagram') {
      const lim = x.resumo.estado?.config?.limite;
      const r = await dialogo('Retomar análise', html`<p>Continua de onde parou, sem repetir perfis.</p>
        <label class="campo">Novo limite de seguidores<input type="number" id="ret-limite" min="0" value="${lim || ''}" placeholder="sem limite"><span class="ajuda">Aumente para ampliar uma análise que chegou ao limite. 0 = sem limite.</span></label>
        <label class="marcar"><input type="checkbox" id="ret-noite" ${x.resumo.estado?.config?.noite ? 'checked' : ''}> Modo noite</label>`,
        [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Retomar', classe: 'primario', valor: 'ok' }]);
      if (r !== 'ok') return;
      dados = { limite: $('#ret-limite').value, noite: $('#ret-noite').checked };
    }
    if (await executar(() => post(`/api/execucoes/${encodeURIComponent(id)}/retomar`, dados), 'Execução retomada.')) atualizar();
  };
  app.acoes.arquivar = async () => {
    if (!x.arquivada) {
      const r = await dialogo('Arquivar execução', html`<p>A execução e os resultados dela saem da base de consulta e das listas. <b>Nenhum arquivo é apagado</b>; você pode restaurar depois em Execuções (mostrar arquivadas).</p>`,
        [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Arquivar', classe: 'primario', valor: 'ok' }]);
      if (r !== 'ok') return;
    }
    if (await executar(() => post(`/api/execucoes/${encodeURIComponent(id)}/arquivar`, { arquivada: !x.arquivada }), x.arquivada ? 'Execução restaurada.' : 'Execução arquivada.')) atualizar();
  };

  const painel = { instagram: painelInstagram, empresas: painelEmpresas, revisao_claude: painelClaude }[x.tipo];
  const secoes = { instagram: secoesInstagram, empresas: secoesEmpresas, revisao_claude: secoesClaude }[x.tipo];
  let estadoAnterior = x.estado;
  let ultimo = JSON.stringify(x);
  const atualizar = async () => {
    const novo = await api(`/api/execucoes/${encodeURIComponent(id)}`);
    const assinatura = JSON.stringify(novo);
    if (assinatura === ultimo) return;
    ultimo = assinatura;
    x = novo;
    acoesExec();
    const abertos = $$('#painel-estado details[open]').map((d) => d.dataset.k);
    put($('#painel-estado'), painel(x));
    abertos.forEach((k) => { const d = $(`#painel-estado details[data-k="${k}"]`); if (d) d.open = true; });
    if (x.estado !== estadoAnterior || x.em_andamento) app.pagina.secoesAtualizar?.(x);
    estadoAnterior = x.estado;
  };
  acoesExec();
  put($('#painel-estado'), painel(x));
  const s = await secoes($('#secoes'), x);
  return { atualizar, intervalo: () => (x.em_andamento ? 4000 : 15000), secoesAtualizar: s };
});

function conclusao(x) {
  const r = x.resumo.estado || {};
  const ICO = { bom: 'check', atencao: 'meia', serio: 'alerta', critico: 'alerta', info: 'info', '': 'info' };
  let texto = '', classe = '';
  if (x.tipo === 'instagram') {
    const cfg = r.config || {}, origem = r.origem || {};
    const mapa = {
      concluida: ['bom', `Varredura completa: a lista de seguidores acessível foi percorrida até o fim e todos os ${num(x.processados)} perfis obtidos foram analisados.`],
      concluida_parcial: r.lista_limitada ? ['atencao', 'Concluída com a lista limitada pelo Instagram: ele exibe só parte dos seguidores deste perfil. O restante não é acessível.']
        : ['atencao', `Concluída para os ${num(cfg.limite)} primeiros seguidores (limite definido)${origem.seguidores ? `; o perfil tem ${num(origem.seguidores)} seguidores públicos` : ''}. Para ampliar, retome com um limite maior.`],
      em_andamento: ['info', `Em andamento: ${r.fase === 'lista' ? 'lendo a lista de seguidores' : r.fase === 'perfis' ? 'analisando os perfis em ordem de prioridade' : r.fase === 'publicacoes' ? 'lendo publicações dos duvidosos' : 'iniciando'}.`],
      aguardando: ['atencao', `O Instagram pediu para esperar; o modo noite retoma sozinho${r.retoma_em ? ' por volta de ' + r.retoma_em.slice(11, 16) : ''}.`],
      parada: ['serio', 'O processo parou sem finalizar (o computador desligou, o programa foi fechado ou travou). Nada do que foi gravado se perde: use Retomar.'],
      interrompida: ['serio', 'Interrompida a pedido. Use Retomar para continuar de onde parou.'],
      pausada: ['atencao', 'Pausada com segurança por limite do Instagram ou falha de rede. Retome mais tarde.'],
      precisa_acao: ['critico', 'Parada: precisa de você (verificação de segurança, sessão expirada ou perfil inacessível). Veja os avisos abaixo.'],
      falhou: ['critico', 'Falhou por um erro inesperado. Os dados gravados foram preservados; veja o log.'],
      criada: ['', 'Criada, mas ainda não iniciada.'],
    };
    [classe, texto] = mapa[x.estado] || ['', x.mensagem];
  } else if (x.tipo === 'empresas') {
    const mapa = {
      concluida: ['bom', `Concluída: as ${num(x.total)} empresas da lista foram pesquisadas sem erro técnico.`],
      concluida_com_falhas: ['serio', `${plural(x.falhas, 'empresa teve', 'empresas tiveram')} erro técnico ou ficaram pendentes. Use "Refazer falhas": só elas são pesquisadas de novo.`],
      em_andamento: ['info', `Pesquisando: ${num(x.processados)} de ${num(x.total)} concluídas.`],
      parada: ['serio', 'O processo parou sem finalizar. As empresas já pesquisadas estão salvas; use Retomar para continuar as pendentes.'],
      interrompida: ['serio', 'Interrompida a pedido. As pendentes continuam com Retomar.'],
      criada: ['', 'Criada, aguardando início.'], falhou: ['critico', 'Falhou; veja o log.'],
    };
    [classe, texto] = mapa[x.estado] || ['', x.mensagem];
  } else {
    [classe, texto] = { concluida: ['bom', 'Revisão concluída pelo Claude Code.'], em_andamento: ['info', 'O Claude Code está revisando.'],
      falhou: ['critico', 'A revisão terminou com erro; veja o log.'], interrompida: ['serio', 'Revisão interrompida.'],
      parada: ['serio', 'O processo da revisão parou sem finalizar.'], criada: ['', 'Preparada.'] }[x.estado] || ['', x.mensagem];
  }
  return html`<div class="conclusao ${classe}">${ic(ICO[classe])}<div>${texto}</div></div>`;
}

function avisosEventos(r) {
  const ev = (r.eventos || []).filter((e) => e.tipo !== 'info' || /parte da lista/.test(e.mensagem)).slice(-6).reverse();
  return ev.map((e) => {
    const [c, rot] = e.tipo === 'intervencao' ? ['critico', 'Precisa de você'] : e.tipo === 'temporario' ? ['', 'Temporário'] : ['info', 'Informação'];
    return html`<div class="aviso ${c}">${ic(e.tipo === 'intervencao' ? 'alerta' : 'info')}<div><b>${rot}</b> · ${data(e.em)}: ${e.mensagem}</div></div>`;
  });
}

function painelInstagram(x) {
  const r = x.resumo.estado || {}, c = r.contadores || {}, pub = r.publicacoes || {}, cfg = r.config || {}, d = x.resumo.dados || {};
  const ordem = ['lista', 'perfis', 'publicacoes', 'fim'];
  const fase = x.completa || ['concluida', 'concluida_parcial'].includes(x.estado) ? 'fim' : r.fase || 'lista';
  const atual = Math.max(0, ordem.indexOf(fase));
  const fases = [
    ['1. Lista de seguidores', `${num(c.obtidos)} obtidos${r.fim_lista ? ' · até o fim' : cfg.limite && c.obtidos >= cfg.limite ? ' · limite' : ''}`],
    ['2. Perfis por prioridade', `${num(c.processados)} analisados · ${num(c.detalhes_lidos)} bios lidas`],
    ['3. Publicações dos duvidosos', cfg.publicacoes === 'nenhuma' ? 'desligado' : `${num(pub.feitos || 0)} de ${num(pub.alvos || 0)} · ${num(pub.mudaram || 0)} mudaram`],
    ['4. Resultado e revisão', fase === 'fim' ? 'pronto' : '—'],
  ];
  const s = d.situacoes || {};
  const est = r.estimativa;
  return html`<section class="card">
    ${conclusao(x)}
    <div class="fases">${fases.map(([t, sub], i) => { const cl = fase === 'fim' || i < atual ? 'ok' : i === atual ? 'agora' : ''; return html`<div class="fase ${cl}"><b>${cl === 'ok' ? ic('check') : cl === 'agora' ? ic('play') : ''}${t}</b><span>${sub}</span></div>`; })}</div>
    ${r.percentual != null && r.alvo ? html`${barra(r.percentual)}<div class="progresso-txt"><span>Lista de seguidores: ${r.percentual.toFixed(1)}% de ${num(r.alvo)} ${cfg.limite && r.alvo === cfg.limite ? '(limite)' : cfg.fonte === 'arquivo' ? '(lista)' : '(total público)'}</span>${est ? html`<span>Estimativa da fase atual: ~${duracao(est.restante_s)} (${est.ritmo_por_min}/min, medido nesta execução)</span>` : ''}</div>`
      : html`${x.em_andamento ? barra(null, true) : ''}<p class="mut pequeno-txt">Percentual da lista indisponível: o total acessível não é conhecido.</p>`}
    <div class="stats" style="margin-top:14px">
      ${[['Obtidos da lista', c.obtidos], ['Analisados', c.processados], ['Identificados', s.identificado || 0, 1], ['Para revisar', s.revisar || 0],
        ['Leituras com falha', (c.detalhes_falhos || 0) + (pub.falhas || 0)], ['Pendentes', x.pendentes]]
        .map(([k, v, dest]) => html`<div class="stat ${dest ? 'destaque' : ''}"><span>${k}</span><b>${num(v)}</b></div>`)}
    </div>
    ${avisosEventos(r)}
    <p class="mut pequeno-txt" style="margin:12px 0 0">Iniciada ${data(x.iniciado)} · ${duracao(r.duracao_s)} de execução${x.finalizado ? html` · finalizada ${data(x.finalizado)}` : ''} · última etapa: <b>${x.ultima_etapa || '—'}</b></p>
    <details class="secao detalhes-exec" data-k="mais"><summary>Mais detalhes</summary>
      <div class="stats">
        ${[['Seguidores públicos', cfg.fonte === 'arquivo' ? '—' : (r.origem || {}).seguidores], ['Bios lidas', c.detalhes_lidos], ['Publicações lidas', pub.lidas || 0], ['Privados', c.privados],
          ['Não lidos (triagem)', c.nao_lidos], ['Repetidos ignorados', c.duplicados]]
          .map(([k, v]) => html`<div class="stat"><span>${k}</span><b>${num(v)}</b></div>`)}
      </div>
      <p class="mut pequeno-txt" style="margin:10px 0 0">${x.mensagem ? x.mensagem + ' · ' : ''}Segmentos: ${(cfg.categorias || []).join(', ')} · limite: ${cfg.limite ? num(cfg.limite) : 'sem limite'} · leitura: ${cfg.detalhes} · publicações: ${cfg.publicacoes} · modo noite: ${cfg.noite ? 'sim' : 'não'}</p>
    </details>
  </section>`;
}

function painelEmpresas(x) {
  const r = x.resumo.estado || {}, d = x.resumo.dados || {}, st = d.status || {};
  const pct = x.total ? (100 * (x.processados + x.falhas)) / x.total : 0;
  const origens = Object.entries(d.origens || {}).filter(([k]) => k);
  const essenciais = { cnpj: 'CNPJ', razao_social: 'Razão social', endereco: 'Endereço', cep: 'CEP', telefones: 'Telefones', whatsapp: 'WhatsApp', emails: 'E-mails', site: 'Site', instagram: 'Instagram' };
  return html`<section class="card">
    ${conclusao(x)}
    ${barra(pct, x.em_andamento && !pct)}
    <div class="progresso-txt"><span>${num(x.processados + x.falhas)} de ${num(x.total)} processadas${x.falhas ? ` · ${x.falhas} com erro` : ''}</span><span>${r.duracao_s ? 'duração ' + duracao(r.duracao_s) : ''}</span></div>
    ${(r.em_andamento || []).length ? html`<div class="aviso info">${ic('play')}<div><b>Pesquisando agora:</b> ${r.em_andamento.join(' · ')}</div></div>` : ''}
    <div class="stats" style="margin-top:14px">
      ${[['Na lista', x.total], ['CNPJ confirmado', st.identificada || 0, 1], ['CNPJ provável', st.provavel || 0], ['Parciais (sem CNPJ)', st.parcial || 0],
        ['Não encontradas', st.nao_encontrada || 0], ['Erro técnico', st.erro || 0], ['Precisam de revisão', d.revisar_pendentes || 0], ['Revisadas', d.revisadas || 0], ['Empresas na base', x.empresas]]
        .map(([k, v, dest]) => html`<div class="stat ${dest ? 'destaque' : ''}"><span>${k}</span><b>${num(v)}</b></div>`)}
    </div>
    ${(r.erros || []).length ? html`<details class="secao" data-k="erros" style="margin-top:12px"><summary>${plural(r.erros.length, 'item com erro', 'itens com erro')}</summary>
      <ul class="pequeno-txt">${r.erros.map((e) => html`<li>Linha ${e.linha}: ${e.entrada} <span class="mut">${e.observacao}</span></li>`)}</ul></details>` : ''}
    ${d.registros ? html`<details class="secao detalhes-exec" data-k="mais"><summary>Campos encontrados e origem dos dados</summary><div class="grade g2">
      <div><h3 style="margin-bottom:8px">Campos encontrados</h3>${hbarras(Object.entries(essenciais).map(([k, rot]) => ({ rotulo: rot, n: (d.preenchidos || {})[k] || 0 })), d.registros)}</div>
      <div><h3 style="margin-bottom:8px">Origem dos dados</h3>${hbarras(origens.map(([k, n]) => ({ rotulo: ORIGEM[k] || k, n })))}
        <p class="mut pequeno-txt" style="margin-top:10px">Sites mais consultados: ${Object.keys(d.fontes || {}).slice(0, 8).join(' · ') || '—'}</p></div></div></details>` : ''}
    <p class="mut pequeno-txt" style="margin:12px 0 0">${[x.mensagem, 'iniciada ' + data(x.iniciado), x.finalizado ? 'finalizada ' + data(x.finalizado) : '', x.ultima_etapa].filter(Boolean).join(' · ')}</p>
  </section>`;
}

function painelClaude(x) {
  const r = x.resumo.estado || {};
  return html`<section class="card">${conclusao(x)}
    <dl class="dl"><dt>Revisando</dt><dd>${x.origem_execucao ? html`<a href="#/execucoes/${encodeURIComponent(x.origem_execucao)}">${x.origem_execucao}</a>` : '—'}</dd>
    <dt>Ações executadas</dt><dd>${num(x.processados)}</dd><dt>Última ação</dt><dd><code>${x.ultima_etapa || '—'}</code></dd>
    <dt>Duração</dt><dd>${duracao(r.duracao_s)}</dd>${r.turnos ? html`<dt>Turnos</dt><dd>${r.turnos}</dd>` : ''}
    <dt>Mensagem</dt><dd>${x.mensagem || '—'}</dd></dl>
    ${r.resultado ? html`<h3 style="margin:14px 0 8px">Resumo do Claude</h3><pre class="resultado">${r.resultado}</pre>` : ''}</section>`;
}

function arquivosELog(x) {
  return html`<section class="card"><div class="card-cab"><h2>Arquivos e log</h2><span class="sub mono">${x.pasta}</span></div>
    <div class="acoes">${x.arquivos.length ? x.arquivos.map((a) => html`<a class="btn pequeno" href="/api/execucoes/${encodeURIComponent(x.id)}/arquivo/${a.arquivo}" target="_blank" rel="noopener">${ic('baixar')}${a.rotulo}</a>`) : html`<span class="mut">Nenhum arquivo gerado ainda.</span>`}
      <button class="btn pequeno fantasma" data-acao="ver_log">${ic('historico')}Ver log</button></div><div id="log"></div></section>`;
}
function acaoLog(x) {
  app.acoes.ver_log = async () => {
    const d = await executar(() => api(`/api/execucoes/${encodeURIComponent(x.id)}/log`));
    if (d) put($('#log'), html`<div class="log" style="margin-top:12px">${d.linhas.length ? d.linhas.join('\n') : 'Log vazio.'}</div>`);
  };
}

function painelRevisaoClaude(x, pendentes, tipo) {
  const filhas = (x.filhas || []).filter((f) => f.tipo === 'revisao_claude');
  const mid = x.id.replace(/[^a-z0-9]/gi, '');
  const maxAtual = document.getElementById('claude-max-' + mid)?.value || (tipo === 'empresas' ? 15 : 40);
  return html`<section class="card"><div class="card-cab"><h2>${ic('claude')} Revisão pelo Claude</h2><span class="sub">${plural(pendentes || 0, 'item incerto pendente', 'itens incertos pendentes')}</span></div>
    <p class="pequeno-txt">${tipo === 'empresas' ? 'Investiga os casos incertos na web e registra cada confirmação com a fonte.' : 'Decide os perfis duvidosos com base no pacote de revisão e registra cada decisão com nota.'}</p>
    <div class="acoes"><label class="campo" style="flex-direction:row;align-items:center;gap:8px">Até<input type="number" id="claude-max-${mid}" min="1" max="100" value="${maxAtual}" style="width:80px">itens</label>
      <button class="btn" data-acao="copiar_pedido" data-id="${x.id}">${ic('copiar')}Copiar pedido para o chat</button>
      <button class="btn primario" data-acao="claude_fundo" data-id="${x.id}">${ic('claude')}Revisar em segundo plano</button></div>
    ${filhas.length ? html`<div class="lista-exec" style="margin-top:10px">${filhas.map(itemExec)}</div>` : ''}</section>`;
}

async function secoesInstagram(el, x) {
  const dd = x.resumo.dados || {};
  const f = { q: '', segmento: [], situacao: ['identificado'], confianca: [], empresa: '', pagina: 1 };
  const pe = { escopo: 'identificados', segmentos: [], incluir: false };
  const cats = (x.resumo.estado?.config?.categorias || []);
  put(el, html`
    ${abasExec([['perfis', 'Perfis'], ['empresas', 'Pesquisar empresas'], ['claude', 'Revisão pelo Claude'], ['arquivos', 'Arquivos e log']])}
    <div data-painel="perfis">
      <section class="card"><div class="card-cab"><h2>Perfis desta análise</h2></div>
        <div class="filtros"><input type="search" data-f="q" placeholder="Buscar @, nome ou bio…" aria-label="Buscar perfis">
          <span id="f-multis"></span>
          ${selecao('empresa', 'Empresa: todas', [['com', 'com empresa vinculada'], ['sem', 'sem empresa'], ['sugerido', 'com vínculo sugerido']], '')}</div>
        <div id="itens"></div></section>
    </div>
    <div data-painel="empresas" hidden>
      <section class="card"><div class="card-cab"><h2>${ic('predio')} Pesquisar as empresas destes perfis</h2></div>
        <p class="pequeno-txt mut">Cria uma pesquisa com os perfis desta análise. Perfis já pesquisados recentemente são pulados.</p>
        <div class="linha-form">
          <label class="campo">Quais perfis<select data-pe="escopo"><option value="identificados">identificados</option><option value="todos">identificados e para revisar</option></select></label>
          <div class="campo"><span>Segmentos (nenhum marcado = todos)</span><span>${multi('pe_segmentos', 'Segmentos', cats.map((c) => ({ valor: c, rotulo: `${c} · ${segNome(c)}`, n: (dd.por_categoria || {})[c] })), [])}</span></div>
          <label class="marcar"><input type="checkbox" data-pe="incluir"> incluir já pesquisadas</label>
        </div>
        <div id="previa" style="margin-top:12px"></div></section>
      <section class="card" id="filhas-wrap"></section>
    </div>
    <div data-painel="claude" hidden><div id="claude-ig">${painelRevisaoClaude(x, dd.pendentes_revisao, 'instagram')}</div></div>
    <div data-painel="arquivos" hidden>${arquivosELog(x)}</div>`);
  acaoLog(x);
  const multisPerfis = () => put($('#f-multis'), html`${multi('segmento', 'Segmento', cats.map((c) => ({ valor: c, rotulo: `${c} · ${segNome(c)}` })), f.segmento)}
    ${multi('situacao', 'Situação', [['identificado', 'Identificado'], ['revisar', 'Revisar'], ['sem_correspondencia', 'Sem correspondência'], ['descartado', 'Descartado']].map(([v, r]) => ({ valor: v, rotulo: r })), f.situacao)}
    ${multi('confianca', 'Confiança', [['alta', 'alta'], ['media', 'média'], ['baixa', 'baixa']].map(([v, r]) => ({ valor: v, rotulo: r })), f.confianca)}`);
  multisPerfis();
  const filhas = (x2) => {
    const lotes = (x2.filhas || []).filter((y) => y.tipo === 'empresas');
    const w = $('#filhas-wrap');
    w.hidden = !lotes.length;
    put(w, html`<div class="card-cab"><h2>Pesquisas de empresas criadas a partir desta análise</h2></div><div class="lista-exec">${lotes.map(itemExec)}</div>`);
  };
  filhas(x);
  const previa = async () => {
    put($('#previa'), html`<div class="mut pequeno-txt">Calculando…</div>`);
    try {
      const d = await api(`/api/execucoes/${encodeURIComponent(x.id)}/candidatos?${qs({ escopo: pe.escopo, segmentos: pe.segmentos, incluir: pe.incluir ? 1 : '' })}`);
      put($('#previa'), html`<p><b>${plural(d.selecionados.length, 'perfil será pesquisado', 'perfis serão pesquisados')}</b>${d.pulados.length ? html` · <span class="mut">${plural(d.pulados.length, 'já pesquisado', 'já pesquisados')} nos últimos ${d.dias} dias (pulados)</span>` : ''}</p>
        ${d.selecionados.length ? html`<details class="secao"><summary class="pequeno-txt">Ver a lista que será enviada</summary><pre class="resultado mono" style="max-height:220px;overflow:auto">${d.selecionados.map((s) => s.linha).join('\n')}</pre></details>` : ''}
        ${d.pulados.length ? html`<details class="secao"><summary class="pequeno-txt">Ver os pulados</summary><ul class="pequeno-txt">${d.pulados.map((p) => html`<li>@${p.usuario} — ${p.motivo} · <a href="#/empresas/${p.empresa_id}">ver empresa</a></li>`)}</ul></details>` : ''}
        <div class="acoes" style="margin-top:10px"><button class="btn primario" data-acao="pesquisar_emp" ${d.selecionados.length ? '' : 'disabled'}>${ic('busca')}Pesquisar ${plural(d.selecionados.length, 'empresa', 'empresas')}</button>
          <span class="mut pequeno-txt">Cerca de 5–15 s por empresa.</span></div>`);
    } catch (e) { put($('#previa'), html`<div class="aviso critico">${e.message}</div>`); }
  };
  app.acoes.pesquisar_emp = async (b) => {
    b.disabled = true;
    const r = await executar(() => post(`/api/execucoes/${encodeURIComponent(x.id)}/pesquisar-empresas`, { escopo: pe.escopo, segmentos: pe.segmentos, incluir_pesquisadas: pe.incluir }), 'Pesquisa de empresas iniciada.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`; else b.disabled = false;
  };
  const carregar = async () => {
    const d = await api(`/api/execucoes/${encodeURIComponent(x.id)}/perfis?${qs({ ...f })}`);
    put($('#itens'), tabelaPerfis(d, 'pag_perfis'));
  };
  app.acoes.pag_perfis = (b) => { f.pagina = +b.dataset.pagina; carregar(); };
  let espera;
  app.mudar = (t) => {
    if (t.dataset.pe) { pe[t.dataset.pe] = t.type === 'checkbox' ? t.checked : t.value; return previa(); }
    const m = t.closest('details.multi');
    if (m?.dataset.multi === 'pe_segmentos') { pe.segmentos = $$('input:checked', m).map((i) => i.value); resumoMulti(m); return previa(); }
    if (m) { f[m.dataset.multi] = $$('input:checked', m).map((i) => i.value); resumoMulti(m); f.pagina = 1; return carregar(); }
    if (t.dataset.sel) { f[t.dataset.sel] = t.value; f.pagina = 1; return carregar(); }
    if (t.dataset.f === 'q') { clearTimeout(espera); espera = depois(() => { f.q = t.value; f.pagina = 1; carregar(); }, 300); }
  };
  await Promise.all([previa(), carregar()]);
  return async (x2) => { filhas(x2); put($('#claude-ig'), painelRevisaoClaude(x2, (x2.resumo.dados || {}).pendentes_revisao, 'instagram')); await carregar(); };
}

function resumoMulti(det, rotuloVazio) {
  const n = $$('input:checked', det).length;
  const s = $('summary', det);
  const base = s.dataset.rotulo || (s.dataset.rotulo = s.firstChild.textContent.trim());
  put(s, html`${n ? base : rotuloVazio || base}${n ? html` <span class="qt">${n}</span>` : ''}`);
}

function tabelaPerfis(d, acaoPag) {
  if (!d.itens.length) return vazio('Nenhum perfil com esses filtros.');
  return html`<div class="resultado-cab"><span class="total">${plural(d.total, 'perfil', 'perfis')}</span></div>
    <div class="tabela-wrap"><table><thead><tr><th>Perfil</th><th>Segmentos</th><th>Situação</th><th class="num">Seguidores</th><th>Cidade</th><th>Empresa</th></tr></thead><tbody>
    ${d.itens.map((p) => html`<tr class="clicavel" data-href="#/perfis/${encodeURIComponent(p.usuario)}">
      <td class="nome"><a href="#/perfis/${encodeURIComponent(p.usuario)}"><strong>@${p.usuario}</strong></a> <a href="https://www.instagram.com/${p.usuario}/" target="_blank" rel="noopener" title="Abrir no Instagram" aria-label="Abrir @${p.usuario} no Instagram">${ic('externo')}</a>
        <span class="sub">${p.nome || ''}${p.categoria_ig ? ' · ' + p.categoria_ig : ''}</span></td>
      <td>${segChips(p.segmentos)}</td><td>${badge(SIT_PERFIL, p.situacao)} ${conf(p.confianca)}</td>
      <td class="num">${num(p.seguidores)}</td><td>${p.cidade || '—'}</td>
      <td>${p.empresa_id ? html`<a href="#/empresas/${p.empresa_id}">${p.empresa_nome || 'empresa ' + p.empresa_id}</a>` : p.sugeridos ? html`<span class="badge nc">${ic('meia')}sugerido</span>` : html`<span class="mut">—</span>`}</td></tr>`)}
    </tbody></table></div>${paginacao(d, acaoPag)}`;
}

async function secoesEmpresas(el, x) {
  const f = { status: '', revisar: '' };
  put(el, html`
    ${abasExec([['empresas', 'Empresas'], ['claude', 'Revisão pelo Claude'], ['arquivos', 'Arquivos e log']])}
    <div data-painel="empresas">
      ${x.pai ? html`<section class="card" style="margin-bottom:14px"><div class="card-cab"><h2>Origem</h2></div>${itemExec(x.pai)}</section>` : ''}
      <section class="card"><div class="card-cab"><h2>Empresas pesquisadas</h2>
        ${selecao('status', 'Status: todos', Object.entries(ST_EMP).map(([k, v]) => [k, v[1]]), '')}
        <label class="marcar pequeno-txt"><input type="checkbox" data-f="revisar"> só as que precisam de revisão</label>
        <a class="btn pequeno" href="#/empresas?execucao=${encodeURIComponent(x.id)}">${ic('filtro')}Abrir na base de empresas</a></div>
        <div id="itens"></div></section>
    </div>
    <div data-painel="claude" hidden><div id="claude-emp">${painelRevisaoClaude(x, (x.resumo.dados || {}).revisar_pendentes, 'empresas')}</div></div>
    <div data-painel="arquivos" hidden>${arquivosELog(x)}</div>`);
  acaoLog(x);
  const carregar = async () => {
    const d = await api(`/api/execucoes/${encodeURIComponent(x.id)}/pesquisas?${qs(f)}`);
    put($('#itens'), d.itens.length ? html`<div class="tabela-wrap"><table><thead><tr><th class="num">#</th><th>Entrada</th><th>Encontrado</th><th>Status</th><th>CNPJ</th><th>Cidade</th><th>Revisão</th></tr></thead><tbody>
      ${d.itens.map((p) => html`<tr class="${p.empresa_id ? 'clicavel' : ''}" ${p.empresa_id ? raw(`data-href="#/empresas/${p.empresa_id}"`) : ''}>
        <td class="num">${p.linha}</td><td>${p.entrada}</td><td class="nome">${p.empresa_id ? html`<a href="#/empresas/${p.empresa_id}"><strong>${p.empresa_nome || p.nome || '—'}</strong></a>` : html`<strong>${p.nome || '—'}</strong>`}${p.nao_confirmados.length ? html`<span class="sub">${plural(p.nao_confirmados.length, 'campo não confirmado', 'campos não confirmados')}</span>` : ''}</td>
        <td>${badge(ST_EMP, p.status)} ${conf(p.confianca)}</td><td class="mono">${p.cnpj ? html`${fmtCnpj(p.cnpj)}${p.cnpj_confirmado ? '' : html` <span class="nc-valor">não conf.</span>`}` : '—'}</td>
        <td>${[p.cidade, p.uf].filter(Boolean).join('/') || '—'}</td>
        <td>${p.revisado_em ? html`<span class="badge bom">${ic('check')}revisada</span>` : p.precisa_revisao ? html`<span class="badge atencao">${ic('meia')}revisar</span>` : html`<span class="mut">—</span>`}</td></tr>`)}
      </tbody></table></div>` : vazio(x.em_andamento ? 'As empresas aparecem aqui conforme forem pesquisadas.' : 'Nenhum resultado com esses filtros.'));
  };
  app.mudar = (t) => {
    if (t.dataset.sel === 'status') { f.status = t.value; carregar(); }
    if (t.dataset.f === 'revisar') { f.revisar = t.checked ? '1' : ''; carregar(); }
  };
  await carregar();
  return async (x2) => { put($('#claude-emp'), painelRevisaoClaude(x2, (x2.resumo.dados || {}).revisar_pendentes, 'empresas')); await carregar(); };
}

async function secoesClaude(el, x) {
  put(el, arquivosELog(x));
  acaoLog(x);
  app.acoes.ver_log();
  return async () => app.acoes.ver_log();
}
const fmtCnpj = (c) => { const d = String(c).replace(/[^0-9A-Za-z]/g, ''); return d.length === 14 ? `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}` : c; };

// ======================================================================================= EMPRESAS (base)
const PENDENCIAS = [['revisar', 'Precisa de revisão'], ['nao_confirmados', 'Com dados não confirmados'], ['sem_cnpj', 'Sem CNPJ confirmado'], ['divergencia', 'Com divergências'],
  ['duplicidade', 'Possível duplicidade'], ['desatualizada', 'Desatualizada'], ['erro', 'Erro técnico'], ['revisada', 'Já revisada']];
const ORDENS = [['nome', 'Nome (A–Z)'], ['-ultima_pesquisa', 'Pesquisa mais recente'], ['ultima_pesquisa', 'Pesquisa mais antiga'], ['-completude', 'Mais completas'], ['completude', 'Menos completas'], ['cidade', 'UF e cidade'], ['status', 'Status']];
const MULTIS_EMP = ['uf', 'cidade', 'segmento', 'status', 'pendencia', 'confianca'];

rota(/^\/empresas$/, 'Base de empresas', 'empresas', async (el, _, q0) => {
  await carregarSegmentos();
  const op = await api('/api/empresas/opcoes');
  const f = { ...q0 };
  delete f.nova;
  const lista = (k) => (f[k] ? String(f[k]).split(',').filter(Boolean) : []);
  const sel = new Set();
  const rotulos = {
    status: Object.fromEntries(Object.entries(ST_EMP).map(([k, v]) => [k, v[1]])), pendencia: Object.fromEntries(PENDENCIAS),
    confianca: { alta: 'confiança alta', media: 'confiança média', baixa: 'confiança baixa' },
    segmento: Object.fromEntries(SEGS.map((s) => [s.codigo, `${s.codigo} · ${s.nome}`])),
    instagram: { com: 'com Instagram', sem: 'sem Instagram', vinculado: 'perfil confirmado', sugerido: 'vínculo sugerido' },
    contato: { com: 'com contato', sem: 'sem contato', whatsapp: 'com WhatsApp' }, origem: { instagram: 'veio de análise do Instagram', lista: 'veio de lista' },
    origem_segmento: { perfil: 'segmento do perfil', inferido: 'segmento inferido', sem: 'sem segmento' },
    execucao: Object.fromEntries(op.execucoes.map((x) => [x.valor, x.nome])),
  };
  const painelAberto = Object.keys(f).some((k) => f[k] && !['q', 'pagina', 'ordenar', 'por_pagina'].includes(k));
  put(el, html`
    <div class="filtros">
      <input type="search" data-f="q" value="${f.q || ''}" placeholder="Buscar por nome, @, CNPJ, site, cidade…" aria-label="Buscar empresas">
      <button class="btn filtros-btn" data-acao="filtros_painel" aria-expanded="${String(painelAberto)}" aria-controls="filtros-painel">${ic('filtro')}Filtros<span id="n-filtros"></span></button>
      ${selecao('ordenar', 'Ordenar', ORDENS, f.ordenar || 'nome')}
      <button class="btn fantasma" data-acao="limpar">Limpar filtros</button>
    </div>
    <div class="filtros-painel" id="filtros-painel" ${painelAberto ? '' : 'hidden'}>
      <span id="multis"></span>
      ${selecao('instagram', 'Instagram', Object.entries(rotulos.instagram), f.instagram)}
      ${selecao('contato', 'Contato', Object.entries(rotulos.contato), f.contato)}
      ${selecao('origem', 'Origem', Object.entries(rotulos.origem), f.origem)}
    </div>
    <div class="filtros-ativos" id="ativos"></div>
    <div class="resultado-cab"><span class="total" id="total"></span><span id="sel-acoes"></span>
      <a class="btn pequeno" id="exp-csv" href="#">${ic('baixar')}CSV</a><a class="btn pequeno" id="exp-xlsx" href="#">${ic('baixar')}XLSX</a>
      <button class="btn primario pequeno" data-acao="nova">${ic('mais')}Nova pesquisa</button></div>
    <div id="perfis-q"></div>
    <div id="itens"></div>`);

  const multiCidade = () => { const ufs = lista('uf'); return multi('cidade', 'Cidade', op.cidades.filter((c) => !ufs.length || ufs.includes(c.uf)).map((c) => ({ valor: c.valor, rotulo: `${c.valor}/${c.uf}`, n: c.n })), lista('cidade')); };
  const multis = () => {
    put($('#multis'), html`
      ${multi('uf', 'UF', op.ufs.map((o) => ({ valor: o.valor, n: o.n })), lista('uf'))}
      <span id="m-cidade">${multiCidade()}</span>
      ${multi('segmento', 'Segmento', [{ grupo: 'Perfil identificado · inferido' }, ...op.segmentos.map((s) => ({ valor: s.codigo, rotulo: `${s.codigo} · ${s.nome}`, n: s.perfil + s.inferido }))], lista('segmento'))}
      ${multi('status', 'Status', op.status.map((o) => ({ valor: o.valor, rotulo: rotulos.status[o.valor] || o.valor, n: o.n })), lista('status'))}
      ${multi('confianca', 'Confiança', Object.entries(rotulos.confianca).map(([v, r]) => ({ valor: v, rotulo: r })), lista('confianca'))}
      ${multi('pendencia', 'Pendências', PENDENCIAS.map(([v, r]) => ({ valor: v, rotulo: r })), lista('pendencia'))}
      ${selecao('origem_segmento', 'Segmento: qualquer origem', [['perfil', 'só do perfil (confirmado)'], ['inferido', 'só inferido'], ['sem', 'sem segmento']], f.origem_segmento)}`);
  };
  const ativos = () => {
    const chips = [];
    for (const [k, v] of Object.entries(f)) {
      if (!v || ['pagina', 'ordenar', 'por_pagina'].includes(k)) continue;
      for (const item of k === 'q' ? [v] : String(v).split(',')) {
        const r = k === 'q' ? `“${item}”` : k === 'cidade' || k === 'uf' ? item : (rotulos[k] || {})[item] || item;
        chips.push(html`<button class="filtro-ativo" data-acao="tirar" data-k="${k}" data-v="${item}" aria-label="Remover filtro ${r}">${r}${ic('x')}</button>`);
      }
    }
    put($('#ativos'), chips);
    const nAtivos = chips.length - (f.q ? 1 : 0);
    put($('#n-filtros'), nAtivos > 0 ? html` <span class="qt">${nAtivos}</span>` : '');
  };
  const exportar = () => { const s = qs({ ...f, pagina: '' }); $('#exp-csv').href = '/api/empresas/exportar.csv?' + s; $('#exp-xlsx').href = '/api/empresas/exportar.xlsx?' + s; };
  const selAcoes = () => put($('#sel-acoes'), sel.size ? html`<span class="pequeno-txt"><b>${sel.size}</b> selecionada(s)</span> <button class="btn pequeno" data-acao="atualizar_sel">${ic('atualizar')}Pesquisar novamente</button> <button class="btn pequeno fantasma" data-acao="limpar_sel">limpar seleção</button>` : '');
  const carregar = async () => {
    trocarQuery(f);
    ativos(); exportar();
    const d = await api('/api/empresas?' + qs(f));
    $('#total').textContent = plural(d.total, 'empresa', 'empresas');
    put($('#itens'), d.itens.length ? html`<div class="tabela-wrap"><table><thead><tr>
      <th><input type="checkbox" data-acao="sel_todas" aria-label="Selecionar todas desta página"></th><th>Empresa</th><th>Segmentos</th><th>Local</th><th>Status</th><th>Contato</th><th>Instagram</th><th>Completude</th><th>Última pesquisa</th></tr></thead><tbody>
      ${d.itens.map((e) => html`<tr class="clicavel ${sel.has(e.id) ? 'sel' : ''}" data-href="#/empresas/${e.id}">
        <td><input type="checkbox" data-acao="sel" data-id="${e.id}" ${sel.has(e.id) ? 'checked' : ''} aria-label="Selecionar ${e.nome}"></td>
        <td class="nome"><a href="#/empresas/${e.id}"><strong>${e.nome || '(sem nome)'}</strong></a><span class="sub">${e.cnpj ? html`<span class="mono">${e.cnpj}</span>${e.cnpj_confirmado ? '' : html` <span class="nc-valor">não conf.</span>`}` : 'sem CNPJ'}</span></td>
        <td>${segChips(e.segmentos_perfil, e.segmentos_inferidos)}</td>
        <td>${[e.cidade, e.uf].filter(Boolean).join('/') || html`<span class="mut">—</span>`}</td>
        <td>${badge(ST_EMP, e.status)}${e.duplicidades ? html`<span class="sub"><span class="badge serio">${ic('alerta')}duplicidade?</span></span>` : ''}</td>
        <td><span class="ico-contatos"><span class="${e.telefone ? 'tem' : ''}" title="${e.telefone || 'sem telefone'}">${ic('tel')}</span><span class="${e.whatsapp ? 'tem' : ''}" title="${e.whatsapp || 'sem WhatsApp'}">${ic('whats')}</span><span class="${e.email ? 'tem' : ''}" title="${e.email || 'sem e-mail'}">${ic('email')}</span><span class="${e.site ? 'tem' : ''}" title="${e.site || 'sem site'}">${ic('site')}</span></span></td>
        <td>${e.instagram ? html`<span class="pequeno-txt">@${handle(e.instagram)}</span>` : html`<span class="mut">—</span>`}${e.perfis_confirmados ? html`<span class="sub">${ic('check')} perfil confirmado</span>` : e.perfis_sugeridos ? html`<span class="sub">vínculo sugerido</span>` : ''}</td>
        <td><span class="medidor" title="${e.completude} de 9 dados principais${e.n_nao_confirmados ? ` · ${e.n_nao_confirmados} não confirmados` : ''}"><i><b style="width:${(100 * e.completude) / 9}%"></b></i>${e.completude}/9</span>${e.n_nao_confirmados ? html`<span class="sub">${e.n_nao_confirmados} não conf.</span>` : ''}</td>
        <td>${data(e.ultima_pesquisa, false)}<span class="sub">${plural(e.n_pesquisas, 'pesquisa', 'pesquisas')}</span></td></tr>`)}
      </tbody></table></div>${paginacao(d)}` : vazio('Nenhuma empresa com esses filtros.', html`<br><button class="btn" data-acao="limpar" style="margin-top:10px">Limpar filtros</button>`));
    if (f.q) {
      const p = await semErro(api('/api/perfis?' + qs({ q: f.q, por_pagina: 1 })), null);
      put($('#perfis-q'), p && p.total ? html`<div class="aviso info">${ic('pessoas')}<div>${plural(p.total, 'perfil do Instagram também corresponde', 'perfis do Instagram também correspondem')} a “${f.q}”. <a href="#/perfis?q=${encodeURIComponent(f.q)}">Ver perfis</a></div></div>` : '');
    } else put($('#perfis-q'), '');
  };
  let espera;
  app.mudar = (t) => {
    const m = t.closest('details.multi');
    if (m) { const v = $$('input:checked', m).map((i) => i.value).join(','); if (v) f[m.dataset.multi] = v; else delete f[m.dataset.multi]; resumoMulti(m); if (m.dataset.multi === 'uf') put($('#m-cidade'), multiCidade()); f.pagina = 1; return carregar(); }
    if (t.dataset.sel) { if (t.value) f[t.dataset.sel] = t.value; else delete f[t.dataset.sel]; f.pagina = 1; return carregar(); }
    if (t.dataset.f === 'q') { clearTimeout(espera); espera = depois(() => { if (t.value.trim()) f.q = t.value.trim(); else delete f.q; f.pagina = 1; carregar(); }, 300); }
  };
  app.acoes.pagina = (b) => { f.pagina = b.dataset.pagina; carregar(); window.scrollTo(0, 0); };
  app.acoes.limpar = () => { for (const k of Object.keys(f)) if (k !== 'ordenar') delete f[k]; $('[data-f=q]', el).value = ''; multis(); $$('select[data-sel]', el).forEach((s) => { if (s.dataset.sel !== 'ordenar') s.value = ''; }); carregar(); };
  app.acoes.tirar = (b) => {
    const k = b.dataset.k;
    const resto = k === 'q' ? [] : String(f[k]).split(',').filter((v) => v !== b.dataset.v);
    if (resto.length) f[k] = resto.join(','); else delete f[k];
    if (k === 'q') $('[data-f=q]', el).value = '';
    const s = $(`select[data-sel="${k}"]`, el); if (s) s.value = f[k] || '';
    multis(); carregar();
  };
  app.acoes.sel = (c) => { const id = +c.dataset.id; if (c.checked) sel.add(id); else sel.delete(id); c.closest('tr').classList.toggle('sel', c.checked); selAcoes(); };
  app.acoes.sel_todas = (c) => { $$('input[data-acao=sel]', el).forEach((x) => { x.checked = c.checked; const id = +x.dataset.id; if (c.checked) sel.add(id); else sel.delete(id); x.closest('tr').classList.toggle('sel', c.checked); }); selAcoes(); };
  app.acoes.limpar_sel = () => { sel.clear(); $$('input[data-acao=sel]', el).forEach((x) => { x.checked = false; x.closest('tr').classList.remove('sel'); }); selAcoes(); };
  app.acoes.atualizar_sel = async () => {
    const ok = await dialogo('Pesquisar novamente', html`<p>Cria uma nova pesquisa para <b>${plural(sel.size, 'empresa selecionada', 'empresas selecionadas')}</b>, com a mesma entrada usada antes. As pesquisas anteriores ficam no histórico de cada empresa.</p>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Pesquisar', classe: 'primario', valor: 'ok' }]);
    if (ok !== 'ok') return;
    const r = await executar(() => post('/api/empresas/atualizar', { ids: [...sel] }), 'Nova pesquisa iniciada.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  };
  app.acoes.nova = () => novaPesquisa();
  multis();
  await carregar();
  if (q0.nova) novaPesquisa();
});

async function novaPesquisa() {
  const ok = await dialogo('Nova pesquisa de empresas', html`
    <p class="pequeno-txt">Uma empresa por linha: <code>@instagram</code>, site, CNPJ ou nome. Pistas extras com <code>|</code>, por exemplo <code>Padaria Real | Bauru/SP</code>.</p>
    <label class="campo">Lista<textarea id="np-lista" placeholder="@perfil&#10;www.empresa.com.br&#10;12.345.678/0001-90&#10;Nome da Empresa | Cidade/UF"></textarea></label>
    <label class="campo">Nome da pesquisa (opcional)<input type="text" id="np-nome" placeholder="ex.: funerárias-curitiba"></label>
    `,
  [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Pesquisar', classe: 'primario', valor: 'ok' }]);
  if (ok !== 'ok') return;
  const lista = $('#np-lista').value, nome = $('#np-nome').value;
  const r = await executar(() => post('/api/empresas/pesquisar', { lista, nome }), 'Pesquisa iniciada.');
  if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
}

// ======================================================================================= EMPRESA (detalhe)
rota(/^\/empresas\/(\d+)$/, 'Empresa', 'empresas', async (el, [id]) => {
  await carregarSegmentos();
  const render = async () => {
    const d = await api(`/api/empresas/${id}`);
    const e = d.empresa, a = d.atual;
    $('#titulo').textContent = e.nome || 'Empresa';
    const v = (campo) => (d.campos.find((c) => c.campo === campo) || { valores: [] }).valores[0]?.valor;
    const links = [[v('site'), 'site', 'Site'], [e.instagram, 'instagram', 'Instagram'], [v('google_maps'), 'mapa', 'Mapa']].map(([u, i, r]) => [urlSegura(u), i, r]).filter(([u]) => u);
    const outrasMaisNovas = d.historico.filter((h) => !h.atual && (h.revisado_em || h.data) > (a?.revisado_em || a?.data || ''));
    put(el, html`
      <a class="voltar" href="#/empresas" data-acao="voltar">${ic('voltar')}Voltar</a>
      ${d.duplicidades.map((x) => html`<div class="aviso">${ic('alerta')}<div><b>Possível duplicidade</b> com <a href="#/empresas/${x.outra.id}">${x.outra.nome}</a> (${[x.outra.cidade, x.outra.uf].filter(Boolean).join('/') || 'local não informado'}) — ${x.motivo}.
        <span class="acoes" style="margin-top:6px"><button class="btn pequeno" data-acao="dup" data-a="${x.a}" data-b="${x.b}" data-d="mesma">${ic('link')}É a mesma empresa (unir)</button><button class="btn pequeno" data-acao="dup" data-a="${x.a}" data-b="${x.b}" data-d="diferentes">São diferentes</button></span></div></div>`)}
      <div class="cab-entidade"><div class="avatar">${(e.nome || '?').trim()[0]?.toUpperCase()}</div>
        <div class="info"><h2>${e.nome || '(sem nome)'}</h2><div class="meta">${badge(ST_EMP, e.status)} ${conf(e.confianca)}
          ${e.cidade || e.uf ? html`<span>${ic('mapa')} ${[e.cidade, e.uf].filter(Boolean).join('/')}</span>` : ''} ${segChips(e.segmentos_perfil, e.segmentos_inferidos)}</div></div>
        <div class="acoes">${links.map(([u, i, r]) => html`<a class="btn pequeno" href="${u}" target="_blank" rel="noopener">${ic(i)}${r}</a>`)}
          <button class="btn pequeno" data-acao="repesquisar">${ic('atualizar')}Pesquisar novamente</button></div></div>
      <div class="grade g-lado">
        <div>
          <section class="card"><div class="card-cab"><h2>Dados coletados</h2>
            <span class="sub">${a ? html`pesquisa de ${data(a.data)}${a.revisado_em ? html`, revisada em ${data(a.revisado_em)}` : ''} · <a href="#/execucoes/${encodeURIComponent(a.execucao_id)}">${a.execucao_nome}</a>` : ''}</span></div>
            ${outrasMaisNovas.length ? html`<div class="aviso info">${ic('info')}<div>Há pesquisa mais recente com erro técnico; esta é a mais recente válida. Veja o histórico abaixo.</div></div>` : ''}
            <div class="campos">${d.campos.map((c) => html`<div class="rot">${c.rotulo}</div><div class="val">${c.valores.length ? c.valores.map((x) => html`<div class="v">
                <span class="${x.confirmado ? '' : 'nc-valor'}">${urlSegura(x.valor) ? html`<a href="${urlSegura(x.valor)}" target="_blank" rel="noopener">${c.campo === 'google_maps' ? 'Abrir no mapa' : x.valor.replace(/^https?:\/\/(www\.)?/, '').slice(0, 70)}</a>` : x.valor}</span>
                <span class="fonte">${ORIGEM[x.origem] || x.origem}${urlSegura(x.fonte) ? html` · <a href="${urlSegura(x.fonte)}" target="_blank" rel="noopener">fonte</a>` : ''}${x.confirmado ? '' : ' · não confirmado'}</span></div>`) : html`<span class="mut">—</span>`}</div>
              <div class="est">${badge(EST_CAMPO, c.estado)}</div>`)}</div>
            ${d.endereco_completo ? html`<p style="margin:12px 0 0"><b>Endereço completo:</b> ${d.endereco_completo}</p>` : ''}
          </section>
          ${d.divergencias.length || d.observacoes.length ? html`<section class="card"><div class="card-cab"><h2>Observações da pesquisa</h2></div>
            ${d.divergencias.map((t) => html`<div class="aviso">${ic('alerta')}<div><b>Divergência</b> · ${t}</div></div>`)}
            <ul class="pequeno-txt">${d.observacoes.map((t) => html`<li>${t}</li>`)}</ul></section>` : ''}
          <section class="card"><div class="card-cab"><h2>Histórico de pesquisas</h2></div>
            <div class="tabela-wrap"><table><thead><tr><th>Data</th><th>Execução</th><th>Entrada</th><th>Status</th><th>CNPJ</th><th></th></tr></thead><tbody>
            ${d.historico.map((h) => html`<tr><td>${data(h.data)}${h.revisado_em ? html`<span class="sub">revisada ${data(h.revisado_em)}</span>` : ''}</td>
              <td><a href="#/execucoes/${encodeURIComponent(h.execucao_id)}">${h.execucao_nome}</a>${h.arquivada ? html` <span class="chip">arquivada</span>` : ''}${h.origem_execucao ? html`<span class="sub">a partir de ${h.origem_execucao.replace(/^ig:/, 'análise ')}</span>` : ''}</td>
              <td>${h.entrada}</td><td>${badge(ST_EMP, h.status)} ${conf(h.confianca)}</td><td class="mono">${h.cnpj ? html`${fmtCnpj(h.cnpj)}${h.cnpj_confirmado ? '' : html` <span class="nc-valor">não conf.</span>`}` : '—'}</td>
              <td>${h.atual ? html`<span class="badge info">exibida</span>` : ''}${d.historico.length > 1 ? html` <button class="btn pequeno fantasma" data-acao="separar" data-p="${h.id}" title="Esta pesquisa é de outra empresa">separar</button>` : ''}</td></tr>`)}
            </tbody></table></div></section>
          ${d.candidatos_cnpj.length || d.alternativas.length ? html`<section class="card"><details class="secao"><summary>Candidatos a CNPJ e alternativas descartadas (${d.candidatos_cnpj.length + d.alternativas.length})</summary>
            <div class="tabela-wrap" style="margin-top:10px"><table><thead><tr><th>CNPJ</th><th>Escolhido</th><th>Razão social</th><th>Cidade</th><th>Situação</th><th class="num">Pontos</th><th>Motivos</th></tr></thead><tbody>
            ${d.candidatos_cnpj.map((c) => html`<tr><td class="mono">${c.cnpj}</td><td>${c.escolhido || '—'}</td><td>${c.razao_social}${c.nome_fantasia ? html`<span class="sub">${c.nome_fantasia}</span>` : ''}</td><td>${c.cidade}</td><td>${c.situacao}</td><td class="num">${c.pontuacao}</td><td class="pequeno-txt">${Array.isArray(c.motivos) ? c.motivos.join('; ') : c.motivos}</td></tr>`)}
            </tbody></table></div>
            ${d.alternativas.length ? html`<ul class="pequeno-txt">${d.alternativas.map((x) => html`<li><b>${x.tipo}</b> ${x.valor} — ${x.motivo}</li>`)}</ul>` : ''}</details></section>` : ''}
          ${d.correcoes.length ? html`<section class="card"><div class="card-cab"><h2>Revisões registradas</h2></div><ul class="pequeno-txt">${d.correcoes.map((c) => html`<li>${data(c.em)} · <b>${c.campo}</b>${c.valor ? ': ' + c.valor : ''} ${c.confirmar ? '(confirmado)' : c.remover ? '(removido)' : c.nao_confirmado ? '(não confirmado)' : ''} ${c.nota ? '— ' + c.nota : ''} ${urlSegura(c.fonte) ? html`· <a href="${urlSegura(c.fonte)}" target="_blank" rel="noopener">fonte</a>` : c.fonte ? '· fonte: ' + c.fonte : ''}</li>`)}</ul></section>` : ''}
        </div>
        <div>
          <section class="card"><div class="card-cab"><h2>Situação dos dados</h2></div>
            <dl class="dl"><dt>Completude</dt><dd><span class="medidor"><i><b style="width:${(100 * e.completude) / 9}%"></b></i>${e.completude} de 9 dados principais</span></dd>
              <dt>Não confirmados</dt><dd>${e.nao_confirmados || 'nenhum'}</dd><dt>Não encontrados</dt><dd>${d.nao_encontrados.join(', ') || 'nenhum'}</dd>
              <dt>Revisão</dt><dd>${e.revisada ? 'revisada' : e.precisa_revisao ? html`<span class="badge atencao">${ic('meia')}precisa de revisão</span>` : 'não precisa'}</dd>
              <dt>Última pesquisa</dt><dd>${data(e.ultima_pesquisa)} (${plural(e.n_pesquisas, 'pesquisa', 'pesquisas')})</dd>
              <dt>Segmentos</dt><dd>${e.segmentos_perfil.length || e.segmentos_inferidos.length ? html`${e.segmentos_perfil.map((s) => html`<div>${segChips([s])} ${segNome(s)} <span class="mut pequeno-txt">(perfil identificado)</span></div>`)}${e.segmentos_inferidos.map((s) => html`<div>${segChips([], [s])} ${segNome(s)} <span class="mut pequeno-txt">(inferido, não confirmado)</span></div>`)}` : 'nenhum identificado'}</dd></dl>
            ${a ? html`<hr class="sep"><p class="pequeno-txt">Revisão dos dados incertos:</p>
              <div class="acoes"><button class="btn pequeno" data-acao="copiar_pedido" data-id="${a.execucao_id}" data-max="15">${ic('copiar')}Copiar pedido</button>
              <a class="btn pequeno" href="#/execucoes/${encodeURIComponent(a.execucao_id)}">${ic('claude')}Revisar o lote</a></div>` : ''}</section>
          <section class="card"><div class="card-cab"><h2>${ic('instagram')} Perfis do Instagram</h2></div>
            ${d.perfis.length ? d.perfis.map((p) => html`<div class="vinculo"><div><a href="#/perfis/${encodeURIComponent(p.usuario)}"><b>@${p.usuario}</b></a> ${badge(EST_VINC, p.estado)} ${p.manual ? html`<span class="chip">decisão sua</span>` : ''}
                <div class="pequeno-txt mut">${p.evidencia || ''}${urlSegura(p.fonte) ? html` · <a href="${urlSegura(p.fonte)}" target="_blank" rel="noopener">fonte</a>` : ''}</div>
                ${p.analisado ? html`<div class="pequeno-txt">${badge(SIT_PERFIL, p.situacao)} ${segChips(p.segmentos)} ${p.seguidores != null ? html`<span class="mut">${num(p.seguidores)} seguidores</span>` : ''}</div>` : html`<div class="pequeno-txt mut">perfil ainda não analisado pela pesquisa do Instagram</div>`}</div>
              <div class="acoes">${p.estado !== 'confirmado' ? html`<button class="btn pequeno" data-acao="vinc" data-u="${p.usuario}" data-e="confirmado">${ic('check')}Confirmar</button>` : ''}${p.estado !== 'rejeitado' ? html`<button class="btn pequeno fantasma" data-acao="vinc" data-u="${p.usuario}" data-e="rejeitado">Não é desta empresa</button>` : ''}</div></div>`)
              : html`<p class="mut pequeno-txt">Nenhum perfil vinculado.</p>`}
            <form data-form="vincular" class="acoes" style="margin-top:12px"><input type="text" name="usuario" placeholder="@perfil" aria-label="@ do perfil para vincular" style="flex:1"><button class="btn pequeno">${ic('link')}Vincular</button></form>
          </section>
        </div>
      </div>`);
  };
  app.acoes.vinc = async (b) => { if (await executar(() => post(`/api/empresas/${id}/vincular`, { usuario: b.dataset.u, estado: b.dataset.e }), b.dataset.e === 'confirmado' ? 'Vínculo confirmado.' : 'Vínculo rejeitado.')) render(); };
  app.enviar.vincular = async (f) => { const u = new FormData(f).get('usuario'); if (u && await executar(() => post(`/api/empresas/${id}/vincular`, { usuario: u, estado: 'confirmado' }), 'Perfil vinculado.')) render(); };
  app.acoes.dup = async (b) => {
    if (b.dataset.d === 'mesma') {
      const ok = await dialogo('Unir as duas empresas', html`<p>As pesquisas, identificadores e vínculos das duas passam a formar <b>uma única empresa</b>. Nenhuma pesquisa é apagada; se errar, use "separar" no histórico.</p>`,
        [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Unir', classe: 'primario', valor: 'ok' }]);
      if (ok !== 'ok') return;
    }
    const r = await executar(() => post('/api/duplicidades', { a: +b.dataset.a, b: +b.dataset.b, decisao: b.dataset.d, manter: +id }), b.dataset.d === 'mesma' ? 'Empresas unidas.' : 'Marcadas como diferentes.');
    if (r) render();
  };
  app.acoes.separar = async (b) => {
    const ok = await dialogo('Separar pesquisa', html`<p>Esta pesquisa passa a ser uma <b>empresa própria</b>, e as duas ficam marcadas como diferentes. Use quando a pesquisa for de outra empresa.</p>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Separar', classe: 'primario', valor: 'ok' }]);
    if (ok !== 'ok') return;
    const r = await executar(() => post(`/api/pesquisas/${encodeURIComponent(b.dataset.p)}/separar`), 'Pesquisa separada.');
    if (r) location.hash = `#/empresas/${r.empresa_id}`;
  };
  app.acoes.repesquisar = async () => {
    const r = await executar(() => post('/api/empresas/atualizar', { ids: [+id] }), 'Nova pesquisa iniciada; o histórico é mantido.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  };
  await render();
});

// ======================================================================================= PERFIS
rota(/^\/perfis$/, 'Perfis do Instagram', 'perfis', async (el, _, q0) => {
  await carregarSegmentos();
  const f = { ...q0 };
  const lista = (k) => (f[k] ? String(f[k]).split(',') : []);
  const painelAberto = ['segmento', 'situacao', 'confianca', 'empresa', 'revisado'].some((k) => f[k]);
  put(el, html`<div class="filtros"><input type="search" data-f="q" value="${f.q || ''}" placeholder="Buscar @, nome, bio ou cidade…" aria-label="Buscar perfis">
      <button class="btn filtros-btn" data-acao="filtros_painel" aria-expanded="${String(painelAberto)}" aria-controls="filtros-painel">${ic('filtro')}Filtros<span id="n-filtros"></span></button>
      ${selecao('ordenar', 'Ordenar: identificados primeiro', [['usuario', '@ (A–Z)'], ['-seguidores', 'Mais seguidores'], ['-em', 'Analisados recentemente']], f.ordenar)}</div>
    <div class="filtros-painel" id="filtros-painel" ${painelAberto ? '' : 'hidden'}>
      ${multi('segmento', 'Segmento', SEGS.map((s) => ({ valor: s.codigo, rotulo: `${s.codigo} · ${s.nome}` })), lista('segmento'))}
      ${multi('situacao', 'Situação', Object.entries(SIT_PERFIL).map(([k, v]) => ({ valor: k, rotulo: v[1] })), lista('situacao'))}
      ${multi('confianca', 'Confiança', [['alta', 'alta'], ['media', 'média'], ['baixa', 'baixa']].map(([v, r]) => ({ valor: v, rotulo: r })), lista('confianca'))}
      ${selecao('empresa', 'Empresa: todas', [['com', 'com empresa vinculada'], ['sem', 'sem empresa (aguardando pesquisa)'], ['sugerido', 'com vínculo sugerido']], f.empresa)}
      ${selecao('revisado', 'Revisão: todos', [['sim', 'revisados'], ['nao', 'não revisados']], f.revisado)}
    </div>
    <div class="resultado-cab"><span id="acao-perfis"></span></div><div id="itens"></div>`);
  const carregar = async () => {
    trocarQuery(f);
    const nAtivos = ['segmento', 'situacao', 'confianca', 'empresa', 'revisado'].filter((k) => f[k]).length;
    put($('#n-filtros'), nAtivos ? html` <span class="qt">${nAtivos}</span>` : '');
    const d = await api('/api/perfis?' + qs(f));
    put($('#itens'), tabelaPerfis(d, 'pagina'));
    put($('#acao-perfis'), f.empresa === 'sem' && d.total ? html`<button class="btn primario pequeno" data-acao="pesq_perfis">${ic('busca')}Pesquisar empresas destes ${num(Math.min(d.total, 500))} perfis</button>` : '');
  };
  let espera;
  app.mudar = (t) => {
    const m = t.closest('details.multi');
    if (m) { const v = $$('input:checked', m).map((i) => i.value).join(','); if (v) f[m.dataset.multi] = v; else delete f[m.dataset.multi]; resumoMulti(m); f.pagina = 1; return carregar(); }
    if (t.dataset.sel) { if (t.value) f[t.dataset.sel] = t.value; else delete f[t.dataset.sel]; f.pagina = 1; return carregar(); }
    if (t.dataset.f === 'q') { clearTimeout(espera); espera = depois(() => { if (t.value.trim()) f.q = t.value.trim(); else delete f.q; f.pagina = 1; carregar(); }, 300); }
  };
  app.acoes.pagina = (b) => { f.pagina = b.dataset.pagina; carregar(); window.scrollTo(0, 0); };
  app.acoes.pesq_perfis = async () => {
    const ok = await dialogo('Pesquisar empresas destes perfis', html`<p>Cria uma pesquisa de empresas com os perfis filtrados (até 500), pulando os que já têm empresa pesquisada recentemente.</p>`,
      [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Pesquisar', classe: 'primario', valor: 'ok' }]);
    if (ok !== 'ok') return;
    const r = await executar(() => post('/api/perfis/pesquisar-empresas', { filtros: f }), 'Pesquisa de empresas iniciada.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  };
  await carregar();
});

rota(/^\/perfis\/(.+)$/, 'Perfil', 'perfis', async (el, [u]) => {
  await carregarSegmentos();
  const render = async () => {
    const d = await api(`/api/perfis/${encodeURIComponent(u)}`);
    const p = d.perfil, c = p.classificacao || {}, pf = p.perfil || {};
    $('#titulo').textContent = '@' + p.usuario;
    put(el, html`<a class="voltar" href="#/perfis" data-acao="voltar">${ic('voltar')}Voltar</a>
      <div class="cab-entidade"><div class="avatar">${ic('instagram')}</div><div class="info"><h2>@${p.usuario}</h2>
        <div class="meta">${badge(SIT_PERFIL, p.situacao)} ${conf(p.confianca)} ${segChips(p.segmentos)} <span>${p.nome || ''}</span>${p.categoria_ig ? html`<span class="chip">${p.categoria_ig}</span>` : ''}</div></div>
        <div class="acoes"><a class="btn pequeno" href="https://www.instagram.com/${p.usuario}/" target="_blank" rel="noopener">${ic('externo')}Abrir no Instagram</a>
          <button class="btn pequeno primario" data-acao="pesq_um">${ic('busca')}Pesquisar a empresa</button></div></div>
      <div class="grade g-lado"><div>
        <section class="card"><div class="card-cab"><h2>Perfil</h2></div>
          ${p.bio ? html`<div class="bio">${p.bio}</div>` : html`<p class="mut">Bio não lida ou vazia (${p.estado_analise || '—'}).</p>`}
          <dl class="dl" style="margin-top:12px"><dt>Seguidores</dt><dd>${num(p.seguidores)}</dd><dt>Tipo</dt><dd>${p.tipo_perfil || '—'} ${p.conta_comercial ? '· conta comercial' : ''}</dd>
            <dt>Link na bio</dt><dd>${urlSegura(p.link_externo) ? html`<a href="${urlSegura(p.link_externo)}" target="_blank" rel="noopener">${p.link_externo}</a>` : p.link_externo || '—'}</dd>
            <dt>Cidade</dt><dd>${p.cidade || '—'}</dd><dt>Telefone</dt><dd>${p.telefone || '—'}</dd><dt>E-mail</dt><dd>${p.email || '—'}</dd>
            <dt>Etapas</dt><dd>${(c.etapas?.length ? c.etapas : pf.etapas || []).join(', ') || '—'}</dd><dt>Fontes usadas</dt><dd>${(c.fontes || []).join('; ') || '—'}</dd></dl></section>
        <section class="card"><div class="card-cab"><h2>Classificação</h2>${p.revisado ? html`<span class="badge bom">${ic('check')}revisado</span>` : ''}</div>
          ${(c.categorias || []).length ? (c.categorias || []).map((k) => html`<div style="margin-bottom:10px"><b>${k.codigo} · ${k.nome}</b> ${conf(k.confianca)} <span class="mut pequeno-txt">pontuação ${k.pontuacao}</span>
            <ul class="pequeno-txt" style="margin:4px 0">${(k.evidencias || []).map((x) => html`<li>${x}</li>`)}</ul>${k.limitacao ? html`<div class="pequeno-txt mut">Limitação: ${k.limitacao}</div>` : ''}</div>`) : html`<p class="mut">Nenhum segmento encontrado.</p>`}
          ${(c.sinais || []).length ? html`<p class="pequeno-txt mut">Sinais: ${c.sinais.join(' · ')}</p>` : ''}
          ${c.revisao ? html`<p class="pequeno-txt">Nota da revisão: ${c.revisao}</p>` : ''}</section>
        ${(pf.posts || []).length ? html`<section class="card"><details class="secao"><summary>Publicações lidas (${pf.posts.length})</summary><ul class="pequeno-txt">${pf.posts.map((x) => html`<li>${x.fixado ? '📌 ' : ''}${(x.texto || '').slice(0, 240)}${x.local ? html` <span class="mut">· ${x.local}</span>` : ''}</li>`)}</ul></details></section>` : ''}
      </div><div>
        <section class="card"><div class="card-cab"><h2>${ic('predio')} Empresa</h2></div>
          ${d.vinculos.length ? d.vinculos.map((v) => html`<div class="vinculo"><div><a href="#/empresas/${v.empresa_id}"><b>${v.empresa_nome}</b></a> ${badge(EST_VINC, v.estado)}
            <div class="pequeno-txt mut">${[v.cidade, v.uf].filter(Boolean).join('/')} · ${v.evidencia}</div></div></div>`) : html`<p class="mut pequeno-txt">Nenhuma empresa vinculada.</p>`}</section>
        <section class="card"><div class="card-cab"><h2>Análises em que apareceu</h2></div>
          <div class="lista-exec">${d.execucoes.map((x) => html`<a class="item-exec" href="#/execucoes/${encodeURIComponent(x.execucao_id)}"><span class="tipo-ico">${ic('instagram')}</span><span><span class="t">${x.referencia}</span><span class="s">${data(x.em)} · segmentos ${x.segmentos.join(', ') || '—'}</span></span>${badge(SIT_PERFIL, x.situacao)}</a>`)}</div></section>
      </div></div>`);
  };
  app.acoes.pesq_um = async () => {
    const r = await executar(() => post('/api/perfis/pesquisar-empresas', { usuarios: [u], incluir_pesquisadas: true }), 'Pesquisa iniciada.');
    if (r) location.hash = `#/execucoes/${encodeURIComponent(r.id)}`;
  };
  await render();
});

// ======================================================================================= EXECUÇÕES
rota(/^\/execucoes$/, 'Histórico de execuções', 'execucoes', async (el, _, q0) => {
  const f = { tipo: q0.tipo || '', estado: q0.estado || '', q: q0.q || '', arquivadas: q0.arquivadas || '', pagina: 1 };
  put(el, html`<div class="filtros"><input type="search" data-f="q" value="${f.q}" placeholder="Buscar por nome ou origem…" aria-label="Buscar execuções">
    ${selecao('tipo', 'Tipo: todos', Object.entries(TIPO).map(([k, v]) => [k, v[1]]), f.tipo)}
    ${multi('estado', 'Estado', Object.entries(EST_EXEC).map(([k, v]) => ({ valor: k, rotulo: v[1] })), f.estado ? f.estado.split(',') : [])}
    <label class="marcar pequeno-txt"><input type="checkbox" data-f="arquivadas" ${f.arquivadas ? 'checked' : ''}> mostrar arquivadas</label></div><div id="itens"></div>`);
  let ativo = false;
  const carregar = async () => {
    const d = await api('/api/execucoes?' + qs(f));
    ativo = d.itens.some((x) => x.em_andamento);
    put($('#itens'), d.itens.length ? html`<div class="resultado-cab"><span class="total">${plural(d.total, 'execução', 'execuções')}</span></div>
      <div class="tabela-wrap"><table><thead><tr><th>Tipo</th><th>Execução</th><th>Estado</th><th>Progresso</th><th class="num">Falhas</th><th class="num">Pendentes</th><th>Início</th><th>Atualização</th></tr></thead><tbody>
      ${d.itens.map((x) => { const pct = x.total ? (100 * (x.processados || 0)) / x.total : null; return html`<tr class="clicavel" data-href="#/execucoes/${encodeURIComponent(x.id)}">
        <td><span class="badge">${ic(TIPO[x.tipo][0])}${TIPO[x.tipo][1]}</span></td>
        <td class="nome"><a href="#/execucoes/${encodeURIComponent(x.id)}"><strong>${x.referencia || x.nome}</strong></a><span class="sub">${x.nome}${x.origem_execucao ? ' · a partir de ' + x.origem_execucao : ''}${x.arquivada ? ' · arquivada' : ''}</span></td>
        <td>${badge(EST_EXEC, x.estado)}</td>
        <td style="min-width:150px">${x.tipo !== 'revisao_claude' && pct != null ? barra(pct) : ''}<span class="sub">${progressoExec(x)}</span></td>
        <td class="num">${num(x.falhas)}</td><td class="num">${num(x.pendentes)}</td><td>${data(x.iniciado || x.criado)}</td><td>${rel(x.atualizado)}</td></tr>`; })}
      </tbody></table></div>${paginacao(d)}` : vazio('Nenhuma execução com esses filtros.'));
  };
  let espera;
  app.mudar = (t) => {
    const m = t.closest('details.multi');
    if (m) { f.estado = $$('input:checked', m).map((i) => i.value).join(','); resumoMulti(m); }
    else if (t.dataset.sel) f[t.dataset.sel] = t.value;
    else if (t.dataset.f === 'arquivadas') f.arquivadas = t.checked ? '1' : '';
    else if (t.dataset.f === 'q') { clearTimeout(espera); espera = depois(() => { f.q = t.value; f.pagina = 1; trocarQuery({ ...f, pagina: '' }); carregar(); }, 300); return; }
    f.pagina = 1; trocarQuery({ ...f, pagina: '' }); carregar();
  };
  app.acoes.pagina = (b) => { f.pagina = +b.dataset.pagina; carregar(); };
  await carregar();
  return { atualizar: carregar, intervalo: () => (ativo ? 5000 : 20000) };
});

// ======================================================================================= REVISÃO
rota(/^\/revisao$/, 'Revisão e pendências', 'revisao', async (el, _, q0) => {
  let aba = q0.aba || 'duplicidades';
  const render = async () => {
    const d = await api('/api/pendencias');
    const r = d.resumo;
    const abas = [['duplicidades', 'Duplicidades', d.duplicidades.length], ['vinculos', 'Vínculos sugeridos', d.vinculos.length],
      ['claude', 'Itens incertos', d.execucoes_revisar.length], ['perfis', 'Perfis sem pesquisa', r.perfis_sem_pesquisa]];
    let corpo;
    if (aba === 'duplicidades') {
      corpo = d.duplicidades.length ? d.duplicidades.map((x) => html`<section class="card"><div class="card-cab"><h2>${ic('alerta')} ${x.motivo}</h2><span class="sub">sugerida ${rel(x.em)}</span></div>
        <div class="dup">${[x.empresa_a, x.empresa_b].map((e) => html`<div class="lado"><a href="#/empresas/${e.id}"><strong>${e.nome}</strong></a>${badge(ST_EMP, e.status)}
          <dl class="dl" style="margin-top:8px"><dt>Local</dt><dd>${[e.cidade, e.uf].filter(Boolean).join('/') || '—'}</dd><dt>CNPJ</dt><dd class="mono">${e.cnpj ? html`${fmtCnpj(e.cnpj)}${e.cnpj_confirmado ? '' : html` <span class="nc-valor">não conf.</span>`}` : '—'}</dd>
          <dt>Site</dt><dd>${e.site || '—'}</dd><dt>Instagram</dt><dd>${e.instagram ? '@' + handle(e.instagram) : '—'}</dd><dt>Pesquisas</dt><dd>${e.n_pesquisas}</dd></dl></div>`)}</div>
        <div class="acoes" style="margin-top:12px"><button class="btn primario" data-acao="dup" data-a="${x.a}" data-b="${x.b}" data-d="mesma">${ic('link')}É a mesma empresa (unir)</button>
          <button class="btn" data-acao="dup" data-a="${x.a}" data-b="${x.b}" data-d="diferentes">São empresas diferentes</button></div></section>`)
        : html`<section class="card">${vazio('Nenhuma duplicidade pendente.')}</section>`;
    } else if (aba === 'vinculos') {
      corpo = html`<section class="card">${d.vinculos.length ? d.vinculos.map((v) => html`<div class="vinculo"><div><a href="#/perfis/${encodeURIComponent(v.usuario)}"><b>@${v.usuario}</b></a> ${v.situacao ? badge(SIT_PERFIL, v.situacao) : ''} ${segChips(v.segmentos)}
          → <a href="#/empresas/${v.empresa_id}"><b>${v.empresa_nome}</b></a> <span class="mut">${[v.cidade, v.uf].filter(Boolean).join('/')}</span>
          <div class="pequeno-txt mut">${v.evidencia}${urlSegura(v.fonte) ? html` · <a href="${urlSegura(v.fonte)}" target="_blank" rel="noopener">fonte</a>` : ''}</div></div>
        <div class="acoes"><button class="btn pequeno" data-acao="vinc" data-u="${v.usuario}" data-emp="${v.empresa_id}" data-e="confirmado">${ic('check')}Confirmar</button><button class="btn pequeno fantasma" data-acao="vinc" data-u="${v.usuario}" data-emp="${v.empresa_id}" data-e="rejeitado">Rejeitar</button></div></div>`)
        : vazio('Nenhum vínculo sugerido.')}</section>`;
    } else if (aba === 'claude') {
      corpo = d.execucoes_revisar.length ? html`<section class="card"><p class="pequeno-txt mut">Itens que a automação não conseguiu decidir sozinha.</p>
        <div class="tabela-wrap"><table><thead><tr><th>Execução</th><th class="num">Pendentes</th><th></th></tr></thead><tbody>
        ${d.execucoes_revisar.map((x) => html`<tr><td class="nome"><a href="#/execucoes/${encodeURIComponent(x.id)}"><strong>${x.referencia}</strong></a><span class="sub">${TIPO[x.tipo][1]} · ${x.nome}</span></td><td class="num">${num(x.pendentes)}</td>
          <td><div class="acoes"><button class="btn pequeno" data-acao="copiar_pedido" data-id="${x.id}">${ic('copiar')}Copiar pedido</button><a class="btn pequeno" href="#/execucoes/${encodeURIComponent(x.id)}">${ic('claude')}Revisar em segundo plano…</a></div></td></tr>`)}
        </tbody></table></div></section>` : html`<section class="card">${vazio('Nenhum item incerto pendente.')}</section>`;
    } else {
      corpo = html`<section class="card"><p><b>${num(r.perfis_sem_pesquisa)}</b> perfis identificados ainda não têm empresa pesquisada.</p>
        <div class="acoes"><a class="btn primario" href="#/perfis?situacao=identificado&empresa=sem">${ic('pessoas')}Ver e pesquisar esses perfis</a><a class="btn" href="#/instagram">${ic('instagram')}Pesquisar a partir de uma análise</a></div></section>`;
    }
    put(el, html`<div class="abas">${abas.map(([k, r2, n]) => html`<button aria-pressed="${aba === k}" data-acao="aba" data-aba="${k}">${r2}<span class="qt">${num(n)}</span></button>`)}</div>${corpo}`);
  };
  app.acoes.aba = (b) => { aba = b.dataset.aba; trocarQuery({ aba }); render(); };
  app.acoes.dup = async (b) => {
    if (b.dataset.d === 'mesma') {
      const ok = await dialogo('Unir as duas empresas', html`<p>As pesquisas, identificadores e vínculos passam a formar uma única empresa. Nenhuma pesquisa é apagada; se errar, use "separar" no histórico da empresa.</p>`,
        [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Unir', classe: 'primario', valor: 'ok' }]);
      if (ok !== 'ok') return;
    }
    if (await executar(() => post('/api/duplicidades', { a: +b.dataset.a, b: +b.dataset.b, decisao: b.dataset.d }), b.dataset.d === 'mesma' ? 'Empresas unidas.' : 'Marcadas como diferentes.')) render();
  };
  app.acoes.vinc = async (b) => { if (await executar(() => post(`/api/empresas/${b.dataset.emp}/vincular`, { usuario: b.dataset.u, estado: b.dataset.e }), 'Decisão registrada.')) render(); };
  await render();
});

// ======================================================================================= SISTEMA
rota(/^\/sistema$/, 'Sistema', 'sistema', async (el) => {
  const render = async () => {
    const s = await api('/api/sistema');
    const ses = s.sessao_instagram;
    put(el, html`<div class="grade g2">
      <section class="card"><div class="card-cab"><h2>${ic('instagram')} Sessão do Instagram</h2></div>
        ${ses.configurada ? html`<p>${badge({ ok: ['bom', 'Configurada', 'check'] }, 'ok')} <span class="mut pequeno-txt">${ses.origem} ${ses.salvo_em ? '· ' + data(ses.salvo_em) : ''} · conta id ${ses.conta_id || '?'}</span></p>`
          : html`<p>${badge({ n: ['critico', 'Não configurada', 'alerta'] }, 'n')}</p>`}
        <p class="pequeno-txt mut">A sessão fica criptografada neste computador e só é enviada ao instagram.com. Use uma conta secundária.</p>
        <div class="acoes"><button class="btn" data-acao="sessao" data-s="firefox">Importar do Firefox</button><button class="btn" data-acao="sessao" data-s="testar">Testar</button>${ses.configurada ? html`<button class="btn perigo" data-acao="sessao" data-s="remover">Remover</button>` : ''}</div>
        <form data-form="sessionid" class="acoes" style="margin-top:12px"><input type="password" name="sessionid" placeholder="ou cole o cookie sessionid" autocomplete="off" aria-label="Cookie sessionid" style="flex:1"><button class="btn">Salvar</button></form>
        <div id="msg-sessao"></div></section>
      <section class="card"><div class="card-cab"><h2>${ic('busca')} Busca na internet</h2></div>
        <p>${s.searxng.disponivel ? badge({ ok: ['bom', 'SearXNG local ativo', 'check'] }, 'ok') : badge({ n: ['atencao', 'SearXNG desligado', 'meia'] }, 'n')}</p>
        <p class="pequeno-txt">${s.searxng.disponivel ? 'A pesquisa de empresas usa vários buscadores pelo SearXNG local.' : html`Opcional. Sem ele, a pesquisa usa o <code>ddgs</code>, com menos buscadores. Para ligar, abra o Docker Desktop e rode <code>docker compose up -d</code> na pasta <code>pesquisa-empresas</code>.`}</p>
        <p class="mut pequeno-txt">${s.searxng.url}</p></section>
      <section class="card"><div class="card-cab"><h2>${ic('claude')} Claude Code</h2></div>
        <p>${s.claude.disponivel ? badge({ ok: ['bom', 'Encontrado', 'check'] }, 'ok') : badge({ n: ['atencao', 'Não encontrado', 'meia'] }, 'n')}</p>
        <p class="pequeno-txt">${s.claude.disponivel ? html`Revisão em segundo plano disponível. <span class="mono">${s.claude.caminho}</span>` : 'A revisão em segundo plano precisa do Claude Code (extensão do VS Code) ou da variável PLATAFORMA_CLAUDE. "Copiar pedido" funciona sempre.'}</p></section>
      <section class="card"><div class="card-cab"><h2>Base de consulta</h2></div>
        <dl class="dl">${Object.entries(s.contagens).map(([k, v]) => html`<dt>${{ execucoes: 'Execuções', empresas: 'Empresas', pesquisas: 'Pesquisas de empresa', perfis: 'Perfis do Instagram', vinculos: 'Vínculos perfil ↔ empresa', duplicidades: 'Sugestões de duplicidade' }[k] || k}</dt><dd>${num(v)}</dd>`)}</dl>
        <p class="pequeno-txt mut" style="margin-top:10px">A base é atualizada automaticamente. Suas decisões ficam salvas no banco.</p>
        <div class="acoes"><button class="btn" data-acao="sinc">${ic('atualizar')}Sincronizar agora</button><button class="btn fantasma" data-acao="sinc" data-completa="1">Reimportar tudo</button></div></section>
      <section class="card"><div class="card-cab"><h2>Pastas e parâmetros</h2></div>
        <dl class="dl"><dt>Análises do Instagram</dt><dd class="mono">${s.pastas.instagram}</dd><dt>Pesquisas de empresas</dt><dd class="mono">${s.pastas.empresas}</dd>
          <dt>Banco</dt><dd class="mono">${s.pastas.banco}</dd><dt>Revisões do Claude</dt><dd class="mono">${s.pastas.claude}</dd>
          <dt>Desatualizada após</dt><dd>${s.parametros.dias_desatualizada} dias</dd><dt>Não repetir pesquisa por</dt><dd>${s.parametros.dias_repesquisa} dias</dd><dt>Máximo por lista</dt><dd>${num(s.parametros.max_linhas_lote)} empresas</dd></dl></section>
      <section class="card"><div class="card-cab"><h2>Suas decisões recentes</h2></div>
        ${s.historico.length ? html`<ul class="pequeno-txt">${s.historico.map((h) => html`<li>${data(h.em)} · ${h.descricao}</li>`)}</ul>` : vazio('Nenhuma decisão registrada.')}</section>
    </div>`);
  };
  const msg = (m, erro) => put($('#msg-sessao'), html`<div class="aviso ${erro ? 'critico' : 'info'}">${ic(erro ? 'alerta' : 'info')}<div>${m}</div></div>`);
  app.acoes.sessao = async (b) => {
    if (b.dataset.s === 'remover') {
      const ok = await dialogo('Remover sessão', html`<p>A sessão do Instagram é apagada deste computador. Análises não conseguem coletar até configurar de novo.</p>`, [{ rotulo: 'Cancelar', valor: '' }, { rotulo: 'Remover', classe: 'perigo', valor: 'ok' }]);
      if (ok !== 'ok') return;
    }
    b.disabled = true;
    try { const r = await post(`/api/sessao/${b.dataset.s}`); await render(); msg(r.mensagem, r.ok === false); }
    catch (e) { msg(e.message, true); }
    finally { b.disabled = false; }
  };
  app.enviar.sessionid = async (f) => {
    const v = new FormData(f).get('sessionid');
    if (!v) return;
    try { const r = await post('/api/sessao/definir', { sessionid: v }); f.reset(); await render(); msg(r.mensagem); } catch (e) { msg(e.message, true); }
  };
  app.acoes.sinc = async (b) => { b.disabled = true; const r = await executar(() => post('/api/sincronizar', { completa: !!b.dataset.completa }), (r) => (r.dados || r.estado || r.removidas ? `Base atualizada: ${num((r.dados || 0) + (r.estado || 0))} execução(ões) relida(s)${r.removidas ? `, ${r.removidas} removida(s)` : ''}.` : 'A base já estava atualizada.')); if (r) render(); b.disabled = false; };
  await render();
});

// ------------------------------------------------------------------------------------------- início
montarCasca();
window.addEventListener('hashchange', navegar);
navegar();
statusGlobal();
setInterval(() => { if (!document.hidden) statusGlobal(); }, 6000);
