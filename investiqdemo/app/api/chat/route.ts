// app/api/chat/route.ts
import { NextRequest } from "next/server";
import http from "http";

export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
	const body = await req.json();
	const { prompt } = body;

	if (!prompt?.trim()) {
		return new Response(JSON.stringify({ error: "Prompt is required" }), {
			status: 400,
			headers: { "Content-Type": "application/json" },
		});
	}

	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
	const url = new URL("/chat", apiUrl);

	// Use Node.js native http module for true chunk-by-chunk streaming.
	// fetch() buffers small chunks internally, which batches agent events
	// and prevents the frontend from showing real-time "thinking" spinners.
	const stream = new ReadableStream({
		start(controller) {
			const postData = JSON.stringify(body);
			const options: http.RequestOptions = {
				hostname: url.hostname,
				port: url.port || 8000,
				path: url.pathname,
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Content-Length": Buffer.byteLength(postData),
				},
			};

			const proxyReq = http.request(options, (proxyRes) => {
				if (proxyRes.statusCode && proxyRes.statusCode >= 400) {
					controller.enqueue(
						new TextEncoder().encode(
							JSON.stringify({ type: "error", data: `Upstream error: ${proxyRes.statusCode}` }) + "\n"
						)
					);
					controller.close();
					return;
				}

				// Each 'data' event fires per TCP chunk — no buffering
				proxyRes.on("data", (chunk: Buffer) => {
					controller.enqueue(new Uint8Array(chunk));
				});

				proxyRes.on("end", () => {
					controller.close();
				});

				proxyRes.on("error", (err) => {
					console.error("[proxy] upstream error:", err);
					controller.error(err);
				});
			});

			proxyReq.on("error", (err) => {
				console.error("[proxy] request error:", err);
				controller.error(err);
			});

			proxyReq.write(postData);
			proxyReq.end();
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


export async function PUT(req: NextRequest) {
	// PUT /api/chat is used for /chat/resume — proxy to Python backend
	const body = await req.text();
	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
	const url = new URL("/chat/resume", apiUrl);

	const stream = new ReadableStream({
		start(controller) {
			const options = {
				hostname: url.hostname,
				port: url.port || 8000,
				path: url.pathname,
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Content-Length": Buffer.byteLength(body),
				},
			};
			const proxyReq = http.request(options, (proxyRes: any) => {
				proxyRes.on("data", (chunk: Buffer) => controller.enqueue(new Uint8Array(chunk)));
				proxyRes.on("end", () => controller.close());
				proxyRes.on("error", (err: any) => controller.error(err));
			});
			proxyReq.on("error", (err: any) => controller.error(err));
			proxyReq.write(body);
			proxyReq.end();
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
