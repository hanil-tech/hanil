// 한일특장 homepage motion: drawings sketch in, figures count up, the process line and the
// revenue bars run once when they come into view, the product ticker can be paused.
// Without this script every element shows in its finished state.
(() => {
  const root = document.documentElement;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // the hero drawing sketches itself on load
  requestAnimationFrame(() => document.querySelectorAll("[data-draw]").forEach(el => el.classList.add("is-in")));

  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      const el = en.target;
      el.classList.add("is-in");
      if (el.matches("[data-count]")) count(el);
      io.unobserve(el);
    }
  }, { threshold: 0.25 });

  document.querySelectorAll("[data-reveal], [data-run]").forEach(el => io.observe(el));

  // numbers count up from zero once, keeping their thousands separator
  function count(el) {
    const target = el.dataset.count;
    const n = parseFloat(target.replace(/,/g, ""));
    if (still || !isFinite(n)) return;
    const sep = target.includes(",");
    const t0 = performance.now(), dur = 1400;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      const v = Math.round(n * (1 - Math.pow(2, -10 * p)));
      el.textContent = p >= 1 ? target : (sep ? v.toLocaleString("en-US") : String(v));
      if (p < 1) requestAnimationFrame(step);
    };
    el.textContent = "0";
    requestAnimationFrame(step);
  }
  if (!still) document.querySelectorAll("[data-count]").forEach(el => io.observe(el));

  // ticker pause / play
  document.querySelectorAll(".ticker__pause").forEach(btn => {
    btn.addEventListener("click", () => {
      const t = btn.closest(".ticker");
      const paused = t.classList.toggle("is-paused");
      btn.setAttribute("aria-pressed", String(paused));
      btn.setAttribute("aria-label", paused ? btn.dataset.play : btn.dataset.pause);
      btn.innerHTML = paused
        ? '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.8v8.4L10 6z" fill="currentColor"/></svg>'
        : '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 2v8M9 2v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    });
  });
  root.classList.add("motion-ready");
})();
