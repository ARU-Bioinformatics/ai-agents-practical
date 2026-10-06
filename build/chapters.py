"""The chapters of "AI agents for bioinformatics".

Numbers quoted here come from the programs as they run in the page (see ../README.md, "Checking
the numbers"): 3,519 read pairs; fastp passes 6,170 of 7,038 reads; minimap2 -ax sr maps 96.86 %;
minimap2 + bcftools gives 60 variants, Bowtie 2 + bcftools 50; position 11,616 is G>A, 0/1.
If a program or the data changes, check them again."""
from lib import *

TASK = ('Find the variants of sample NA12878. Map the paired reads data/NA12878_R1.fastq and data/NA12878_R2.fastq to '
        'data/reference.fa, call the variants and save them as variants.vcf.gz (compressed and indexed). '
        'Then tell me the genotype at position 11616 of human_CYP2C19, and the evidence for it.')

# Patterns for the answers that are checked, and for one task. (Kept out of the f-strings below:
# before Python 3.12 an f-string expression may not contain a backslash.)
CMP_RUNS = ("cd ~/runs && for d in */; do echo \"== $d\"; "
            "jq -r '\"model: \" + (.models | join(\", \")), (.steps[].commands[] | select(.code == 0) | .cmd)' $d/run.json"
            " | grep -E '^(model|fastp|minimap2|bowtie2|bcftools (mpileup|call|filter|norm|view -[a-zA-Z]*[ie]))'; done")
RE_PAIRS = r"^3[ ,.]?519( pairs?| read pairs?)?$"
RE_PASSED = r"^6[ ,.]?170"
RE_MAPPED = r"^9[5-8]([.,]\d+)?\s*%?$"
RE_GENOTYPE = r"^0\s*[/|]\s*1$||het"
README_FILLED = r"has:check1/README.md|What I did:\s+(?!\.\.\.)\S"


def loop_figure():
    return '''<div class="loopfig" role="img" aria-label="The agent's loop: the model writes a command, the page runs it in the terminal, the output goes back to the model; this repeats until the model writes its report.">
  <div class="lf-box task"><b>Your task</b><span>in words</span></div>
  <div class="lf-arrow">→</div>
  <div class="lf-cycle">
    <div class="lf-box model"><b>AI model</b><span>reads everything so far, writes the next command</span></div>
    <div class="lf-arrows"><span>command ↓</span><span>↑ what it printed</span></div>
    <div class="lf-box term"><b>Your terminal</b><span>the page runs the command</span></div>
  </div>
  <div class="lf-arrow">→</div>
  <div class="lf-box report"><b>Report</b><span>when the model decides it is done</span></div>
</div>'''


def ch_start():
    body = f'''
<h2 id="s-question">The question</h2>
<p>The gene <i>CYP2C19</i> makes an enzyme that turns the anti-clotting drug clopidogrel into its active form. One common variant, <b><i>CYP2C19*2</i></b> (rs4244285, G&gt;A), stops the enzyme from being made, and people who carry it respond less well to the drug. Your question for today:</p>
<blockquote class="quote">Which genotype does the sample NA12878 have at <i>CYP2C19*2</i>?</blockquote>
<p>You have the sequencing reads of that sample and a reference sequence. In this data the variant is at <b>position 11,616</b> of the sequence called {c("human_CYP2C19")}. You will first look at the data yourself, then answer the question twice – with an AI assistant, and with an AI agent – and in the end make the answer one that someone else can check.</p>

<h2 id="s-tools">What is on this page</h2>
<table class="table">
<tr><th>Terminal</th><td>A Linux-like terminal. The programs are the real ones – fastp, minimap2, Bowtie 2, samtools, bcftools and the GNU text tools – compiled to run in your browser, on this computer. The data is small, so each program takes seconds.</td></tr>
<tr><th>Files</th><td>Your folders, an editor for text files, and a viewer for reports.</td></tr>
<tr><th>AI</th><td>A real AI model, in two roles: <b>Chat</b>, an assistant that answers questions, and <b>Agent</b>, which carries out a task itself.</td></tr>
</table>

{callout("concept", "Assistant or agent?", f"""<p>An <b>assistant</b> writes text. You ask, it answers; <i>you</i> run the commands and read what they print.</p>
<p>An <b>agent</b> is the same kind of model in a loop: it writes a command, the command is run, the model reads what it printed and writes the next command – until it decides the task is done. You say what you want, not how.</p>{loop_figure()}""")}

{activity("Connect the AI", [
    task("s-open", f'Open the <b>AI</b> tab {bench("assistant", "show me")} and read <b>What is sent, and where</b>.'),
    task("s-connect", 'Paste an API key and press <b>Connect</b>. Your lecturer will say which key to use: one that they hand out, or one of your own – for Google’s Gemini API you make one at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> (sign in, <i>Create API key</i>, copy it).', auto="ai:connect ok=true", check="connected"),
    task("s-help", f'In the <b>Terminal</b>, see which programs are there: {cmd("help")} A <i>show me</i> button only types the command – press <kbd>Enter</kbd> to run it.', auto="term:command name=help"),
])}

{callout("warn", "Three rules for today – and for every day after", """<ol>
<li><b>No personal or patient data in an AI tool.</b> What you type, and what the agent’s commands print, goes to the company that runs the model. Today’s data is a public reference sample, so that is fine.</li>
<li><b>The result is yours.</b> An AI can be wrong and sound certain. Whatever you report, you must be able to show where it comes from.</li>
<li><b>A key is a password.</b> Do not share it or put it in a file. This page keeps it in this browser tab only.</li>
</ol>""")}

{callout("info", "Good to know", """<ul>
<li>A free key allows each model only a few requests per minute, and a limited number per day. The agent uses one request for each step.</li>
<li>If a Gemini model is busy, over a limit or gives no answer, the page asks another one, and leaves the first alone for a while: an amber dot beside the model’s name at the top of the AI tab says so. Under each answer you can see which model replied.</li>
<li>When no model can answer for the moment, the agent waits – a countdown is shown – and goes on by itself. If there is still no answer after three waits, the run ends with a message that says what each model said.</li>
<li>Your work is kept in this browser. <b>My answers</b> (top right) downloads your answers; chapter 4 ends with a download of your analysis.</li>
</ul>""")}

{q("s-q1", "Suppose an AI agent tells you: “NA12878 is heterozygous for <i>CYP2C19*2</i>.” What would you want to see before you put that sentence in a report?",
   "<p>The sentence is a claim. The evidence would be: the commands that were run, and the versions of the programs; the line of the variant file for that position – the genotype, its quality, how many reads cover the position and how many support each allele; how well the reads mapped; and that the analysis can be run again and gives the same answer. By the end of this practical you will have all of these.</p>")}
'''
    return chapter("start", "0", "Start here", "assistant", "AI agents for bioinformatics", 10,
                   "AI tools can now do bioinformatics for you: you say what you want, and an agent maps the reads and calls the variants. In this practical you use a real AI model in two ways – as an assistant that answers and as an agent that acts – on real sequencing reads, with real programs. Then you turn what the agent did into an analysis that anyone can repeat.", body)


