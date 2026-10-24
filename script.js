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

// Base URL of the Terravia chatbot API. Override before this script loads with
//   <script>window.TERRAVIA_API = 'https://your-host';</script>
// Empty string = same origin (when the API also serves the site).
const TERRAVIA_API = (window.TERRAVIA_API || '').replace(/\/$/, '');

const chatForm = document.querySelector('.chat-form');
if (chatForm) {
  const input = chatForm.querySelector('input');
  const sendBtn = chatForm.querySelector('button');
  const messages = document.querySelector('.chat-messages');

  const addMessage = (text, who) => {
    const el = document.createElement('p');
    el.className = `chat-message ${who === 'user' ? 'user-message' : 'bot-message'}`;
    // Preserve the answer's line breaks (CI lists, profiles).
    el.textContent = text;
    el.style.whiteSpace = 'pre-wrap';
    messages.append(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  };

  chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    addMessage(question, 'user');
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    const pending = addMessage('Thinking…', 'bot');
    try {
      const res = await fetch(`${TERRAVIA_API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      pending.textContent = data.answer;
    } catch (err) {
      pending.textContent =
        'Sorry, the health data assistant is unavailable right now. Please try again shortly.';
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
      messages.scrollTop = messages.scrollHeight;
    }
  });
}
