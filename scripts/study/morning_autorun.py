#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path('/Users/ming/projects/MOCA')
DAILY = ROOT / 'study_plan/portfolio/daily'
CONFIG = DAILY / 'automation_config.json'
WRAPPER_MARKERS = DAILY / '.autorun_markers'


@dataclass(frozen=True)
class Job:
    name: str
    script: Path
    args: list[str]


JOBS = {
    'reminders-sync': Job('reminders-sync', ROOT / 'scripts/study/reminders_sync.py', ['--day', 'auto', '--sequential', '--write']),
    'calendar-sync': Job('calendar-sync', ROOT / 'scripts/study/calendar_sync.py', ['--day', 'auto', '--write']),
    'audit-day': Job('audit-day', ROOT / 'scripts/study/audit_day.py', ['--day', 'auto', '--codex']),
    'plan-next-day': Job('plan-next-day', ROOT / 'scripts/study/start_day.py', ['--day', 'auto', '--codex']),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run study automation once after wake/login, with per-day idempotent markers.')
    parser.add_argument('job', choices=sorted(JOBS))
    parser.add_argument('--date', default=None, help='Run date YYYY-MM-DD, default today')
    return parser.parse_args()


def resolve_day(run_date: date) -> int:
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    start = date.fromisoformat(config['program_start_date'])
    day = (run_date - start).days + 1
    if day < 1:
        raise SystemExit(f'{run_date.isoformat()} is before program_start_date {start.isoformat()}')
    return min(day, 30)


def marker_for(job: Job, day: int) -> Path:
    return WRAPPER_MARKERS / f'day{day:02d}_{job.name}.done'


def run_job(job: Job, run_date: date, day: int) -> int:
    marker = marker_for(job, day)
    if marker.exists():
        print(f'{job.name}: already done for day {day:02d} ({run_date.isoformat()}), skip')
        return 0
    args = list(job.args)
    if job.name == 'plan-next-day':
        args.extend(['--date', run_date.isoformat()])
    cmd = ['/opt/homebrew/bin/python3', str(job.script), *args]
    result = subprocess.run(cmd, cwd=str(ROOT), text=True)
    if result.returncode == 0:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f'{job.name} done for day {day:02d} ({run_date.isoformat()})\n', encoding='utf-8')
    if result.returncode == 0 and job.name == 'audit-day':
        tomorrow = run_date + timedelta(days=1)
        tomorrow_day = resolve_day(tomorrow)
        return run_job(JOBS['plan-next-day'], tomorrow, tomorrow_day)
    return result.returncode


def main() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.date) if args.date else date.today()
    day = resolve_day(run_date)
    return run_job(JOBS[args.job], run_date, day)


if __name__ == '__main__':
    raise SystemExit(main())