def ch_look():
    fastp = "fastp -i data/NA12878_R1.fastq -I data/NA12878_R2.fastq -o trimmed_R1.fastq -O trimmed_R2.fastq -h fastp.html -j fastp.json"
    versions = "fastp --version; minimap2 --version; bowtie2 --version | head -1; samtools --version | head -1; bcftools --version | head -1"
    body = f'''
{activity("The files", [
    task("l-ls", f'List the data: {cmd("cd ~ && ls -l data")} Then read what it is: {cmd("cat data/README.md")}', auto="term:command line~README code=0"),
    task("l-head", f'Look at one read – four lines: a name, the bases, a plus sign, a quality for each base. {cmd("head -4 data/NA12878_R1.fastq")}', auto="term:command name=head code=0"),
    task("l-count", f'Count the reads of the first file: its lines, divided by four. {cmd("echo $(( $(wc -l < data/NA12878_R1.fastq) / 4 ))")}', auto="term:command line~wc code=0"),
    task("l-ref", f'The reference: which sequences does it have? {cmd("grep " + chr(39) + ">" + chr(39) + " data/reference.fa")}', auto="term:command name=grep code=0"),
])}

{q("l-q1", "How many read pairs are there? (The second file has the same number of reads: read 1 and read 2 of each pair.)",
   "<p><b>3,519</b> pairs – 14,076 lines in each file, four lines per read. Each read is 76 bases long.</p>",
   accept=RE_PAIRS, hint="count the lines of one file and divide by 4", placeholder="a number")}

{activity("Are the files what they should be?", [
    task("l-md5", f'A <b>checksum</b> is a fingerprint of a file’s contents: change one byte and the checksum changes. The <code>data</code> folder has a list of the expected checksums, <code>MD5SUMS</code>; check the files against it: {cmd("(cd ~/data && md5sum -c MD5SUMS)")} The brackets make the <code>cd</code> last for this one line only.', auto="term:command line~md5sum code=0"),
], "<p class='small muted'>Three times <code>OK</code>: these are exactly the files the practical was written for. You will use checksums again in chapter 4, to compare results.</p>")}

{activity("Quality control with fastp", [
    task("l-fastp", f'fastp measures the quality of the reads, removes poor reads and trims adapters. It writes the cleaned reads and two reports. {cmd(fastp)}', auto="term:command name=fastp code=0"),
    task("l-report", f'Open the report: {cmd("open fastp.html")} Read the <b>Summary</b>, then scroll to the quality curves: quality along the read, before and after filtering.', auto="editor:view name=fastp.html"),
    task("l-json", f'The same numbers, for programs to read, are in the JSON report. {cmd("jq .filtering_result fastp.json")} {cmd("jq .summary.before_filtering fastp.json")}', auto="term:command name=jq code=0"),
])}

{q("l-q2", "How many of the 7,038 reads passed fastp’s filter?",
   "<p><b>6,170</b> (87.7 %). 864 reads failed for low quality and 4 for too many unknown bases (N); none was too short. Adapters were trimmed from 42 reads.</p>",
   accept=RE_PASSED, hint="look for passed_filter_reads", placeholder="a number")}

{q("l-q3", "fastp removed 868 reads – about one in eight. Are these bad data? What in the report helps you decide?",
   "<p>Not bad, but not new either. Before filtering, 82 % of the bases have a quality of at least 30 (one error in 1,000) and 90 % of at least 20; the curves show quality falling towards the end of the reads, more so in read 2 – usual for Illumina reads of this age. Only 42 reads carried adapter sequence, and the duplication rate is about 7 %. Nothing here says the data cannot answer the question; it does say that a careful analysis might use the filtered reads, and that a result should not hang on a few low-quality bases.</p>")}

{activity("Which programs, which versions?", [
    task("l-versions", f'{cmd(versions)}', auto="term:command line~--version code=0"),
])}

{mcq("l-q4", "Why note the versions before any analysis is done?", [
    ("Because newer versions are always better, and you should know if you are behind.", False, "Newer is not the point – the point is to know exactly which one produced a result."),
    ("Because the same command can give a different result with another version – so a result is only described when the versions are.", True, "Yes: defaults, models and bug fixes change between versions. “bcftools” is not a method; “bcftools 1.10” is."),
    ("Because the AI needs them to answer.", False, "It helps the AI, but that is not why they belong in your notes."),
])}

{callout("concept", "What you now know – and an agent does not, until it looks", "<p>3,519 pairs of 76-base reads; a reference with two sequences, <code>human_CYP2C19</code> (30,000 bases) and <code>human_CYP2C9</code> (26,000 bases); about one read in eight of low quality; and the programs at hand: fastp 0.20.1, minimap2 2.22, Bowtie 2 2.4.2, samtools 1.17, bcftools 1.10. With that you can tell whether what an AI says about this data makes sense.</p>")}
'''
    return chapter("look", "1", "Look first", "terminal", "Look before you delegate", 20,
                   "You cannot judge an agent’s work on data you have never looked at. So, before any AI: what is in the files, are they intact, how good are the reads, which programs are here? A few commands of your own.", body)


