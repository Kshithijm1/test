// app/api/chat/route.ts
import { NextRequest } from "next/server";

export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
	const { prompt } = await req.json();

	if (!prompt?.trim()) {
		return new Response(JSON.stringify({ error: "Prompt is required" }), {
			status: 400,
			headers: { "Content-Type": "application/json" },
		});
	}

	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
	const pythonRes = await fetch(`${apiUrl}/chat`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ prompt }),
	});

	if (!pythonRes.ok) {
		return new Response(
			JSON.stringify({ error: `Upstream error: ${pythonRes.status}` }),
			{ status: 502, headers: { "Content-Type": "application/json" } },
		);
	}

	if (!pythonRes.body) {
		return new Response(
			JSON.stringify({ error: "No response body from upstream" }),
			{ status: 502, headers: { "Content-Type": "application/json" } },
		);
	}

	// Manually read each chunk from the Python backend and immediately
	// enqueue it to the browser stream — prevents buffering by the proxy.
	const reader = pythonRes.body.getReader();

	const stream = new ReadableStream({
		async pull(controller) {
			const { done, value } = await reader.read();
			if (done) {
				controller.close();
				return;
			}
			controller.enqueue(value);
		},
		cancel() {
			reader.cancel();
		},
	});

	return new Response(stream, {
		headers: {
			"Content-Type": "text/event-stream; charset=utf-8",
			"X-Accel-Buffering": "no",
			"Cache-Control": "no-cache, no-transform",
			"Connection": "keep-alive",
			"Transfer-Encoding": "chunked",
		},
	});
}
