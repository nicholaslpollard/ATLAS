"use strict";

[
  ["atlas-overview-style", "/assets/atlas_overview.css"],
  ["atlas-tabs-style", "/assets/atlas_tabs.css"],
  ["atlas-status-style", "/assets/atlas_status.css"],
].forEach(([key, href]) => {
  if (document.querySelector(`link[data-atlas-style="${key}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.dataset.atlasStyle = key;
  document.head.appendChild(link);
});
