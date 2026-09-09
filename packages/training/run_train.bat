@echo off
cd /d E:\invest_agent
set PYTHONIOENCODING=utf-8
python -m packages.training.train_source_tier --epochs 3 --batch 2 --grad-accum 8
