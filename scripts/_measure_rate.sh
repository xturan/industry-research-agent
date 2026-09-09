#!/usr/bin/env bash
a=$(du -sb ~/.cache/pip 2>/dev/null | cut -f1)
sleep 30
b=$(du -sb ~/.cache/pip 2>/dev/null | cut -f1)
echo "delta_MB: $(( (b - a) / 1048576 ))"
python3 -c "print('rate_MBps:', round(($b - $a) / 1048576 / 30, 2))"
ps aux | grep 'pip install' | grep -v grep | awk '{print "cpu%:", $3, "mem%:", $4}'
