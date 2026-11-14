"use strict";

// The page's one MediaRecorder and one Audio element. Limits come from /api/status `voice`.
const Voice = (() => {
  const player = new Audio();
  const SILENT = "data:audio/wav;base64,UklGRnQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YVAAAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA==";
  let rec = null, current = null;

  const mimeFor = v => v.mimes.find(m => MediaRecorder.isTypeSupported(m));
  const canListen = v => Boolean(v?.available && navigator.mediaDevices?.getUserMedia && window.MediaRecorder && mimeFor(v));

  const base64 = blob => new Promise((ok, fail) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(",")[1] ?? "");
    r.onerror = fail;
    r.readAsDataURL(blob);
  });

  async function listen(v) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = mimeFor(v), chunks = [];
    rec = new MediaRecorder(stream, { mimeType: mime });
    rec.ondataavailable = ev => chunks.push(ev.data);
    const stopped = new Promise(ok => { rec.onstop = ok; });
    const timer = setTimeout(stop, v.clip_s * 1000);
    rec.start();
    await stopped;
    clearTimeout(timer);
    stream.getTracks().forEach(tr => tr.stop());
    rec = null;
    return { audio: await base64(new Blob(chunks, { type: mime })), mime };
  }

  function stop() {
    if (rec?.state === "recording") rec.stop();
  }

  function speak(url) {
    current = url;
    player.src = url;
    player.play().catch(() => {});
  }

  function hush() {
    player.pause();
    current = null;
  }

  const playing = url => current === url && !player.paused && !player.ended;

  // iOS plays audio only inside a tap. Playing a silent clip there lets the answer play later.
  function unlock() {
    hush();
    player.src = SILENT;
    player.play().catch(() => {});
  }

  return { listen, stop, speak, hush, unlock, canListen, playing };
})();
