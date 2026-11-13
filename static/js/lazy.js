// Swaps data-src into src when an image nears the viewport (tests JS-only image loading).
(function () {
  var imgs = document.querySelectorAll("img.js-lazy[data-src]");
  function load(img) { img.src = img.getAttribute("data-src"); img.removeAttribute("data-src"); }
  if (!("IntersectionObserver" in window)) { imgs.forEach(load); return; }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { load(en.target); io.unobserve(en.target); } });
  }, { rootMargin: "300px" });
  imgs.forEach(function (img) { io.observe(img); });
})();
