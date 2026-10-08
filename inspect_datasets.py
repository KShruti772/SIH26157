from pathlib import Path
import pandas as pd


BASE = Path("data/public")


def inspect_csv(path, sample_rows=5):
    print("\n" + "=" * 80)
    print(f"FILE: {path}")
    print("=" * 80)

    # Read only a small sample first
    df = pd.read_csv(path, nrows=sample_rows)

    print("\nColumns:")
    for i, column in enumerate(df.columns, start=1):
        print(f"{i:2}. {column}")

    print("\nData types:")
    print(df.dtypes)

    print("\nSample:")
    print(df.to_string(index=False))


files = [
    BASE / "salad" / "salad_train.txt",
    BASE / "salad" / "salad_val.txt",
    BASE / "salad" / "salad_test.txt",
    BASE / "salad" / "salad_train.csv",
    BASE / "salad" / "salad_val.csv",
    BASE / "salad" / "salad_test.csv",
    BASE / "ai_soc" / "soc_alerts.csv",
    BASE / "ai_soc" / "assets.csv",
    BASE / "ai_soc" / "analyst_feedback.csv",
    BASE / "ai_soc" / "cti_indicators.csv",
]


for file in files:
    if file.exists():
        inspect_csv(file)
    else:
        print(f"\nNOT FOUND (or excluded from git): {file}")