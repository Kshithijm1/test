"use client";
import { Box } from "@mui/material";
import React, { useEffect, useRef } from "react";

export function PlotlyChart({ data, layout }: { data: any[]; layout: any }) {
	const chartRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!data || data.length === 0) return;

		import("plotly.js-dist-min").then((Plotly) => {
			if (!chartRef.current) return;

			const safeLayout = layout ?? {};

			const hasDateX = data.some(
				(trace) =>
					Array.isArray(trace.x) &&
					typeof trace.x[0] === "string" &&
					/^\d{4}-\d{2}-\d{2}/.test(trace.x[0]),
			);

			const mergedLayout = {
				...safeLayout,
				autosize: true,
				height: 480,
				paper_bgcolor: "#ffffff",
				plot_bgcolor: "#fafbfd",
				margin: { t: 64, r: 40, b: 72, l: 80 },
				font: { family: "'Inter', 'Segoe UI', system-ui, sans-serif", size: 12, color: "#4a5568" },
				title: safeLayout.title
					? {
							text:
								typeof safeLayout.title === "string"
									? safeLayout.title
									: safeLayout.title.text,
							font: { size: 16, color: "#1a202c", family: "'Inter', 'Segoe UI', system-ui, sans-serif" },
							x: 0.02,
							xanchor: "left",
							y: 0.98,
						}
					: undefined,
				legend: {
					orientation: "h" as const,
					yanchor: "bottom",
					y: 1.04,
					xanchor: "left",
					x: 0,
					font: { size: 12, color: "#4a5568" },
					bgcolor: "rgba(0,0,0,0)",
					borderwidth: 0,
					itemsizing: "constant",
				},
				hovermode: "x unified" as const,
				hoverlabel: {
					bgcolor: "#1a202c",
					font: { color: "#fff", size: 12, family: "'Inter', sans-serif" },
					bordercolor: "transparent",
				},
				xaxis: {
					...(safeLayout.xaxis ?? {}),
					...(hasDateX && {
						type: "date",
						tickformat: "%b '%y",
						dtick: "M3",
						tickangle: 0,
					}),
					showgrid: false,
					showline: true,
					linecolor: "#e2e8f0",
					linewidth: 1,
					tickfont: { size: 11, color: "#718096" },
					title: {
						text:
							safeLayout.xaxis?.title?.text ?? safeLayout.xaxis?.title ?? "",
						font: { size: 12, color: "#4a5568" },
						standoff: 16,
					},
					zeroline: false,
				},
				yaxis: {
					showgrid: true,
					gridcolor: "#edf2f7",
					gridwidth: 1,
					griddash: "dot" as const,
					showline: false,
					tickfont: { size: 11, color: "#718096" },
					tickformat: ",.0f",
					...(safeLayout.yaxis ?? {}),
					title: {
						text:
							safeLayout.yaxis?.title?.text ?? safeLayout.yaxis?.title ?? "",
						font: { size: 12, color: "#4a5568" },
						standoff: 16,
					},
					zeroline: true,
					zerolinecolor: "#cbd5e0",
					zerolinewidth: 1,
				},
			};

			Plotly.newPlot(chartRef.current, data, mergedLayout, {
				responsive: true,
				displayModeBar: "hover",
				modeBarButtonsToRemove: ["lasso2d", "select2d"],
			});
		});
	}, [data, layout]);

	return (
		<Box sx={{ width: "100%", borderRadius: 2, overflow: "hidden" }}>
			<div
				ref={chartRef}
				style={{ width: "100%", display: "block" }}
			/>
		</Box>
	);
}
// ── Data classes ──────────────────────────────────────────────────────────────
export class ChartData {
	type: string;
	data: any[];
	layout: any;
	title?: string;

	constructor(type: string, data: any[], layout?: any, title?: string) {
		this.type = type;
		this.data = data;
		// Don't mutate the incoming layout object — clone it
		this.layout = layout ? { ...layout } : {};
		// Only set title if not already present in layout
		if (title && !this.layout.title) {
			this.layout.title = title;
		}
		this.title = title;
	}
}

export class LineGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new LineGraph(
			"LineGraph",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
export class BarGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new BarGraph(
			"BarGraph",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
export class ScatterPlotGraph extends ChartData {
	static fromData(payload: { data: any[]; layout?: any; title?: string }) {
		return new ScatterPlotGraph(
			"ScatterPlot",
			payload.data,
			payload.layout,
			payload.title,
		);
	}
}
