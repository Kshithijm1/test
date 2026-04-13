// app/api/chat/resume/route.ts
import { NextRequest } from "next/server";
import http from "http";

export const maxDuration = 300;
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
	const body = await req.text();
	const apiUrl = process.env.PYTHON_API_URL ?? "http://localhost:8000";
	const url = new URL("/chat/resume", apiUrl);

	const stream = new ReadableStream({
		start(controller) {
			const options = {
				hostname: url.hostname,
				port: parseInt(url.port) || 8000,
				path: url.pathname,
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Content-Length": Buffer.byteLength(body),
				},
			};

			const proxyReq = http.request(options, (proxyRes: any) => {
				proxyRes.on("data", (chunk: Buffer) => {
					controller.enqueue(new Uint8Array(chunk));
				});
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