def ch_assistant():
    p_map = ("I have paired-end Illumina reads in data/NA12878_R1.fastq and data/NA12878_R2.fastq, and a reference in data/reference.fa. "
             "Give me the commands to map the reads with minimap2 and to make a sorted, indexed BAM file called mapped.bam. Say in a few words what each option does.")
    p_call = ("Now give me the commands to call the variants from mapped.bam with bcftools into a compressed, indexed file variants.vcf.gz, "
              "and a command that shows me the line for position 11616 of human_CYP2C19.")
    p_count = "How many variants are there in my file variants.vcf.gz?"
    p_bwa = "Give me the bwa mem command to map these reads."
    body = f'''
{activity("Ask for the mapping", [
    task("a-ask", f'Make sure the terminal is in your home folder {show("cd ~", "cd ~")}, then give the assistant this prompt – read it first: what does it tell the assistant, and what does it leave open?{prompt(p_map)}Press <b>Send</b>.', auto="ai:answer tab=chat"),
    task("a-run", 'Read the answer. Under each block of commands is a button, <b>Put command … in the terminal</b>: it types one command for you. Read the command, press <kbd>Enter</kbd>, read what it prints – then the next one, until <code>mapped.bam</code> and its index are there.', auto="term:command name=samtools sub=index code=0", check="exists:mapped.bam.bai"),
    task("a-flagstat", f'Check the result yourself: {cmd("samtools flagstat mapped.bam")}', auto="term:command name=samtools sub=flagstat code=0"),
])}

{q("a-q1", "What percentage of the reads were mapped? (If the assistant gave you other options than <code>-ax sr</code>, your number may differ a little.)",
   "<p>With <code>minimap2 -ax sr</code>: <b>96.86 %</b> – 6,817 of 7,038 reads; 94.77 % as proper pairs.</p>",
   accept=RE_MAPPED, hint="the line with “mapped (”", placeholder="a percentage")}

{activity("Ask for the variants", [
    task("a-ask2", f'{prompt(p_call)}Send it, and run the commands as before, until <code>variants.vcf.gz</code> is there.', check="exists:variants.vcf.gz"),
    task("a-err", 'If a command fails, do not guess: under the error message in the terminal press <b>✦ Ask the AI assistant about this error</b>. The command and its message go to the assistant. (No error? Good – tick this step.)'),
    task("a-site", f'The line for the position should now be on your screen. If not: {cmd("bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz")}', auto="term:command line~11616 code=0"),
])}

{q("a-q2", "Which genotype does NA12878 have at position 11,616? Write it as it stands in the last column of the line (before the colon).",
   "<p><b>0/1</b> – heterozygous: one copy of the reference allele G and one of the alternative allele A. NA12878 carries one <i>CYP2C19*2</i> allele.</p>",
   accept=RE_GENOTYPE, hint="0 is the reference allele, 1 the alternative one", placeholder="for example 1/1")}

{q("a-q3", "Read the whole line. What is the evidence for this genotype?",
   "<p>With minimap2 and bcftools’ default settings: the reference base is G, the alternative A; the quality of the call (QUAL) is 222, about as high as bcftools goes; 106 reads cover the position (DP). <code>DP4=40,4,46,2</code> counts the good-quality reads for each allele, forward and reverse: 44 for G and 48 for A – about half and half, as expected when one of the two chromosomes carries the variant. <code>GT:PL 0/1:255,0,255</code>: the heterozygous genotype is far more likely than either homozygous one.</p>")}

{activity("Find the assistant’s limits", [
    task("a-count", f'{prompt(p_count)}What does it answer? Then find out yourself: {cmd("bcftools view -H variants.vcf.gz | wc -l")}', auto="term:command line~wc code=0"),
    task("a-bwa", f'{prompt(p_bwa)}What does it say?', auto="ai:ask text~bwa"),
])}

{callout("info", "Why this assistant knows that bwa is not here", "<p>Before your first question, this page gave the model a description of the terminal: the programs and their versions, the data files, what is not installed. Such a text is called a <b>system prompt</b>; with every question the page also sends the name of your folder and of your files. A chatbot in another browser tab knows none of this. It would most likely give you a <code>bwa mem</code> command – correct in general, and useless here.</p>")}

{q("a-q4", "Did the assistant tell you how many variants there are? What can it know about your file, and what not?",
   "<p>It knows the file’s <i>name</i> (sent with your question) and how such files are made. It cannot open the file, and it did not see what your commands printed – unless you pasted that in. So the honest answer is “I cannot see it; run this command”, and the right number is the one you counted: 60 with <code>minimap2 -ax sr</code> and bcftools’ defaults. If an assistant gives a number anyway, it has made one up that looks right. That is what people call a hallucination, and it is why a number from an AI is worth nothing until you have seen the output it comes from.</p>")}

{mcq("a-q5", "Who did the analysis in this chapter?", [
    ("The AI: it wrote every command.", False, "It wrote them. But it ran nothing, saw no result and checked nothing."),
    ("You: the assistant wrote text; you ran the commands, read the results and decided what to believe.", True, "Yes. With an assistant, you are the loop: copy, run, read, ask again. And you answer for the result."),
    ("Nobody – the programs did.", False, "Programs run what they are given. Someone chose the commands and judged the output."),
])}
'''
    return chapter("assistant", "2", "The assistant", "assistant", "The assistant answers – you act", 20,
                   "An AI assistant is a language model that writes text; here, commands. It runs nothing, and it sees nothing of your files unless you show it. You are the one who acts – and the one who checks.", body)


