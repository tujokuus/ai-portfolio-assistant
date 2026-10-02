// No framework or build step: this file connects the page to our Python server.
const form = document.querySelector('#chat-form');
const questionInput = document.querySelector('#question');
const messages = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const sendButton = document.querySelector('#send');
const clearButton = document.querySelector('#clear');
const examples = document.querySelectorAll('.example');
let busy = false;

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  clearButton.disabled = value;
  questionInput.disabled = value;
  examples.forEach(button => { button.disabled = value; });
  sendButton.textContent = value ? 'Preparing answer…' : 'Send question ↗';
  status.textContent = value ? 'Reading the portfolio and preparing an answer…' : '';
  form.setAttribute('aria-busy', String(value));
}

function addMessage(role, text, sources = []) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const heading = document.createElement('h2');
  heading.textContent = role === 'user' ? 'You' : 'Portfolio assistant';
  const paragraph = document.createElement('p');
  // Treat both user and model output as text, never executable HTML.
  paragraph.textContent = text;
  article.append(heading, paragraph);

  if (sources.length) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = `Sources (${sources.length})`;
    const list = document.createElement('ul');
    for (const source of sources) {
      const item = document.createElement('li');
      item.textContent = `[${source.id}] ${source.title}`;
      const file = document.createElement('span');
      file.className = 'source-file';
      file.textContent = source.file;
      item.append(file);
      list.append(item);
    }
    details.append(summary, list);
    article.append(details);
  }
  messages.append(article);
  return article;
}

examples.forEach(button => {
  button.addEventListener('click', () => {
    questionInput.value = button.textContent;
    questionInput.focus();
  });
});

clearButton.addEventListener('click', () => {
  if (busy) return;
  messages.replaceChildren();
  welcome.hidden = false;
  error.hidden = true;
  questionInput.value = '';
  questionInput.focus();
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.setCustomValidity('Please write a question.');
    questionInput.reportValidity();
    return;
  }
  error.hidden = true;
  welcome.hidden = true;
  const userMessage = addMessage('user', question);
  setBusy(true);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string'
        ? data.detail : 'The question could not be processed. Please check its length.');
    }
    addMessage('assistant', data.answer, data.sources);
    questionInput.value = '';
  } catch (problem) {
    // Keep the question for manual retry; never automatically repeat a paid call.
    userMessage.remove();
    welcome.hidden = messages.childElementCount > 0;
    error.textContent = problem instanceof TypeError || problem instanceof SyntaxError
      ? 'Could not reach the local server. Check the terminal. Your question is still below.'
      : problem.message;
    error.hidden = false;
  } finally {
    setBusy(false);
    questionInput.focus();
  }
});

questionInput.addEventListener('input', () => questionInput.setCustomValidity(''));
