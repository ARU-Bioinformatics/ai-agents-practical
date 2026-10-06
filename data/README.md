# The data: NA12878 reads around CYP2C19 and CYP2C9

Read-only. The AI agent gets its own copies; never change these.

| File | What it is |
| --- | --- |
| `NA12878_R1.fastq`, `NA12878_R2.fastq` | 3,519 pairs of real 76-base Illumina exome reads from sample **NA12878** (run SRR098401, 1000 Genomes Project), from two regions of chromosome 10 |
| `reference.fa` | the reference: two slices of the human genome (UCSC hg19) – `human_CYP2C19` = chr10:96,530,001–96,560,000 and `human_CYP2C9` = chr10:96,699,001–96,725,000 |
| `MD5SUMS` | checksums of the three files: `md5sum -c MD5SUMS` (in this folder) checks that they are unchanged |
| `provenance.json` | where the data came from and how it was extracted (addresses, hashes, counts, limitations) |

Positions in results made with this reference are relative to the slices: add
96,530,000 to a position on `human_CYP2C19`, or 96,699,000 on `human_CYP2C9`,
to get the GRCh37/hg19 chromosome 10 coordinate. The variant *CYP2C19\*2*
(rs4244285, hg19 chr10:96,541,616) is at position **11,616** of `human_CYP2C19`.

The reads were reconstructed from the public 1000 Genomes exome alignment of
NA12878 (both mates of every pair that overlaps the two regions; nothing was
simulated or filtered by variant). The qualities are the recalibrated values
stored in that alignment. NA12878 is the widely used public reference sample
(Coriell cell line GM12878); no patient data is part of this practical.
This is exome data, so depth varies a lot, and there is no truth set: two
analyses that agree show that they agree, not that they are right.