def ch_agent():
    body = f'''
<p>An agent does what you did in the last chapter – run a command, read what it prints, decide what comes next – by itself. The page runs each of its commands in <i>your</i> terminal, in a folder of its own ({c("~/runs/1-approve")}, {c("~/runs/2-plan")} …) that starts with a copy of the data. While it works the terminal is locked; switch to the <b>Terminal</b> tab to watch.</p>
<p>How much an agent may do without asking is a setting. There are four settings here. You will give the <b>same task</b> with each of them – with one of them twice, so five runs in all:</p>
{prompt(TASK, tab="agent", title="The task – the same for all five runs", button="Put it in the agent’s box")}

<h2 id="g-ask">1 · Approve each step</h2>
{activity("The agent proposes, you decide", [
    task("g-ask-send", f'In the AI tab choose <b>Agent</b> and <b>Approve each step</b>, put the task in the box <button class="do ask" type="button" data-prompt="{esc(TASK)}" data-tab="agent" data-mode="ask">do it for me</button> and press <b>Send</b>.', auto="agent:start mode=ask"),
    task("g-ask-run", 'For every step, read what the agent wants to run <b>before</b> you allow it. Would you have done the same? Press <b>Run it</b> if so. (For a step that only writes a file the button reads <b>Write it</b>.)', auto="agent:approve choice=run || agent:approve choice=all"),
    task("g-ask-change", 'At least once, do not just agree. Change the command in its box before you press <b>Run it</b> – or press <b>Refuse</b>, with your reason in the line for the agent. The agent is told what you did; watch how it reacts.', auto="agent:approve choice=edited || agent:approve choice=refused"),
    task("g-ask-done", 'Go on until the agent writes its report. (Tired of approving? <b>Run, and stop asking</b> lets it finish alone – many people press that button rather soon. If you do, remember at which step.)', check="runs:ask:1"),
    task("g-ask-check", f'Now check the report against the file. On the run’s card press <b>Go to its folder</b>, then <kbd>Enter</kbd> – the prompt of the terminal now shows the run’s folder, <code>~/runs/1-approve</code>. Then: {cmd("bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz")}', auto="term:command line~11616 code=0 cwd~/runs/"),
])}

{q("g-q1", "Compare the agent’s report with the line you just printed. Is every statement in the report backed by something a command printed? Is there anything you cannot find in the outputs?",
   "<p>The genotype (0/1), the quality and the read counts should match the line exactly, if the agent printed that line and read it. Look for the rest in the record (<b>The record (RUN.md)</b> on the card): how many reads mapped, how many variants. Statements that no command printed – “high confidence”, “a poor metaboliser”, a clinical recommendation – come from what the model knows in general, not from this analysis. They may be right (they often are), but nothing in this run shows it. And a carrier of one *2 allele is usually called an intermediate metaboliser, not a poor one: exactly the kind of detail to check.</p>")}

{mcq("g-q2", "What does approving each step guarantee?", [
    ("That nothing runs that you have not seen.", True, "Yes – and only that. It protects your files from a command you would not have allowed."),
    ("That the commands are the right ones for the question.", False, "Only if you can tell – the approval is as good as the person approving."),
    ("That the report at the end is true.", False, "The report is written after the last step, and nobody approves it."),
    ("That the analysis can be repeated.", False, "Nothing about approving makes it repeatable. That is chapter 4."),
])}

<h2 id="g-plan">2 · Plan first</h2>
{activity("Agree on the route, then let it drive", [
    task("g-plan-send", f'Choose <b>Plan first</b> and send the same task. <button class="do ask" type="button" data-prompt="{esc(TASK)}" data-tab="agent" data-mode="plan">do it for me</button> The agent answers with a plan and runs nothing yet.', auto="agent:start mode=plan"),
    task("g-plan-change", 'Read the plan as you would read a colleague’s. Then ask for one change – for example: <i>“Check the quality of the reads with fastp first, and map the filtered reads.”</i> or <i>“Use Bowtie 2 instead of minimap2.”</i> Press <b>Ask for changes</b>.', auto="agent:plan choice=change"),
    task("g-plan-ok", 'When the plan is what you want, press <b>Approve the plan</b>. From here the agent works alone.', auto="agent:plan choice=approve"),
    task("g-plan-record", 'When it has finished, open <b>The record (RUN.md)</b>. It has the plan, and under <i>What the agent did</i> every command. Did the agent do what it said it would?', auto="editor:open path~-plan/RUN.md"),
])}

{q("g-q3", "Did the agent keep to the plan? Where did it depart from it – and did it tell you?",
   "<p>Look for departures of these kinds: a command fails and is repaired; an extra check is added; an option or a file name is not what the plan said; a step is quietly dropped. A good agent says so in its report – but the report is the agent’s own account. The record shows what happened whether the agent mentions it or not. A plan is a promise; the record is what was done.</p>")}

<h2 id="g-auto">3 · Autonomous – twice</h2>
{activity("Let it run, and then let it run again", [
    task("g-auto-1", f'Choose <b>Autonomous</b> and send the same task. <button class="do ask" type="button" data-prompt="{esc(TASK)}" data-tab="agent" data-mode="auto">do it for me</button> Watch; you are not asked anything.', check="runs:auto:1"),
    task("g-auto-2", f'When it has finished, send <b>exactly the same task</b> again, again autonomous. <button class="do ask" type="button" data-prompt="{esc(TASK)}" data-tab="agent" data-mode="auto">do it for me</button>', check="runs:auto:2"),
    task("g-auto-cmp", f'You now have four runs of one task. Compare them. This line prints, for each run, the model that answered and the main commands that worked: {cmd(CMP_RUNS)} <span class="small muted">(<code>jq</code> reads <code>run.json</code> – the record of a run in a form for programs – and <code>grep</code> keeps the lines that start with one of the main programs. For everything a run did, open its <code>RUN.md</code>.)</span>', auto="term:command line~run.json"),
    task("g-auto-n", f'And this one prints the number of variants each run found, and what each found at the position: {cmd("cd ~/runs && for d in */; do echo " + chr(34) + "$d $(bcftools view -H $d/variants.vcf.gz | wc -l) variants, at 11616: $(bcftools query -f " + chr(39) + "%REF>%ALT QUAL=%QUAL [%GT]" + chr(39) + " -r human_CYP2C19:11616 $d/variants.vcf.gz)" + chr(34) + "; done")}', auto="term:command line~query"),
], "<p class='small muted'>Error messages and <code>0 variants</code>: the run has no <code>variants.vcf.gz</code>. Error messages and a number, but nothing after <code>at 11616:</code> – the file has no index (<code>bcftools index</code>). Both are results worth noticing.</p>")}

{q("g-q4", "Same task, same data – and, if the <i>model:</i> lines agree, the same model. Were your runs the same? List the differences that could change the result.",
   "<p>Most likely not – compare with your neighbours, too. A model need not give the same answer twice, and the task leaves choices open: which mapper (minimap2 or Bowtie 2); the raw reads or the reads filtered by fastp; default settings or others; a filter on the variants or none; which checks. (When a model is busy or over its limit the page asks another one, so even the model can differ between your runs – the <i>model:</i> lines show it.) Those choices change the list of variants: with default settings minimap2 and bcftools give <b>60</b> variants (27 of them with QUAL of 30 or more), Bowtie 2 and bcftools <b>50</b>; after fastp it is 60 and 49. The answer to <i>your question</i> should be the same in all of them – G&gt;A, 0/1, with QUAL 222 from minimap2 alignments and 178 from Bowtie 2’s – because that position is well covered. A result that survives different reasonable analyses is a robust one; but you only know that because you compared. And if your runs happened to be identical: nothing guaranteed it.</p>")}

{mcq("g-q5", "A methods section says: “Variants were called by an AI agent (model X), given the prompt ‘Find the variants of sample NA12878 …’.” Is the analysis described?", [
    ("Yes: model and prompt are given, so anyone can repeat it.", False, "You gave the same prompt several times. Did you get the same commands each time – and could you have known beforehand?"),
    ("No: the same prompt can lead to different commands each time. The analysis is the commands, options and versions that were actually run.", True, "Yes. The prompt is worth reporting – but it describes what was asked, not what was done."),
    ("No, because AI must not be used for analysis.", False, "It may, in many places – if you say so, and can show and check what was done."),
])}

<h2 id="g-script">4 · Write a script</h2>
{activity("Ask for the analysis, not for the answer", [
    task("g-script-send", f'Choose <b>Write a script</b> and send the same task once more. <button class="do ask" type="button" data-prompt="{esc(TASK)}" data-tab="agent" data-mode="script">do it for me</button> The agent is now asked to write one script, <code>analysis.sh</code>, to run it, and to repair it until it works.', check="runs:script:1"),
    task("g-script-read", 'Open <code>analysis.sh</code>: press <b>Open</b> next to its name on the run’s card (or find it in the <b>Files</b> tab under <code>runs</code>). Read it from top to bottom. Can you follow every step?', auto="editor:open name=analysis.sh"),
])}

{q("g-q6", "Name one thing in <code>analysis.sh</code> that you would change or check before you used it on other data.",
   "<p>Whatever you found – for example: file and sample names written into the commands, so that the script works for this sample only; a threshold (a minimum quality, a depth) that the agent chose without giving a reason; no test that the input files exist or that a step produced something; nothing that records the versions of the programs; an option you do not know and would look up with <code>--help</code>. The point of a script is that you <i>can</i> read and question all of this – a chat that ended with “the genotype is 0/1” gives you nothing to question.</p>")}

<h2 id="g-table">The four ways, side by side</h2>
<table class="table compare">
<tr><th></th><th>Who decides each step</th><th>What you must do</th><th>Use it when</th></tr>
<tr><th>Approve each step</th><td>You, one step at a time</td><td>Read every command before it runs</td><td>the tools or the data are new to you; a command could destroy something</td></tr>
<tr><th>Plan first</th><td>You approve the route; the agent drives</td><td>Judge the plan; afterwards check that it was kept</td><td>the approach matters more than each single command</td></tr>
<tr><th>Autonomous</th><td>The agent</td><td>Check afterwards: the record and the results</td><td>routine work in a place where nothing can be damaged, and checking is cheap</td></tr>
<tr><th>Write a script</th><td>The agent writes; the script does</td><td>Read the script; run it again</td><td>you will repeat, share or publish the analysis</td></tr>
</table>

{callout("warn", "Outside this page", "<p>Agent tools for the command line and for code editors have the same settings under other names: ask before each command, plan mode, run without asking. The difference is where they run. Here the agent works in a web page, in a folder of its own; what it changes anywhere else is put back. On your laptop or on a cluster an autonomous agent can delete or overwrite real data, and it will not always notice. So: keep raw data read-only, work in a copy or a container, keep your work under version control – and do not give an agent more access than the task needs.</p>")}
'''
    return chapter("agent", "3", "The agent", "assistant", "Agents: four ways to let an AI act", 45,
                   "An agent runs the commands itself. That saves you the typing – and takes away the moments in which you would have looked. How much you still see and decide depends on how you let it work.", body)


