# Plots

Rules for every chart in an LAA report, app screen or web page, plus drop-in styles for matplotlib and Plotly. The live examples are `ElevationProfile` and `AcclimatisationChart`.

## Rules

- **One message per plot.** Title it with the finding, not the variable: "Slept 600 m below each high point", not "Altitude vs day".
- **Orange is the subject.** `series-1` (`brand`) is the series the plot is about. Comparison series go `series-2` (glacier blue), then `series-3` (granite). `series-4` and `series-5` only when a fifth reading is unavoidable; past five, split the plot.
- **Area under altitude.** Elevation and altitude lines get a `chart-area` fill to the baseline; other series are lines only, 2px.
- **Grid:** horizontal gridlines in `chart-grid`, 1px. No vertical gridlines, no top or right spines, no plot border. The x baseline is 1px `line-strong`.
- **Labels:** label lines directly at their right end in the series colour (bold `body-sm`). Use a legend only when lines overlap at the end.
- **Numbers:** ticks in `tick` (`numeric`, 12px, `ink-muted`, tabular). Altitude in metres with a thousands separator; time as `h:mm` or day number. Annotate the summit with its height in `stat` weight.
- **Events:** camps, summit and turnaround as small markers (6px circle, `surface-000` fill, 2px series-colour stroke) with a `body-sm` label above.
- **Background:** `surface-000`. Export at 2x (or SVG) and at the report column width (680px, or 1120px full-bleed).
- **Dark:** the same plot in the dark theme swaps every value for its dark token; nothing else changes.

## matplotlib

Save as `laa.mplstyle` and call `plt.style.use("laa.mplstyle")`. Install Barlow locally (Google Fonts) or matplotlib falls back to DejaVu Sans.

```
# LAA light — generated from tokens.json
font.family: Barlow, Barlow Semi Condensed, DejaVu Sans
font.size: 11
text.color: 242428
axes.labelcolor: 666671
axes.titlesize: 16
axes.titleweight: 600
axes.titlelocation: left
axes.titlepad: 14
axes.facecolor: ffffff
axes.edgecolor: 8a8a96
axes.linewidth: 0.8
axes.spines.top: False
axes.spines.right: False
axes.spines.left: False
axes.grid: True
axes.grid.axis: y
axes.axisbelow: True
axes.prop_cycle: cycler('color', ['fc4c02', '1f6fb2', '4a4a55', '2e8540', 'a37500'])
grid.color: e6e6eb
grid.linewidth: 0.8
xtick.color: 666671
ytick.color: 666671
xtick.labelsize: 9
ytick.labelsize: 9
ytick.left: False
lines.linewidth: 2
lines.solid_capstyle: round
legend.frameon: False
legend.fontsize: 9
figure.facecolor: ffffff
figure.dpi: 150
savefig.dpi: 200
savefig.bbox: tight
```

For dark, change: `text.color: f2f2f5`, `axes.labelcolor` / `xtick.color` / `ytick.color: a3a3ad`, `axes.facecolor` / `figure.facecolor: 1c1c20`, `axes.edgecolor: 6a6a75`, `grid.color: 2c2c32`, cycle `['fc4c02', '5aa9e6', 'c4c4cc', '5cc77a', 'ffc94a']`.

Elevation profile in four lines:

```python
ax.plot(dist_km, alt_m, color="#fc4c02")
ax.fill_between(dist_km, alt_m, alt_m.min() - 100, color="#fc4c02", alpha=0.14, lw=0)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
ax.annotate(f"{alt_m.max():,.0f} m", (dist_km[alt_m.argmax()], alt_m.max()), xytext=(0, 8), textcoords="offset points", ha="center", weight=600)
```

## Plotly

```python
import plotly.graph_objects as go, plotly.io as pio
pio.templates["laa"] = go.layout.Template(layout=dict(
    font=dict(family="Barlow, system-ui, sans-serif", size=13, color="#242428"),
    title=dict(x=0, xanchor="left", font=dict(size=18, color="#242428")),
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    colorway=["#fc4c02", "#1f6fb2", "#4a4a55", "#2e8540", "#a37500"],
    xaxis=dict(showgrid=False, linecolor="#8a8a96", ticks="", tickfont=dict(color="#666671", family="Barlow Semi Condensed")),
    yaxis=dict(gridcolor="#e6e6eb", zeroline=False, showline=False, tickformat=",", tickfont=dict(color="#666671", family="Barlow Semi Condensed")),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor="#dfdfe8", font=dict(color="#242428")),
    showlegend=False, margin=dict(l=48, r=24, t=56, b=40)))
pio.templates.default = "laa"
```

## Sequential and categorical

- Heatmaps, altitude bands and maps: `seq-100` → `seq-500` (low to high). Never a rainbow.
- Categorical (team members, routes): `series-1` … `series-5` in order.
- Diverging (temperature anomaly, faster/slower than plan): `series-2` blue for below, `brand` for above, `surface-200` at zero.
