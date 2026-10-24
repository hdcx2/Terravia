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

  const scrollToEnd = () => { messages.scrollTop = messages.scrollHeight; };

  const addMessage = (text, who) => {
    const el = document.createElement('p');
    el.className = `chat-message ${who === 'user' ? 'user-message' : 'bot-message'}`;
    el.textContent = text;
    el.style.whiteSpace = 'pre-wrap';   // preserve line breaks (CI lists, profiles)
    messages.append(el);
    scrollToEnd();
    return el;
  };

  // Split the API answer into the body and its "Source:" citation so the
  // citation renders as a small muted footnote rather than part of the blob.
  const renderBotAnswer = (el, answer) => {
    const idx = answer.indexOf('Source:');
    const body = idx >= 0 ? answer.slice(0, idx).trim() : answer.trim();
    const source = idx >= 0 ? answer.slice(idx).trim() : '';
    el.classList.remove('is-pending');
    el.textContent = body;
    el.style.whiteSpace = 'pre-wrap';
    if (source) {
      const cite = document.createElement('span');
      cite.className = 'chat-source';
      cite.textContent = source;
      el.append(document.createElement('br'), cite);
    }
    scrollToEnd();
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
    pending.classList.add('is-pending');
    try {
      const res = await fetch(`${TERRAVIA_API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
      if (res.status === 422) {
        // Validation error (e.g. question too long): tell the user plainly.
        pending.classList.remove('is-pending');
        pending.textContent =
          'That question is too long. Please shorten it to under 500 characters.';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderBotAnswer(pending, data.answer);
    } catch (err) {
      pending.classList.remove('is-pending');
      pending.textContent =
        'Sorry, the health data assistant is unavailable right now. Please try again shortly.';
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
      scrollToEnd();
    }
  });
}
