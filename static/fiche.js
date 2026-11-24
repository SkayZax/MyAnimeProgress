(function () {
    var form = document.querySelector('form.suivi');
    if (!form) return;
    var sortie = document.getElementById('episode-choisi');
    form.addEventListener('input', function (e) {
        if (e.target.name === 'current_episode') sortie.textContent = e.target.value || 0;
    });
    // Amène la case de l'épisode en cours dans la zone visible, sans faire défiler la page
    var cases = form.querySelector('.cases');
    var actuelle = form.querySelector('input:checked');
    if (cases && actuelle) cases.scrollTop = actuelle.parentNode.offsetTop - cases.offsetTop - cases.clientHeight / 2;
})();
