// No framework or build step: this file connects the page to our Python server.
const form = document.querySelector('#chat-form');
const questionInput = document.querySelector('#question');
const messages = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const characterCount = document.querySelector('#character-count');
const questionLimitError = document.querySelector('#question-limit-error');
const sendButton = document.querySelector('#send');
const clearButton = document.querySelector('#clear');
const examples = [...document.querySelectorAll('.example')];
const suggestions = document.querySelector('.suggestions');
const maxQuestionChars = 2000;
let busy = false;
let overLimit = false;
let selectedExample = null;

function setBusy(value) {
  busy = value;
  sendButton.disabled = value || overLimit;
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
    const sourceList = document.createElement('div');
    sourceList.className = 'sources';
    const label = document.createElement('h3');
    label.textContent = `Sources (${sources.length})`;
    sourceList.append(label);
    for (const source of sources) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = `[${source.id}] ${source.title}`;
      const file = document.createElement('span');
      file.className = 'source-file';
      file.textContent = source.file;
      const original = document.createElement('a');
      original.className = 'source-original';
      original.href = source.url;
      original.target = '_blank';
      original.rel = 'noopener noreferrer';
      original.textContent = source.file.endsWith('.pdf') ? 'Open original CV (PDF)' : 'Open original README';
      const content = document.createElement('div');
      content.className = 'source-text';
      // Show the original document as plain text, including Markdown notation.
      content.textContent = source.text;
      details.append(summary, file, original, content);
      sourceList.append(details);
    }
    article.append(sourceList);
  }
  messages.append(article);
  return article;
}

function removeAskedExample(question) {
  const normalizedQuestion = question.trim().toLocaleLowerCase();
  const selectedMatch = selectedExample && selectedExample.textContent.trim().toLocaleLowerCase() === normalizedQuestion
    ? selectedExample : null;
  const askedExample = selectedMatch || examples.find(button =>
    button.textContent.trim().toLocaleLowerCase() === normalizedQuestion
  );
  selectedExample = null;
  if (!askedExample) return;
  askedExample.remove();
  if (!suggestions.querySelector('.example')) suggestions.hidden = true;
}

function updateQuestionLength() {
  const count = Array.from(questionInput.value).length;
  overLimit = count > maxQuestionChars;
  characterCount.textContent = `${count} / ${maxQuestionChars} characters`;
  questionLimitError.textContent = overLimit
    ? `The 2,000-character limit has been exceeded by ${count - maxQuestionChars}. Shorten your question before sending.`
    : '';
  questionLimitError.hidden = !overLimit;
  sendButton.disabled = busy || overLimit;
}

examples.forEach(button => {
  button.addEventListener('click', () => {
    selectedExample = button;
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
  updateQuestionLength();
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
  updateQuestionLength();
  if (overLimit) {
    questionInput.focus();
    return;
  }
  error.hidden = true;
  welcome.hidden = true;
  removeAskedExample(question);
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
    updateQuestionLength();
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

questionInput.addEventListener('keydown', event => {
  // Enter may confirm a composed character; it must not send that question.
  if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return;
  if (event.ctrlKey) {
    event.preventDefault();
    if (busy || event.repeat) return;
    const start = questionInput.selectionStart;
    const end = questionInput.selectionEnd;
    if (questionInput.value.length - (end - start) < questionInput.maxLength) {
      questionInput.setRangeText('\n', start, end, 'end');
      questionInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return;
  }
  // Preserve native Shift+Enter and other modified keyboard shortcuts.
  if (event.shiftKey || event.altKey || event.metaKey) return;
  event.preventDefault();
  if (!busy && !event.repeat) form.requestSubmit();
});

questionInput.addEventListener('input', () => {
  questionInput.setCustomValidity('');
  updateQuestionLength();
});

updateQuestionLength();