README_TEMPLATE = """# CYP2C19*2 in NA12878

## Question
Which genotype does the sample NA12878 have at CYP2C19*2
(rs4244285; position 11,616 of the sequence human_CYP2C19)?

## Answer
Genotype:  ...
Evidence:  QUAL ..., ... reads at the position, ... support G and ... support A
           (bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz)

## How to repeat the analysis
In a folder with data/ and rerun.sh:   bash rerun.sh
The same result is:   bcftools view -H variants.vcf.gz | md5sum   ->   ...
(The .vcf.gz file itself differs from run to run: its header holds the date.)

## Data (md5)
d2b8ddb488975fa5ef18e6e59edb5681  data/NA12878_R1.fastq
aee82e1b82bedb037208f5ff5b9ff34b  data/NA12878_R2.fastq
d9155e00b786f74b0837f6a675483563  data/reference.fa

## Programs
...   (copy the list from RUN.md)
WebAssembly builds, run in a web browser.

## Use of AI
Tool:            the AI agent of the practical "AI agents for bioinformatics"
Model and date:  ...
What the AI did: chose and ran the commands (see RUN.md, which the page wrote, not the AI)
What I did:      ...   (for example: read every command; took out ...; ran the
                 script twice in new folders; compared the variants; read the
                 line for position 11,616 myself)
"""


