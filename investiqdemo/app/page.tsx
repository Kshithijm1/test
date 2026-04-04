"use client";
import { Box } from "@mui/material";
import InputBox from "./components/InputBox";
import GraphBox from "./components/GraphBox";
import { useState, useEffect, useCallback, useRef } from "react";
import ChatBox from "./components/ChatBox";
import {
    LineGraph,
    BarGraph,
    ScatterPlotGraph,
    ChartData,
} from "./classes/charts";
import { parseStream, DisplayModule, AgentStatusDetail } from "./hooks/useStreamParser";


/**
 * Trace template builders for each use case.
 * Each template defines the exact Plotly trace structure for that use case.
 */
const TRACE_TEMPLATES = {
	// Use Case 1: Single line chart (one X, one Y)
	"1": (config: any, sqlRows: Record<string, any>[]) => {
		const xValues = sqlRows.map((row) => row[config.x]);
		const yValues = sqlRows.map((row) => row[config.y]);
		
		console.log(`[UC1] Single line: x="${config.x}", y="${config.y}"`);
		console.log(`[UC1] Data points: ${xValues.length}, mode: ${config.mode}`);
		
		return [{
			x: xValues,
			y: yValues,
			type: "scatter" as const,
			mode: config.mode || "lines+markers",
			name: config.name || config.y,
			connectgaps: true,
		}];
	},

	// Use Case 2: Scatter plot (one X, one Y, markers only)
	"2": (config: any, sqlRows: Record<string, any>[]) => {
		const xValues = sqlRows.map((row) => row[config.x]);
		const yValues = sqlRows.map((row) => row[config.y]);
		
		console.log(`[UC2] Scatter plot: x="${config.x}", y="${config.y}"`);
		console.log(`[UC2] Data points: ${xValues.length}, mode: markers`);
		
		return [{
			x: xValues,
			y: yValues,
			type: "scatter" as const,
			mode: "markers",
			name: config.name || config.y,
			marker: { size: 8 },
		}];
	},

	// Use Case 3: Multi-line chart (one X, multiple Y)
	"3": (config: any, sqlRows: Record<string, any>[]) => {
		const xValues = sqlRows.map((row) => row[config.x]);
		const yCols = Array.isArray(config.y) ? config.y : [config.y];
		const names = Array.isArray(config.name) ? config.name : [config.name];
		
		console.log(`[UC3] Multi-line: x="${config.x}", y=[${yCols.join(", ")}]`);
		console.log(`[UC3] Lines: ${yCols.length}, data points: ${xValues.length}`);
		
		return yCols.map((yCol: string, i: number) => {
			const yValues = sqlRows.map((row) => row[yCol]);
			return {
				x: xValues,
				y: yValues,
				type: "scatter" as const,
				mode: config.mode || "lines+markers",
				name: names[i] || yCol,
				connectgaps: true,
			};
		});
	},
};

/**
 * Build Plotly traces + layout using template-based approach.
 * Each use case has a predefined trace structure.
 */
function buildPlotlyChart(
	config: any,
	sqlRows: Record<string, any>[]
): { data: any[]; layout: any } {
	console.log("[buildPlotlyChart] ===== START =====");
	console.log("[buildPlotlyChart] Use case:", config.usecase);
	console.log("[buildPlotlyChart] Config:", config);
	console.log("[buildPlotlyChart] SQL rows:", sqlRows.length);
	console.log("[buildPlotlyChart] Available columns:", Object.keys(sqlRows[0] || {}));

	// Validate use case
	const usecase = config.usecase || "1";
	const templateBuilder = TRACE_TEMPLATES[usecase as keyof typeof TRACE_TEMPLATES];
	
	if (!templateBuilder) {
		console.error(`[buildPlotlyChart] Unknown use case: "${usecase}". Defaulting to UC1.`);
		const traces = TRACE_TEMPLATES["1"](config, sqlRows);
		return { data: traces, layout: buildLayout(config) };
	}

	// Build traces using template
	const traces = templateBuilder(config, sqlRows);
	console.log("[buildPlotlyChart] Generated traces:", traces.length);
	console.log("[buildPlotlyChart] ===== END =====");

	return { data: traces, layout: buildLayout(config) };
}

/**
 * Build Plotly layout from config
 */
function buildLayout(config: any): any {
	const yAxisTitle = Array.isArray(config.update_yaxis_title_text)
		? config.update_yaxis_title_text[0]
		: config.update_yaxis_title_text || "";

	return {
		title: config.update_layout_title || "",
		xaxis: { title: config.update_xaxis_title_text || "" },
		yaxis: { title: yAxisTitle },
	};
}


export interface AgentStep {
    agent: string;
    status: "started" | "completed";
    message: string;
    detail?: AgentStatusDetail;
}

export interface ChatMessage {
    type: "user" | "bot" | "thinking" | "status";
    text: string;
    steps?: AgentStep[];
}


type BackendStatus = "checking" | "online" | "offline";


const SUBMIT_TIMEOUT_MS = 180_000;


