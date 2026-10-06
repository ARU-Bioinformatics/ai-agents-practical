#!/usr/bin/env bash
# Runs the tests of the practical, one after the other (each starts its own web server and browser).
#   bash run_all.sh              all of them (about 15 minutes)
#   bash run_all.sh lang agent   only these
# Logs: out/NAME.log   Summary: out/all.log
cd "$(dirname "$0")"
mkdir -p out
tests=("$@")
[ ${#tests[@]} -eq 0 ] && tests=(lang files parse typical typical2 partial tools threads guard facts store agent rerun walk ui)
: > out/all.log
for t in "${tests[@]}"; do
  start=$(date +%s)
  timeout 2400 python3 -u "t_$t.py" > "out/$t.log" 2>&1
  rc=$?
  echo "$t: exit $rc, $(( $(date +%s) - start )) s — $(grep -E '^(ALL OK|FAILED|[0-9]+ BAD of|[0-9]+ of [0-9]+ passed)' "out/$t.log" | tail -1)" | tee -a out/all.log
done
echo "finished" >> out/all.log
