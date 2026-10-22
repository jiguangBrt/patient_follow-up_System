// Keep requests, navigation and session keys inside this application on a shared host.
(() => {
  const scriptPath = new URL(document.currentScript.src).pathname;
  const prefix = scriptPath.slice(0, scriptPath.lastIndexOf("/static/"));
  function url(path) {
    if (typeof path !== "string" || !path.startsWith("/") || path.startsWith("//")) return path;
    if (prefix && (path === prefix || path.startsWith(prefix + "/"))) return path;
    return prefix + path;
  }
  const key = name => prefix ? `${prefix}:${name}` : name;
  window.AppPaths = {
    prefix,
    url,
    pathname: () => location.pathname.slice(prefix.length) || "/",
    fetch: (path, options) => window.fetch(url(path), options),
    storage: {
      getItem: name => sessionStorage.getItem(key(name)),
      setItem: (name, value) => sessionStorage.setItem(key(name), value),
      removeItem: name => sessionStorage.removeItem(key(name)),
    },
  };
})();
