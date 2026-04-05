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

	// Manually read each chunk and forward it immediately to prevent buffering.
	// The previous TransformStream + pipeTo approach batched chunks together,
	// causing the frontend to miss intermediate "thinking" states.
	const upstream = pythonRes.body.getReader();
	const stream = new ReadableStream({
		async pull(controller) {
			const { done, value } = await upstream.read();
			if (done) {
				controller.close();
				return;
			}
			controller.enqueue(value);
		},
		cancel() {
			upstream.cancel();
		},
	});

	return new Response(stream, {
		headers: {
			"Content-Type": "text/plain; charset=utf-8",
			"X-Accel-Buffering": "no",
			"Cache-Control": "no-cache, no-transform",
		},
	});
}