def ch_repro():
    cmp_all = 'for d in ~/check1 ~/check2 ~/runs/*; do echo "$(bcftools view -H $d/variants.vcf.gz | md5sum) $d"; done'
    body = f'''
<p>Three things make an analysis repeatable: the <b>data</b> (and a way to know it is the same data), the <b>commands</b> (as a script, not as a memory), and the <b>programs</b> (with their versions). The agent’s runs have left you all three – in pieces. Now you put them together and test them.</p>

{activity("The record: what was done", [
    task("r-record", 'Choose the run you trust most. In the AI tab, on its card, press <b>The record (RUN.md)</b>. Find: the task as you gave it; the model; each command with its exit status; the programs and versions; the checksums of the input files.', auto="editor:open name=RUN.md"),
])}

{q("r-q1", "What does RUN.md tell you that the agent’s report did not? And who wrote it?",
   "<p>Every command, also the ones that failed, with exit status and the end of what it printed; what you approved, changed or refused; the versions of the programs; the checksums of inputs and results; the model and the time. The report is the agent’s summary of its own work, and a summary leaves things out. RUN.md was written by the page, from what really ran – the agent cannot improve on it. Agent tools on your own computer keep such logs too (session transcripts). Keep them with the results: they are your lab notebook for work you did not do by hand.</p>")}

{activity("From the record to a script", [
    task("r-script", 'On the same card press <b>Make a script from this run</b>. The page writes <code>rerun.sh</code>: the commands that worked, in the order they ran. A command that failed and left nothing behind is there as a comment – and so is any command that reached outside the run’s folder. A command that ended with an error status but did write a file is kept (<code>diff</code> ends with status 1 when two files differ: no mistake, and the next step may read its output). (A <i>Write a script</i> run has its script already, <code>analysis.sh</code>, and no such button: open that one, and tick this step yourself. If the agent did not write it, the card says so – and has the button.)', auto="agent:script"),
    task("r-tidy", 'Read the script. Take out what only looked at things (<code>ls</code>, <code>head</code>, <code>cat</code> …) and is not needed to make the result. Leave the comments that say what a step is for – or write better ones. Where the agent named its folder in full (<code>/home/student/runs/…</code>), the page has written <code>"$RUN_FOLDER"</code>: the folder the script runs in, set near the top. A line that begins with <code># left out</code> says why a command of the run is not in the script; a line that begins with <code># CHECK:</code> stands above a command that the page kept but could not check – read those first. The script stops at the first command that fails and at a variable that has no value (<code>set -eu</code>); the agent’s own commands ran without that. Where its run went on all the same – a <code>grep</code> that finds nothing inside a loop, a variable that was never set – the page has put <code>set +e</code> or <code>set +u</code> before the command, with the reason, and switched it on again after it: decide whether the analysis should go on there. A command that ended the way a script ends – an <code>exit</code> inside it, the agent’s own <code>set -e</code> – stands in a subshell, <code>( … )</code>, so that it ends alone, as it did in the run; the lines above it say so. Check, too, that no command reaches outside its folder (a path that starts with <code>~</code>, <code>/</code> or <code>..</code>, or a <code>cd</code> that leaves the folder): in the agent’s run the page put such changes back; when you run the script, nothing does. Save with <kbd>Ctrl</kbd>+<kbd>S</kbd>.', auto="editor:save"),
])}

{activity("Does it repeat?", [
    task("r-run1", f'A script that works in the folder where everything already exists proves little. Test it in a new folder that has only the data – a fresh copy of the course data, not the files the agent has worked with – and the script. On the run’s card press <b>Go to its folder</b> and <kbd>Enter</kbd>; then: {cmd("mkdir -p ~/check1 && cp -rf ~/data rerun.sh RUN.md ~/check1/ && cd ~/check1 && bash rerun.sh")}<details class="alt"><summary>For a <i>Write a script</i> run</summary>Its script is called <code>analysis.sh</code>. This line copies it under the name <code>rerun.sh</code>, so that everything below is the same for you: {cmd("mkdir -p ~/check1 && cp -rf ~/data RUN.md ~/check1/ && cp -f analysis.sh ~/check1/rerun.sh && cd ~/check1 && bash rerun.sh")}</details>', auto="script:done code=0 path~/check1/"),
    task("r-fix", f'If the script stopped with an error: read the message, repair the script ({c("nano rerun.sh")}) and run it again with {c("bash rerun.sh")} – or ask the Chat. To start afresh instead, remove the test folder ({c("cd ~ && rm -rf ~/check1")}), go to the run’s folder again and repeat the line above.', auto="script:done code=0 path~/check1/"),
    task("r-run2", f'Once more, in a second new folder: {cmd("mkdir -p ~/check2 && cp -rf ~/data ~/check1/rerun.sh ~/check2/ && cd ~/check2 && bash rerun.sh")}', check="exists:check2/variants.vcf.gz"),
    task("r-md5", f'Are the two results the same file? {cmd("md5sum ~/check1/variants.vcf.gz ~/check2/variants.vcf.gz")}', auto="term:command name=md5sum code=0"),
    task("r-diff", f'Not the same! Find the difference: unpack both and compare them line by line. {cmd("zcat ~/check1/variants.vcf.gz > ~/v1.vcf; zcat ~/check2/variants.vcf.gz > ~/v2.vcf; diff ~/v1.vcf ~/v2.vcf")}', auto="term:command line~diff"),
    task("r-same", f'Now compare what matters – the variants, without the header – for both test folders and for all the agent’s runs: {cmd(cmp_all)}', auto="term:command line~md5sum line~bcftools"),
])}

{q("r-q2", "Which line differs between the two files, and why?",
   "<p>A line of the header: <code>##bcftools_callCommand=call …; Date=…</code>. bcftools writes into the file when it was run. (If your script filters or converts the file with bcftools, there are more such lines.) One changed character gives another checksum, so two <code>.vcf.gz</code> files made at different times are not identical – although every variant in them is.</p>")}

{q("r-q3", "So: did the script give “the same result” twice? What do you compare to decide – and what did the last command show about the agent’s runs?",
   "<p>Yes: the variant lines (<code>bcftools view -H</code>) have the same checksum in <code>check1</code> and <code>check2</code> – and the same as the run the script was made from. “Reproducible” needs a definition: here, the same variants with the same genotypes and qualities, not the same bytes in a file that holds a date. Say which you mean, and give the checksum of the thing you compare. The other runs of the agent show other checksums wherever the agent chose other commands: identical checksums mean the same variant list; different ones, a different list.</p>")}

{activity("Say what was done – the AI included", [
    task("r-readme", f'A folder that someone else can use needs a note. Create this file in <code>~/check1</code> and fill in every <code>...</code> – from RUN.md and from what you did yourself.{codefile("~/check1/README.md", README_TEMPLATE)}', auto="file:create name=README.md"),
    task("r-fill", 'Fill it in and save. Under <b>Use of AI</b>, be exact about who did what: it protects you, and it tells the reader what was checked by a person.', check=README_FILLED),
    task("r-zip", 'Download the folder: data, script, record, results, note. <button class="do" type="button" data-download="~/check1|cyp2c19-na12878.zip">Download ~/check1 as a .zip</button> That file is your analysis.', auto="project:download root~/check1"),
])}

{q("r-q4", "A colleague opens your .zip two years from now. The model you used no longer exists. What can they still do – and what not?",
   "<p>They can read what was asked and what was done (RUN.md), check that the data is the same (the checksums), run <code>rerun.sh</code> with the same versions of the programs and get the same variants, and read which parts a person checked. (With minimap2 the checksum in your README comes out the same on another computer. Bowtie 2 places a few reads that fit two places equally well by a pseudo-random number, which can differ between computers: there, compare positions and genotypes.) They cannot have the same conversation with the agent again – and might not get the same commands if they could. That no longer matters: the analysis does not depend on the model any more. What it does depend on is the programs, and old versions are not always easy to get. That is why they are written down; in real projects an environment file or a container fixes them.</p>")}

{mcq("r-q5", "Which sentence belongs in the methods of a report?", [
    ("“The data was analysed by an AI agent.”", False, "This says who, not what. Nobody could repeat or check it."),
    ("“We asked the model: ‘Find the variants of sample NA12878 …’”", False, "The prompt alone does not define the analysis – the same prompt can lead to other commands each time. Compare your runs."),
    ("“Reads were mapped with minimap2 2.22 (-ax sr) and variants called with bcftools 1.10 (mpileup, call -mv). The commands were written by an AI agent (model, date) and checked by the authors; the script and the record of the agent’s run are in the supplement.”", True, "Yes: what was done, with what; what the AI did; what people checked; and where to find the evidence."),
    ("The same as before AI existed – how the commands were written is nobody’s business.", False, "Journals, universities and funders increasingly ask for a statement on the use of AI. Leaving it out can count as misconduct – check your course’s rules."),
])}

<div class="export-row"><label class="name-field">Your name (for the file of answers): <input type="text" data-student-name placeholder="optional"></label><button class="btn primary" type="button" data-export-answers>Download my answers</button></div>
'''
    return chapter("repro", "4", "Make it repeatable", "terminal", "Make it reproducible", 25,
                   "The model that did your analysis will be replaced before long, and it might not write the same commands twice anyway. What can be kept is what was done: the data, the commands, the versions. This chapter turns one of your runs into an analysis that anyone can run again – and tests whether it really gives the same result.", body)


