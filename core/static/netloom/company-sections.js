// Preserve bookmarks to sections that now have dedicated pages.
(() => {
  const links = document.getElementById("legacy-company-sections");
  if (!links) return;
  const sections = {
    "#subscribers": links.dataset.users,
    "#users": links.dataset.users,
    "#plans": links.dataset.plans,
    "#routers": links.dataset.routers,
  };
  const target = sections[window.location.hash];
  if (target) window.location.replace(target);
})();
