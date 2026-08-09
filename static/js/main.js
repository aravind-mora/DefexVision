// DefexVision frontend helpers
document.addEventListener('DOMContentLoaded', () => {
  // auto-dismiss alerts
  document.querySelectorAll('.alert').forEach(a => {
    setTimeout(() => { a.style.opacity = '0'; a.style.transition = 'opacity .5s'; }, 5000);
  });
});
