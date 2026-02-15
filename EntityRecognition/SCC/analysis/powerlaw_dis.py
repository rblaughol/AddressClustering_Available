import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

############################################
# Global font / style (MAKE FONTS BIGGER)
############################################
plt.rcParams.update({
    "font.size": 18,          # base font
    "axes.titlesize": 20,
    "axes.labelsize": 19,
    "xtick.labelsize": 17,
    "ytick.labelsize": 17,
    "legend.fontsize": 17
})

############################################
# Path config
############################################
DATA_PATH = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/analysis/group_statistics_size_dist.csv"
OUT_FIG = "/public/home/blockchain_2/slave3/deanonymization/EntityRecognition/SCC/analysis/figures/group_size_powerlaw_fit.png"

# Ensure output directory exists
os.makedirs(os.path.dirname(OUT_FIG), exist_ok=True)

############################################
# Load data
############################################
df = pd.read_csv(DATA_PATH)

# group_size: number of addresses per entity
# count: number of entities with this size
x = df["group_size"].astype(float).values
y = df["count"].astype(float).values

############################################
# Power-law fitting
############################################
log_x = np.log10(x)
log_y = np.log10(y)

slope, intercept = np.polyfit(log_x, log_y, 1)
alpha = -slope

############################################
# Find maxima to annotate
############################################
idx_max_x = int(np.argmax(x))
max_entity_size = x[idx_max_x]
max_entity_count = y[idx_max_x]

idx_max_y = int(np.argmax(y))
max_num_entity_size = x[idx_max_y]
max_num_entity = y[idx_max_y]

############################################
# Plot
############################################
plt.figure(figsize=(9, 7))  # slightly larger figure

# Scatter plot
plt.scatter(x, y)

# Log-log scale
plt.xscale("log")
plt.yscale("log")

plt.xlabel("Entity Size (Number of Addresses)")
plt.ylabel("Number of Entities")
plt.title(f"Distribution of Entity Size (Addresses per Entity)")

############################################
# Annotations (bigger text + arrows)
############################################
plt.scatter(
    max_num_entity_size,
    max_num_entity,
    marker="^",
    s=140
)
plt.annotate(
    f"Max Number of Entities\n({int(max_num_entity_size)}, {int(max_num_entity)})",
    xy=(max_num_entity_size, max_num_entity),
    xytext=(0.60, 0.85),
    textcoords="axes fraction",
    fontsize=14,
    arrowprops=dict(arrowstyle="->", linewidth=1.5)
)

plt.scatter(
    max_entity_size,
    max_entity_count,
    marker="x",
    s=140
)
plt.annotate(
    f"Max Entity Size\n({int(max_entity_size)}, {int(max_entity_count)})",
    xy=(max_entity_size, max_entity_count),
    xytext=(0.60, 0.65),
    textcoords="axes fraction",
    fontsize=14,
    arrowprops=dict(arrowstyle="->", linewidth=1.5)
)

plt.tight_layout()
plt.savefig(OUT_FIG, dpi=300)
plt.close()

print("Power-law exponent alpha =", alpha)
print("Max Entity Size point =", (int(max_entity_size), int(max_entity_count)))
print("Max Number of Entities point =", (int(max_num_entity_size), int(max_num_entity)))
print("Figure saved to:", OUT_FIG)
