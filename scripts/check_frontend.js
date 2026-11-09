// Syntax and error handling checks. Run: gjs scripts/check_frontend.js
const GLib = imports.gi.GLib;
const [, data] = GLib.file_get_contents('app/static/app.js');
const source = new TextDecoder().decode(data);
new Function(source);
const helper = source.slice(source.indexOf('async function readResult'), source.indexOf('document.querySelectorAll("a.active")'));
const readResult = new Function(`${helper}; return readResult;`)();
(async () => {
  const value = await readResult({ ok: true, json: async () => ({ translation: 'ok' }) });
  if (value.translation !== 'ok') throw new Error('Success response lost');
  for (const [response, expected] of [
    [{ ok: false, json: async () => ({ detail: [{loc: ['body', 'queries', 0], msg: 'Too long'}] }) }, 'queries / 0: Too long'],
    [{ ok: false, json: async () => ({ detail: 'translation unavailable' }) }, 'translation unavailable'],
    [{ ok: false, json: async () => { throw new Error('HTML'); } }, 'resposta válida'],
  ]) {
    let caught = false;
    try { await readResult(response); } catch (error) {
      if (!error.message.includes(expected)) throw error;
      caught = true;
    }
    if (!caught) throw new Error('Error response accepted');
  }
  print('PASS: JavaScript syntax and 4 response handling scenarios');
})().catch((error) => { printerr(error); imports.system.exit(1); });
