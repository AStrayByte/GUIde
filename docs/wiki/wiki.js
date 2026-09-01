/* Wiki chrome: the shared sidebar and the theme toggle.
 *
 * Injected by script so five pages share one nav and it cannot drift. Classic
 * script, relative paths, no fetch — the wiki has to open over file:// straight
 * out of a clone, the same bet the product page makes (ADR 0007).
 */

(function () {
  "use strict";

  const PAGES = [
    {
      group: "Start here",
      items: [
        { href: "index.html", name: "Overview", note: "what it is, how to run it" },
        { href: "walkthrough.html", name: "A batch, end to end", note: "follow one push" },
      ],
    },
    {
      group: "Reference",
      items: [
        { href: "filesystem.html", name: "The file system", note: "every file, what it's for" },
        { href: "architecture.html", name: "How it's built", note: "the seams and the rules" },
        { href: "decisions.html", name: "Why it's built that way", note: "the ADRs, summarised" },
      ],
    },
  ];

  const here = location.pathname.split("/").pop() || "index.html";

  function sidebar() {
    const nav = document.createElement("nav");
    nav.className = "side";

    const brand = document.createElement("div");
    brand.className = "brand";
    const name = document.createElement("b");
    name.append("GU", Object.assign(document.createElement("i"), { textContent: "I" }), "de");
    const sub = document.createElement("span");
    sub.textContent = "engineering wiki";
    brand.append(name, sub);
    nav.append(brand);

    for (const section of PAGES) {
      const heading = document.createElement("h3");
      heading.textContent = section.group;
      nav.append(heading);
      for (const page of section.items) {
        const link = document.createElement("a");
        link.href = page.href;
        if (page.href === here) link.className = "here";
        link.append(page.name);
        const note = document.createElement("small");
        note.textContent = page.note;
        link.append(note);
        nav.append(link);
      }
    }

    const outHeading = document.createElement("h3");
    outHeading.textContent = "Outside the wiki";
    nav.append(outHeading);
    for (const [href, label] of [
      ["../../README.md", "README"],
      ["../architecture.md", "Product architecture"],
      ["../format.md", "The batch format"],
      ["../versioning.md", "Versioning contract"],
      ["../decisions/", "ADRs, in full"],
      ["../roadmap.md", "Roadmap"],
      ["../open-questions.md", "Open questions"],
    ]) {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      nav.append(link);
    }
    return nav;
  }

  function themeButton() {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "themebtn";
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
    return button;
  }

  try {
    const saved = localStorage.getItem("guide.theme");
    if (saved) document.documentElement.dataset.theme = saved;
  } catch {
    /* dark is the default anyway */
  }

  window.addEventListener("DOMContentLoaded", () => {
    document.querySelector(".shell").prepend(sidebar());
    document.body.append(themeButton());
  });
})();
