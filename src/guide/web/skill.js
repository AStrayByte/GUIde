/* GUIde — the "install the skill" page.
 *
 * The daemon knows two things a README cannot: the exact SKILL.md that matches
 * this build, and whether it is installed right now. So the instructions live
 * here and are accurate by construction.
 */

(function (namespace) {
  "use strict";

  const { fill } = namespace.render;

  async function boot() {
    namespace.ui.wireThemeButton(document.getElementById("themeBtn"));

    const info = await (await fetch(`${namespace.ui.API}/skill`)).json();

    document.getElementById("prompt").textContent = info.prompt;
    document.getElementById("command").textContent = info.command;
    document.getElementById("content").textContent = info.content;
    document.getElementById("installPath").textContent = info.install_path;

    fill(
      document.getElementById("promptActions"),
      namespace.ui.copyButton(info.prompt, "Copy the prompt"),
    );
    fill(
      document.getElementById("commandActions"),
      namespace.ui.copyButton(info.command, "Copy"),
    );
    fill(
      document.getElementById("contentActions"),
      namespace.ui.copyButton(info.content, "Copy SKILL.md"),
    );

    paintStatus(info);
    document
      .getElementById("installBtn")
      .addEventListener("click", () => installNow(info));
  }

  function paintStatus(info) {
    const status = document.getElementById("status");
    status.textContent = info.installed
      ? `Installed at ${info.install_path} · guide ${info.guide_version}`
      : `Not installed yet · guide ${info.guide_version}`;
    status.classList.toggle("good", Boolean(info.installed));
  }

  async function installNow(info) {
    const button = document.getElementById("installBtn");
    const result = document.getElementById("installResult");
    button.disabled = true;
    result.textContent = "writing…";

    try {
      const response = await fetch(`${namespace.ui.API}/skill/install`, { method: "POST" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const written = await response.json();
      result.textContent = `wrote ${written.path} — restart Claude Code`;
      result.classList.add("good");
      paintStatus({ ...info, installed: true });
    } catch (error) {
      result.textContent = `could not write it: ${error.message}`;
      result.classList.add("bad");
    } finally {
      button.disabled = false;
    }
  }

  namespace.ui.restoreTheme();

  window.addEventListener("DOMContentLoaded", () => {
    boot().catch((error) => {
      document.getElementById("status").textContent =
        `Could not reach the daemon: ${error.message}`;
    });
  });
})((window.GUIde = window.GUIde || {}));