def ch_ref():
    body = f'''
<h2 id="x-check">Before you believe an agent</h2>
<ul class="check-list">
<li>Do I know the data well enough to notice a wrong answer? (chapter 1)</li>
<li>Is each statement in the report backed by something a command printed?</li>
<li>Have I looked at the result myself – the line, the count, the file – and not only at the report?</li>
<li>Do I know what the agent decided for me: the program, the options, the filters?</li>
<li>Is there a record of what was run, written by the tool and not by the model?</li>
<li>Is there a script, and have I run it somewhere fresh?</li>
<li>Have I said what the AI did and what I checked?</li>
</ul>

<h2 id="x-cmd">Commands of this practical</h2>
<table class="table">
<tr><td>{c("fastp -i R1.fastq -I R2.fastq -o out1.fastq -O out2.fastq -h fastp.html -j fastp.json")}</td><td>quality control and filtering of paired reads</td></tr>
<tr><td>{c("minimap2 -ax sr ref.fa R1.fastq R2.fastq > mapped.sam")}</td><td>map short paired reads</td></tr>
<tr><td>{c("bowtie2-build ref.fa ref")} · {c("bowtie2 -x ref -1 R1.fastq -2 R2.fastq -S mapped.sam")}</td><td>the same with Bowtie 2: index first, then map</td></tr>
<tr><td>{c("samtools sort -o mapped.bam mapped.sam")} · {c("samtools index mapped.bam")}</td><td>sort and index the alignments</td></tr>
<tr><td>{c("samtools flagstat mapped.bam")}</td><td>how many reads mapped</td></tr>
<tr><td>{c("bcftools mpileup -f ref.fa mapped.bam | bcftools call -mv -Oz -o variants.vcf.gz")}</td><td>call variants</td></tr>
<tr><td>{c("bcftools index variants.vcf.gz")}</td><td>index the variants (needed for {c("-r")})</td></tr>
<tr><td>{c("bcftools view -H -r human_CYP2C19:11616 variants.vcf.gz")}</td><td>the line for one position</td></tr>
<tr><td>{c("bcftools view -H variants.vcf.gz | wc -l")}</td><td>count the variants</td></tr>
<tr><td>{c("bcftools view -H variants.vcf.gz | md5sum")}</td><td>a checksum of the variants, without the header</td></tr>
<tr><td>{c("md5sum -c MD5SUMS")}</td><td>check files against a list of checksums</td></tr>
<tr><td>{c("bash script.sh")}</td><td>run a script; {c("set -euo pipefail")} at its top stops it at the first error</td></tr>
</table>
<p class="small">Every program explains itself: {c("samtools --help")}, {c("samtools view --help")}, {c("bcftools call --help")}, {c("fastp --help")}. (Some commands of samtools and bcftools print their help and then end with an error status, as they do on Linux – the help is there all the same. One, <code>bcftools mpileup</code>, shows its help only when it is typed with nothing after it.) {c("help")} lists what the terminal has.</p>

<h2 id="x-words">Words</h2>
<table class="table">
<tr><th>Language model</th><td>A program that continues text. Asked a question, it writes a likely answer – from what it was trained on and from what is in front of it.</td></tr>
<tr><th>Assistant</th><td>A language model you talk to. It writes; you act.</td></tr>
<tr><th>Agent</th><td>A language model in a loop with tools – here it can run commands in the terminal and write text files. It acts, reads the result and acts again, until it decides it is done.</td></tr>
<tr><th>Prompt</th><td>The text the model is given. The <b>system prompt</b> is the part you do not see: what the tool told the model about its job and its surroundings.</td></tr>
<tr><th>Context</th><td>Everything the model can “see” at one moment: system prompt, your messages, its own earlier replies, outputs of commands. What is not in the context does not exist for the model.</td></tr>
<tr><th>Hallucination</th><td>Text that looks right and is not backed by anything: an invented number, option, file or reference.</td></tr>
<tr><th>Non-deterministic</th><td>The same prompt need not give the same answer twice.</td></tr>
<tr><th>Provenance</th><td>Where a result comes from: which data, which commands, which programs, who or what ran them.</td></tr>
<tr><th>Reproducible</th><td>Someone else, with the same data and the same instructions, gets the same result.</td></tr>
</table>

<h2 id="x-ai">A statement on the use of AI</h2>
<p>Rules differ between courses, journals and employers – read yours. A useful statement answers four questions:</p>
<table class="table">
<tr><th>Which tool and model, and when?</th><td>for example: the agent of this practical; the model’s name as it stands in RUN.md; the date</td></tr>
<tr><th>What did the AI do?</th><td>for example: chose and ran the commands for mapping and variant calling</td></tr>
<tr><th>What did I do?</th><td>for example: set the task; read each command; ran the script again in a new folder; checked the genotype in the VCF file myself</td></tr>
<tr><th>Where is the evidence?</th><td>for example: RUN.md (the record of the run), rerun.sh (the script)</td></tr>
</table>
<p class="small">The note you wrote in chapter 4 (<code>README.md</code>, <i>Use of AI</i>) is such a statement.</p>

<h2 id="x-trouble">If something does not work</h2>
<table class="table">
<tr><th>“Too many requests” (429)</th><td>Every model that the page can ask is over its limit per minute. The agent waits (up to a minute and a half, three times at most) and goes on by itself; in the chat, wait a minute. If an agent’s run ends with this message, many people may be using the same key: give the task again a little later.</td></tr>
<tr><th>“No requests are left for today”</th><td>Every model is over its limit per day for your key; the message says when the service takes requests again. Waiting does not help today, and a second key from the same Google project does not either (the limits are counted per project): work with a neighbour, or ask for another key.</td></tr>
<tr><th>“Busy”, “high demand” (503)</th><td>The service is overloaded. The page asks other models by itself and names the one that answered. If a run ends with this message, every model was busy: wait a few minutes and give the task again.</td></tr>
<tr><th>“… sent an empty reply”</th><td>A model sometimes ends a reply before it has begun. In the chat, ask again; the agent asks again by itself.</td></tr>
<tr><th>The key is not accepted</th><td>Copy it again, without spaces, and check that the service chosen in the form is the one the key belongs to. An old Gemini key may no longer be accepted by Google: make a new one.</td></tr>
<tr><th>A command never ends</th><td>Press <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal; press it again to stop the program by force. The programs then start again. A file that a program wrote in the last seconds before may be lost, or come back as it was before – the terminal says which: make it again.</td></tr>
<tr><th>The agent goes in circles</th><td>Press <b>Stop</b>. Its folder and the record stay. Start a new run, and say in the task what it should avoid.</td></tr>
<tr><th>The page was reloaded</th><td>Your ticks, answers and files are still there. (A file that a program wrote in the last seconds before is not: the terminal names it.) An agent that was running cannot go on, and that run has no record – its folder holds a note instead: give the task again.</td></tr>
<tr><th>“Your browser storage is full”</th><td>The browser gives a site only a few megabytes for text files, and other practicals of the same site share them. Keep what you have with <b>My answers → Save all my work to a file</b>; then make room: remove large text files you do not need (a SAM file, say: {c("rm mapped.sam")}), or use <b>Start again</b> in a practical that you have finished.</td></tr>
<tr><th>“This practical is open in another tab or window”</th><td>Work in one tab or window only. Two of them save to the same place, and each writes over what the other has saved. Close one.</td></tr>
<tr><th>Start from scratch</th><td><b>My answers → Start again</b> clears everything in this browser.</td></tr>
</table>

<h2 id="x-data">The data</h2>
<p>3,519 pairs of 76-base Illumina reads of the public reference sample NA12878 (exome sequencing, run SRR098401 of the 1000 Genomes Project), from the regions of <i>CYP2C19</i> and <i>CYP2C9</i>; and two pieces of the human reference genome hg19. Details: {cmd("cat ~/data/README.md")}</p>
'''
    return chapter("ref", "R", "Reference", "terminal", "Reference", 0,
                   "A checklist, the commands, the words, and what to do when something does not work.", body)


def ALL():
    return [ch_start(), ch_look(), ch_assistant(), ch_agent(), ch_repro(), ch_ref()]
