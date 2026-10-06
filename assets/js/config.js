/* =====================================================================
   Settings for the "AI agents for bioinformatics" practical.
   Edit and re-upload this file; nothing else needs to change.
   (The text of the chapters is in build/chapters.py – see README.md.)
   ===================================================================== */
window.MG_CONFIG = {
  /* Title and subtitle in the header of the page (also the title of the browser tab and of the
     files of answers); the name in the terminal prompt. */
  courseTitle: 'AI agents for bioinformatics',
  courseSubtitle: 'From a prompt to an analysis you can repeat',
  hostname: 'biolab',
  /* The prefix of what the page keeps in the browser. Change it only if two copies of the
     practical on one site must not share their saved work. */
  storePrefix: 'aiagents',

  /* true: the questions with a model answer have a "Show answer" button (it does not wait for an
     answer of the student's; multiple-choice questions explain each option instead).
     false: the "Show answer" buttons are hidden (add ?answers to the address to see them).
     The answers are still in the page source, so this is not a way to keep them secret. */
  showModelAnswers: true,

  /* The WebAssembly programs (fastp, minimap2, Bowtie 2, samtools, bcftools, GNU tools …). */
  biowasmBase: 'assets/vendor/biowasm',

  /* The AI in this practical is always a real model. Each student enters an API key in the
     AI tab; the key stays in that browser tab and is sent only to the chosen service.
     Never put an API key in this file – anyone could copy it from a public site.

     The service offered first ('gemini', 'anthropic' or 'openai') and the model of each.
     Google's Gemini API has a free tier (a key from aistudio.google.com/apikey).
     Models are retired from time to time: if the AI reports that a model is not found,
     put a current one here (see ai.google.dev/gemini-api/docs/models). */
  liveProvider: 'gemini',
  geminiModel: 'gemini-3.8-flash',
  /* If that model is busy ("high demand", HTTP 503), over a limit (429), not found (404) or
     gives no answer, these models are asked in turn; the answer says which one replied. The
     page remembers a model that could not answer and does not ask it again at once.
     On the free tier every model has limits of its own, per minute and per day, so a longer
     list gives a free key more requests in a day: put the models first that you would rather
     have. [] turns this off. (All of these answered a free key on 6 October 2026.) */
  geminiFallbackModels: ['gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'],
  /* How many seconds a Gemini model may say nothing – before its answer begins, or in the
     middle of it – until the page gives that request up and asks the next model. */
  aiWaitSeconds: 60,
  anthropicModel: 'claude-sonnet-5-5',

  /* The agent: the most steps one task may take (a step is one reply of the model: a file,
     a block of commands, or both); how many characters of each command's output the model
     is sent; and after how many seconds a command that has not ended is stopped. */
  agentMaxSteps: 20,
  agentOutputChars: 3000,
  agentCommandSeconds: 150
};
