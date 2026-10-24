const sidebar = document.querySelector('.sidebar');
const menuToggle = document.querySelector('.menu-toggle');

if (sidebar && menuToggle) {
  menuToggle.addEventListener('click', () => {
    const expanded = sidebar.classList.toggle('is-expanded');
    menuToggle.setAttribute('aria-expanded', String(expanded));
    menuToggle.setAttribute('aria-label', expanded ? 'Collapse navigation' : 'Expand navigation');
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-expanded')) {
      sidebar.classList.remove('is-expanded');
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Expand navigation');
      menuToggle.focus();
    }
  });

  document.addEventListener('click', (event) => {
    const compact = window.matchMedia('(max-width: 650px)').matches;
    if (compact && sidebar.classList.contains('is-expanded') && !sidebar.contains(event.target)) {
      sidebar.classList.remove('is-expanded');
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Expand navigation');
    }
  });
}

const chatForm = document.querySelector('.chat-form');
if (chatForm) {
  const input = chatForm.querySelector('input');
  const messages = document.querySelector('.chat-messages');
  chatForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    const userMessage = document.createElement('p');
    userMessage.className = 'chat-message user-message';
    userMessage.textContent = question;
    messages.append(userMessage);

    const response = document.createElement('p');
    response.className = 'chat-message bot-message';
    response.textContent = 'I\u2019m a site guide for now. Try the About Us, Concerns, or Our Team links to explore Terravia. A health data assistant can be connected here later.';
    messages.append(response);
    input.value = '';
    input.focus();
    messages.scrollTop = messages.scrollHeight;
  });
}
