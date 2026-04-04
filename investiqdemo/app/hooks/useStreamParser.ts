// Strongly-typed shapes that match the backend NDJSON protocol
export interface ThinkingChunk {
	type: "thinking_content";
	data: string;
}

export interface ResponseChunk {
	type: "response_content";
	data: string;
}

export interface DisplayModule {
	type: "LineGraph" | "BarGraph" | "ScatterPlot";
	data: any[]; // ← was Record<string, unknown>
	layout?: any; // ← add this
	title?: string; // ← add this
}

export interface SqlDataChunk {
	type: "sql_data";
	data: {
		query: string;
		data: Record<string, any>[];
	};
}

export interface DisplayChunk {
	type: "display_modules";
	data: DisplayModule[];
}

export interface AgentStatusDetail {
	plan_summary?: string;
	sql?: string;
	preview?: Record<string, any>[];
	columns?: string[];
	total_rows?: number;
	config?: Record<string, any>;
	config_raw?: string;
}

export interface AgentStatusChunk {
	type: "agent_status";
	data: {
		agent: string;
		status: "started" | "completed";
		message: string;
		detail?: AgentStatusDetail;
	};
}

export type StreamChunk = ThinkingChunk | ResponseChunk | DisplayChunk | SqlDataChunk | AgentStatusChunk;

export interface StreamHandlers {
	onThinking: (text: string) => void;
	onResponse: (text: string) => void;
	onDisplay: (modules: DisplayModule[]) => void;
	onSqlData?: (payload: { query: string; data: Record<string, any>[] }) => void;
	onAgentStatus?: (payload: { agent: string; status: "started" | "completed"; message: string; detail?: AgentStatusDetail }) => void;
}

/**
 * Parses a streaming NDJSON response from the backend and dispatches
 * each chunk to the appropriate handler. Handles incomplete lines across
 * chunk boundaries via an internal line buffer.
 */
export async function parseStream(
	response: Response,
	handlers: StreamHandlers,
): Promise<void> {
	if (!response.body) {
		throw new Error("Response body is null");
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let lineBuffer = "";

	const dispatch = async (parsed: StreamChunk) => {
		if (parsed.type === "thinking_content") {
			handlers.onThinking(parsed.data);
		} else if (parsed.type === "response_content") {
			handlers.onResponse(parsed.data);
		} else if (parsed.type === "sql_data") {
			console.log("[useStreamParser] Received sql_data:", (parsed as SqlDataChunk).data.data?.length, "rows");
			handlers.onSqlData?.((parsed as SqlDataChunk).data);
		} else if (parsed.type === "display_modules") {
			console.log("[useStreamParser] Received display modules:", parsed.data);
			handlers.onDisplay(parsed.data);
		} else if (parsed.type === "agent_status") {
			console.log("[useStreamParser] Agent status:", (parsed as AgentStatusChunk).data);
			handlers.onAgentStatus?.((parsed as AgentStatusChunk).data);
			// Yield to React so it renders the status update before the next event
			await new Promise((r) => setTimeout(r, 30));
		}
	};

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;

		lineBuffer += decoder.decode(value, { stream: true });
		const lines = lineBuffer.split("\n");
		// Last element may be incomplete — keep it for the next read
		lineBuffer = lines.pop() ?? "";

		for (const line of lines) {
			if (!line.trim()) continue;
			try {
				const parsed = JSON.parse(line) as StreamChunk;
				await dispatch(parsed);
			} catch {
				console.warn("[useStreamParser] Failed to parse chunk:", line);
			}
		}
	}

	// Flush any remaining buffered content
	if (lineBuffer.trim()) {
		try {
			const parsed = JSON.parse(lineBuffer) as StreamChunk;
			await dispatch(parsed);
		} catch {
			console.warn(
				"[useStreamParser] Leftover unparseable buffer:",
				lineBuffer,
			);
		}
	}
}
