"""Repeat existing bounded engineering probes without overwriting historical evidence."""
import argparse
from pathlib import Path
from validation.cg1 import resources

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    resources.BASE=args.out
    resources.main()
