"use strict";

if (!document.querySelector('link[data-atlas-overview-style="true"]')) {
  const atlasOverviewStyle = document.createElement("link");
  atlasOverviewStyle.rel = "stylesheet";
  atlasOverviewStyle.href = "/assets/atlas_overview.css";
  atlasOverviewStyle.dataset.atlasOverviewStyle = "true";
  document.head.appendChild(atlasOverviewStyle);
}
