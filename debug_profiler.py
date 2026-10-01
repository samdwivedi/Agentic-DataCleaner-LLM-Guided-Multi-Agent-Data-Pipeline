import pandas as pd
import numpy as np

rng = np.random.default_rng(7)
names = [f"person_{i}" for i in range(80)]
df = pd.DataFrame({"name": names})

non_null = df["name"].dropna()
try:
    str_series = non_null.astype(str)
    lengths = str_series.str.len()
    avg_len = round(float(lengths.mean()), 4)
    max_len = int(lengths.max())
    min_len = int(lengths.min())
    print("Success:")
    print("avg_len:", avg_len)
    print("max_len:", max_len)
    print("min_len:", min_len)
except Exception as e:
    print("Exception!")
    import traceback
    traceback.print_exc()