export default function Home() {
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [displayBox, setDisplayBox] = useState<ChartData[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const sqlDataRef = useRef<Record<string, any>[]>([]);
    const chartConfigRef = useRef<any>(null);
    const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");

    // Build chart only when BOTH sql_data and chart config are available
    const tryBuildChart = useCallback(() => {
        const config = chartConfigRef.current;
        const rows = sqlDataRef.current;
        if (!config || rows.length === 0) return;

        console.log("[tryBuildChart] Building chart with", rows.length, "rows");
        console.log("[tryBuildChart] Full config object:", config);
        console.log("[tryBuildChart] config.graphType:", config.graphType);
        console.log("[tryBuildChart] config.config.usecase:", config.config?.usecase);
        
        const { data: traces, layout } = buildPlotlyChart(config.config, rows);
        const graphType = config.graphType || "LineGraph";
        const payload = { data: traces, layout, title: config.config.update_layout_title };

        console.log("[tryBuildChart] Determined graphType:", graphType);
        console.log("[tryBuildChart] Creating chart class:", 
            graphType === "ScatterPlot" ? "ScatterPlotGraph" :
            graphType === "BarGraph" ? "BarGraph" : "LineGraph");

        if (graphType === "ScatterPlot") {
            setDisplayBox((prev) => [...prev, ScatterPlotGraph.fromData(payload)]);
        } else if (graphType === "BarGraph") {
            setDisplayBox((prev) => [...prev, BarGraph.fromData(payload)]);
        } else {
            setDisplayBox((prev) => [...prev, LineGraph.fromData(payload)]);
        }

        // Clear refs so we don't rebuild on next call
        chartConfigRef.current = null;
    }, []);


    // ── Backend health poll ───────────────────────────────────────────────────
    useEffect(() => {
        const check = () => {
            fetch("/api/health")
                .then((r) => r.json())
                .then((body) =>
                    setBackendStatus(body.status === "online" ? "online" : "offline"),
                )
                .catch(() => setBackendStatus("offline"));
        };
        check();
        const interval = setInterval(check, 30_000);
        return () => clearInterval(interval);
    }, []);


    const toolHandlers = useCallback((module: any) => {
        if (module.type === "chart" && module.config) {
            // Store chart config and try to build
            console.log("[toolHandlers] Received chart config, storing...");
            chartConfigRef.current = module;
            tryBuildChart();
        } else {
            // Old format: pre-built Plotly traces
            const payload = { data: module.data, layout: module.layout, title: module.title };
            if (module.type === "LineGraph") {
                setDisplayBox((prev) => [...prev, LineGraph.fromData(payload)]);
            } else if (module.type === "BarGraph") {
                setDisplayBox((prev) => [...prev, BarGraph.fromData(payload)]);
            } else if (module.type === "ScatterPlot") {
                setDisplayBox((prev) => [...prev, ScatterPlotGraph.fromData(payload)]);
            } else {
                console.warn(`No handler for module type: "${module.type}"`);
            }
        }
    }, [tryBuildChart]);


    // ── Submit handler ────────────────────────────────────────────────────────
    const handleSubmit = async (prompt: string) => {
        if (!prompt.trim() || isLoading) return;


        setIsLoading(true);


        setChatMessages((prev) => [
            ...prev,
            { text: prompt, type: "user" },
            { text: "", type: "status", steps: [] },
        ]);


        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), SUBMIT_TIMEOUT_MS);
        let botSeeded = false;


        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt }),
                signal: controller.signal,
            });


            if (!response.ok)
                throw new Error(`HTTP error! status: ${response.status}`);


            await parseStream(response, {
                onSqlData: (payload) => {
                    console.log("[page] Received SQL data:", payload.data?.length, "rows");
                    sqlDataRef.current = payload.data || [];
                    tryBuildChart();
                },

                onAgentStatus: (payload) => {
                    setChatMessages((prev) => {
                        const updated = [...prev];
                        // Find the last status message
                        const statusIdx = updated.findLastIndex((m) => m.type === "status");
                        if (statusIdx === -1) return prev;
                        const statusMsg = { ...updated[statusIdx] };
                        const steps = [...(statusMsg.steps || [])];

                        if (payload.status === "started") {
                            steps.push({ agent: payload.agent, status: "started", message: payload.message });
                        } else if (payload.status === "completed") {
                            const stepData: AgentStep = {
                                agent: payload.agent,
                                status: "completed",
                                message: payload.message,
                                detail: payload.detail,
                            };
                            // Update the matching started step to completed
                            const idx = steps.findLastIndex((s) => s.agent === payload.agent && s.status === "started");
                            if (idx !== -1) {
                                steps[idx] = stepData;
                            } else {
                                steps.push(stepData);
                            }
                        }

                        statusMsg.steps = steps;
                        updated[statusIdx] = statusMsg;
                        return updated;
                    });
                },

                onThinking: (_text) => {
                    // Raw LLM tokens suppressed — agent_status handles progress display
                },


                onResponse: (text) => {
                    if (!botSeeded) {
                        setChatMessages((prev) => [
                            ...prev,
                            { text: "", type: "bot" },
                        ]);
                        botSeeded = true;
                    }
                    setChatMessages((prev) => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];
                        if (last.type !== "bot") return prev;
                        updated[updated.length - 1] = {
                            ...last,
                            text: last.text + text,
                        };
                        return updated;
                    });
                },
                


                onDisplay: (modules) => {
                    console.log("Received display modules in page.tsx:", modules);
                    modules.forEach(toolHandlers);
                },
            });
        } catch (error) {
            const isAbort =
                error instanceof DOMException && error.name === "AbortError";
            const message = isAbort
                ? "Request timed out. Please try again."
                : "Something went wrong. Please try again.";


            if (!isAbort) console.error("Chat API error:", error);


            setChatMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = { text: message, type: "bot" };
                return updated;
            });
        } finally {
            clearTimeout(timeoutId);
            setIsLoading(false);
        }
    };


    // ── Status indicator config ───────────────────────────────────────────────
    const statusColor: Record<BackendStatus, string> = {
        checking: "#facc15",
        online: "#22c55e",
        offline: "#ef4444",
    };
    const statusLabel: Record<BackendStatus, string> = {
        checking: "Connecting",
        online: "Connected",
        offline: "Offline",
    };


    return (
        <Box
            sx={{
                height: "100vh",
                width: "100vw",
                display: "flex",
                flexDirection: "column",
                bgcolor: "#f0f4fb",
                overflow: "hidden",
            }}
        >
            {/* Header */}
            <Box
                sx={{
                    px: 4,
                    py: 1.5,
                    bgcolor: "white",
                    borderBottom: "1px solid #e3eaf5",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    boxShadow: "0 1px 4px rgba(25,118,210,0.06)",
                    flexShrink: 0,
                }}
            >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <Box
                        sx={{
                            width: 32,
                            height: 32,
                            borderRadius: "8px",
                            bgcolor: "#1976d2",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            boxShadow: "0 2px 8px rgba(25,118,210,0.3)",
                        }}
                    >
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                            <path
                                d="M3 8h10M8 3v10"
                                stroke="white"
                                strokeWidth="2"
                                strokeLinecap="round"
                            />
                        </svg>
                    </Box>
                    <Box
                        component="span"
                        sx={{
                            fontSize: "1rem",
                            fontWeight: 700,
                            color: "#1a1a2e",
                            letterSpacing: "-0.01em",
                        }}
                    >
                        Analyst
                    </Box>
                    <Box
                        component="span"
                        sx={{
                            fontSize: "0.65rem",
                            fontWeight: 600,
                            color: "#1976d2",
                            bgcolor: "rgba(25,118,210,0.08)",
                            border: "1px solid rgba(25,118,210,0.2)",
                            px: 1,
                            py: 0.25,
                            borderRadius: "4px",
                            letterSpacing: "0.08em",
                            textTransform: "uppercase",
                        }}
                    >
                        Beta
                    </Box>
                </Box>


                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Box
                        sx={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            bgcolor: statusColor[backendStatus],
                            boxShadow: `0 0 6px ${statusColor[backendStatus]}80`,
                            transition: "background-color 0.3s",
                        }}
                    />
                    <Box
                        sx={{
                            fontSize: "0.75rem",
                            color: "#90a4c0",
                            letterSpacing: "0.04em",
                        }}
                    >
                        {statusLabel[backendStatus]}
                    </Box>
                </Box>
            </Box>


            {/* Main content */}
            <Box sx={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
                {/* Left: Chat Panel */}
                <Box
                    sx={{
                        width: "520px",
                        flexShrink: 0,
                        display: "flex",
                        flexDirection: "column",
                        borderRight: "1px solid #e3eaf5",
                        bgcolor: "#f8fafd",
                        minHeight: 0,
                        overflow: "hidden",
                    }}
                >
                    <Box
                        sx={{
                            px: 3,
                            py: 1.5,
                            borderBottom: "1px solid #e3eaf5",
                            bgcolor: "white",
                            flexShrink: 0,
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                        }}
                    >
                        <Box
                            sx={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                bgcolor: "#1976d2",
                            }}
                        />
                        <Box
                            sx={{
                                fontSize: "0.7rem",
                                fontWeight: 600,
                                color: "#90a4c0",
                                letterSpacing: "0.1em",
                                textTransform: "uppercase",
                            }}
                        >
                            Conversation
                        </Box>
                    </Box>


                    <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
                        <ChatBox chatMessages={chatMessages} />
                    </Box>


                    <Box
                        sx={{
                            p: 2,
                            borderTop: "1px solid #e3eaf5",
                            flexShrink: 0,
                            bgcolor: "white",
                        }}
                    >
                        <InputBox
                            handleSubmit={handleSubmit}
                            disabled={isLoading}
                        />
                    </Box>
                </Box>


                {/* Right: Graph Panel */}
                <Box
                    sx={{
                        flex: 1,
                        display: "flex",
                        flexDirection: "column",
                        minWidth: 0,
                        minHeight: 0,
                        overflow: "hidden",
                        p: 2.5,
                    }}
                >
                    <GraphBox
                        charts={displayBox}
                        onChartsChange={setDisplayBox}
                    />
                </Box>
            </Box>
        </Box>
    );
}
