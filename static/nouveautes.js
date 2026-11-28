// Ouvre la pop-up « Nouveautés » une seule fois par version, sur chaque appareil
(function () {
    var boite = document.getElementById('nouveautes');
    if (!boite || typeof boite.showModal !== 'function') return;
    var cle = 'nouveautes-vues';
    var version = boite.dataset.version;
    var vue = null;
    try { vue = localStorage.getItem(cle); } catch (e) { return; }
    if (vue === version) return;

    boite.addEventListener('close', function () {
        try { localStorage.setItem(cle, version); } catch (e) {}
    });
    // Un clic sur le fond sombre ferme aussi la pop-up
    boite.addEventListener('click', function (e) {
        if (e.target !== boite) return;
        var r = boite.getBoundingClientRect();
        if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) boite.close();
    });
    boite.querySelector('.maj__pied a').addEventListener('click', function () {
        try { localStorage.setItem(cle, version); } catch (e) {}
    });
    boite.showModal();
})();
