/* GUIde — the small things both pages need.
 *
 * Two kinds of thing, and the file is named for holding both rather than
 * pretending to hold one: the chrome each page draws but neither page is
 * *about* (the theme toggle, the copy button), and the one constant they both
 * address the daemon by.
 *
 * It exists because the same forty lines were pasted into app.js and skill.js
 * and had already drifted — different fallback text, different timings. Kept
 * small deliberately: this is not a utils.js, and anything that belongs to one
 * page stays on that page.
 */

(function (namespace) {
  "use strict";

  const { el } = namespace.render;

  /* The versioned HTTP surface. Stated once, here rather than in transport.js,
     because skill.js talks to the daemon too and does not load transport.js.
     See docs/decisions/0005. */
  const API = "/api/v0";

  const COPIED_MS = 1700;

  /* A button that copies `text`. Falls back to telling the reader to do it by
     hand, because clipboard access is denied often enough — an insecure origin,
     a locked-down browser — that a silent no-op would be the worst outcome. */
  function copyButton(text, label) {
    const name = label || "Copy";
    const button = el(
      "button",
      {
        type: "button",
        class: "btn",
        onclick: async () => {
          try {
            await navigator.clipboard.writeText(text);
            button.textContent = "Copied";
          } catch {
            button.textContent = "Select it and press ⌘C";
          }
          setTimeout(() => {
            button.textContent = name;
          }, COPIED_MS);
        },
      },
      name,
    );
    return button;
  }

  /* Dark by default; the choice is remembered per browser and nowhere else. */
  function restoreTheme() {
    try {
      const saved = localStorage.getItem("guide.theme");
      if (saved) document.documentElement.dataset.theme = saved;
    } catch {
      /* dark is the default anyway */
    }
  }

  function wireThemeButton(button) {
    const paint = () => {
      button.textContent =
        document.documentElement.dataset.theme === "light" ? "dark" : "light";
    };
    button.addEventListener("click", () => {
      const root = document.documentElement;
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      try {
        localStorage.setItem("guide.theme", root.dataset.theme);
      } catch {
        /* the choice just will not survive a reload */
      }
      paint();
    });
    paint();
  }

  namespace.ui = { API, copyButton, restoreTheme, wireThemeButton };
})((window.GUIde = window.GUIde || {}));
